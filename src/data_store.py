import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

Source = Literal["upbit", "binance"]

TIMEFRAME_HOURS = {"1h": 1, "4h": 4}

_TABLE_BY_SOURCE = {
    "upbit": "upbit_candles",
    "binance": "binance_candles",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS {table} (
    market TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    candle_time TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (market, timeframe, candle_time)
);
"""


@dataclass(frozen=True)
class TickerInfo:
    market: str
    trade_price_24h: float


@dataclass(frozen=True)
class Candle:
    market: str
    timeframe: str
    candle_time: datetime  # UTC
    open: float
    high: float
    low: float
    close: float
    volume: float


def close_time(candle: Candle) -> datetime:
    """When the candle's interval finishes -- candle_time is the OPEN time on both exchanges."""
    return candle.candle_time + timedelta(hours=TIMEFRAME_HOURS[candle.timeframe])


def drop_unclosed(candles: list[Candle], now: datetime | None = None) -> list[Candle]:
    """Discard the still-forming candle both exchanges return as their last element.

    Using it made the live check read a partial bar, which contradicted BR7 ("가장 최근 마감된 1h 봉")
    and quietly defeated the scheduler's :05 offset -- that offset exists precisely to wait for the
    bar to close. It also meant a golden cross could appear and then vanish when the bar settled,
    and that no reproducible entry price existed to publish.
    """
    reference = now or datetime.now(timezone.utc)
    return [c for c in candles if close_time(c) <= reference]


@dataclass(frozen=True)
class RecommendationRecord:
    market: str
    expected_return: float
    n: int
    hit_count: int
    target_reached: bool | None = None
    realized_return: float | None = None
    evaluated_at: datetime | None = None
    source: str = "upbit"
    entry_time: datetime | None = None
    entry_price: float | None = None
    max_drawdown: float | None = None


@dataclass(frozen=True)
class PipelineRunResult:
    run_time: datetime | None
    regime_bullish: bool
    recommendations: list[RecommendationRecord]


_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_time TEXT PRIMARY KEY,
    regime_bullish INTEGER NOT NULL
);
"""

_RECOMMENDATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
    run_time TEXT NOT NULL,
    market TEXT NOT NULL,
    expected_return REAL NOT NULL,
    n INTEGER NOT NULL,
    hit_count INTEGER NOT NULL,
    target_reached INTEGER,
    realized_return REAL,
    evaluated_at TEXT,
    PRIMARY KEY (run_time, market)
);
"""

# Migration for DBs created before outcome tracking existed (NFR-L3) -- CREATE TABLE IF NOT EXISTS
# above only covers fresh DBs, so already-deployed `recommendations` tables need these added explicitly.
_RECOMMENDATIONS_OUTCOME_COLUMNS = [
    ("target_reached", "INTEGER"),
    ("realized_return", "REAL"),
    ("evaluated_at", "TEXT"),
    ("source", "TEXT"),
    ("entry_time", "TEXT"),
    ("entry_price", "REAL"),
    ("max_drawdown", "REAL"),
]


_RECOMMENDATIONS_SELECT = (
    "SELECT market, expected_return, n, hit_count, target_reached, realized_return, evaluated_at, source, "
    "entry_time, entry_price, max_drawdown FROM recommendations"
)


def _row_to_recommendation_record(row) -> RecommendationRecord:
    (
        market,
        expected_return,
        n,
        hit_count,
        target_reached,
        realized_return,
        evaluated_at,
        source,
        entry_time,
        entry_price,
        max_drawdown,
    ) = row
    return RecommendationRecord(
        market=market,
        expected_return=expected_return,
        n=n,
        hit_count=hit_count,
        target_reached=None if target_reached is None else bool(target_reached),
        realized_return=realized_return,
        evaluated_at=None if evaluated_at is None else datetime.fromisoformat(evaluated_at),
        source=source or "upbit",
        entry_time=None if entry_time is None else datetime.fromisoformat(entry_time),
        entry_price=entry_price,
        max_drawdown=max_drawdown,
    )


class DataStore:
    """SQLite persistence for Upbit and Binance candles.

    Uses WAL journal mode and a short-lived connection per operation so the
    scheduler thread and API request threads can safely access the DB
    concurrently (see nfr-design/nfr-design-patterns.md).
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            for table in _TABLE_BY_SOURCE.values():
                conn.execute(_SCHEMA.format(table=table))
            conn.execute(_RUNS_SCHEMA)
            conn.execute(_RECOMMENDATIONS_SCHEMA)
            for column, col_type in _RECOMMENDATIONS_OUTCOME_COLUMNS:
                try:
                    conn.execute(f"ALTER TABLE recommendations ADD COLUMN {column} {col_type}")
                except sqlite3.OperationalError as exc:
                    if "duplicate column name" not in str(exc):
                        raise

    def upsert_candles(self, source: Source, market: str, timeframe: str, candles: list[Candle]) -> int:
        if not candles:
            return 0
        table = _TABLE_BY_SOURCE[source]
        rows = [
            (
                market,
                timeframe,
                c.candle_time.isoformat(),
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume,
            )
            for c in candles
        ]
        with self._connect() as conn:
            conn.executemany(
                f"""
                INSERT INTO {table} (market, timeframe, candle_time, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market, timeframe, candle_time) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume
                """,
                rows,
            )
        return len(rows)

    def get_last_candle_time(self, source: Source, market: str, timeframe: str) -> datetime | None:
        table = _TABLE_BY_SOURCE[source]
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT MAX(candle_time) FROM {table} WHERE market = ? AND timeframe = ?",
                (market, timeframe),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return datetime.fromisoformat(row[0])

    def get_first_candle_time(self, source: Source, market: str, timeframe: str) -> datetime | None:
        """Earliest stored candle -- lets the collector tell "history is shorter than the configured
        lookback" (needs backfilling) apart from "already deep enough" (incremental is enough)."""
        table = _TABLE_BY_SOURCE[source]
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT MIN(candle_time) FROM {table} WHERE market = ? AND timeframe = ?",
                (market, timeframe),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return datetime.fromisoformat(row[0])

    def get_candles(
        self,
        source: Source,
        market: str,
        timeframe: str,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Candle]:
        table = _TABLE_BY_SOURCE[source]
        query = f"SELECT market, timeframe, candle_time, open, high, low, close, volume FROM {table} WHERE market = ? AND timeframe = ?"
        params: list = [market, timeframe]
        if since is not None:
            query += " AND candle_time >= ?"
            params.append(since.isoformat())
        query += " ORDER BY candle_time ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            Candle(
                market=r[0],
                timeframe=r[1],
                candle_time=datetime.fromisoformat(r[2]),
                open=r[3],
                high=r[4],
                low=r[5],
                close=r[6],
                volume=r[7],
            )
            for r in rows
        ]

    def save_run(self, run_time: datetime, regime_bullish: bool, recommendations: list) -> None:
        """BR3/BR6: always records that a run happened (even with 0 recommendations), so callers can
        distinguish "ran, found nothing" from "never ran". `recommendations` items just need
        .market/.expected_return/.n/.hit_count attributes (duck-typed, avoids importing scorer.Recommendation)."""
        run_time_str = run_time.isoformat()
        rows = []
        for r in recommendations:
            entry_time = getattr(r, "entry_time", None)
            rows.append(
                (
                    run_time_str,
                    r.market,
                    r.expected_return,
                    r.n,
                    r.hit_count,
                    getattr(r, "source", "upbit"),
                    entry_time.isoformat() if entry_time is not None else None,
                    getattr(r, "entry_price", None),
                    getattr(r, "max_drawdown", None),
                )
            )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO pipeline_runs (run_time, regime_bullish) VALUES (?, ?)",
                (run_time_str, int(regime_bullish)),
            )
            if rows:
                conn.executemany(
                    "INSERT INTO recommendations (run_time, market, expected_return, n, hit_count, source, "
                    "entry_time, entry_price, max_drawdown) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )

    def get_latest_run(self) -> PipelineRunResult | None:
        """BR6: returns None if the pipeline has never run yet (distinct from a run with 0 recommendations)."""
        with self._connect() as conn:
            row = conn.execute("SELECT run_time, regime_bullish FROM pipeline_runs ORDER BY run_time DESC LIMIT 1").fetchone()
            if row is None:
                return None
            run_time_str, regime_bullish = row
            rec_rows = conn.execute(
                f"{_RECOMMENDATIONS_SELECT} WHERE run_time = ? ORDER BY expected_return DESC",
                (run_time_str,),
            ).fetchall()
        return PipelineRunResult(
            run_time=datetime.fromisoformat(run_time_str),
            regime_bullish=bool(regime_bullish),
            recommendations=[_row_to_recommendation_record(r) for r in rec_rows],
        )

    def get_recent_runs(self, limit: int) -> list[PipelineRunResult]:
        """BR10: most recent `limit` runs (newest first), each with its own recommendations."""
        with self._connect() as conn:
            run_rows = conn.execute(
                "SELECT run_time, regime_bullish FROM pipeline_runs ORDER BY run_time DESC LIMIT ?", (limit,)
            ).fetchall()
            runs = []
            for run_time_str, regime_bullish in run_rows:
                rec_rows = conn.execute(
                    f"{_RECOMMENDATIONS_SELECT} WHERE run_time = ? ORDER BY expected_return DESC",
                    (run_time_str,),
                ).fetchall()
                runs.append(
                    PipelineRunResult(
                        run_time=datetime.fromisoformat(run_time_str),
                        regime_bullish=bool(regime_bullish),
                        recommendations=[_row_to_recommendation_record(r) for r in rec_rows],
                    )
                )
        return runs

    def get_pending_evaluations(self, older_than: datetime) -> list[tuple[str, datetime, str]]:
        """BR12: (market, run_time, source) triples not yet evaluated, whose 24h window has already closed."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT market, run_time, source FROM recommendations WHERE evaluated_at IS NULL AND run_time <= ?",
                (older_than.isoformat(),),
            ).fetchall()
        return [(market, datetime.fromisoformat(run_time_str), source or "upbit") for market, run_time_str, source in rows]

    def record_outcome(self, outcome) -> None:
        """BR9/BR11: persists a RecommendationOutcome onto its recommendation row.
        `outcome` just needs .market/.run_time/.target_reached/.realized_return/.evaluated_at (duck-typed,
        avoids importing backtest.RecommendationOutcome -- same pattern as save_run)."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE recommendations
                SET target_reached = ?, realized_return = ?, evaluated_at = ?
                WHERE run_time = ? AND market = ?
                """,
                (
                    int(outcome.target_reached),
                    outcome.realized_return,
                    outcome.evaluated_at.isoformat(),
                    outcome.run_time.isoformat(),
                    outcome.market,
                ),
            )

    def ping(self) -> bool:
        """RESILIENCY-06: basic DB connectivity check for the health endpoint."""
        with self._connect() as conn:
            conn.execute("SELECT 1")
        return True
