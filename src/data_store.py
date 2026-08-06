import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

Source = Literal["upbit", "binance"]

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
class Candle:
    market: str
    timeframe: str
    candle_time: datetime  # UTC
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class RecommendationRecord:
    market: str
    expected_return: float
    n: int
    hit_count: int


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
    PRIMARY KEY (run_time, market)
);
"""


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
        rows = [(run_time_str, r.market, r.expected_return, r.n, r.hit_count) for r in recommendations]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO pipeline_runs (run_time, regime_bullish) VALUES (?, ?)",
                (run_time_str, int(regime_bullish)),
            )
            if rows:
                conn.executemany(
                    "INSERT INTO recommendations (run_time, market, expected_return, n, hit_count) VALUES (?, ?, ?, ?, ?)",
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
                "SELECT market, expected_return, n, hit_count FROM recommendations WHERE run_time = ? ORDER BY expected_return DESC",
                (run_time_str,),
            ).fetchall()
        recommendations = [RecommendationRecord(market=r[0], expected_return=r[1], n=r[2], hit_count=r[3]) for r in rec_rows]
        return PipelineRunResult(
            run_time=datetime.fromisoformat(run_time_str),
            regime_bullish=bool(regime_bullish),
            recommendations=recommendations,
        )

    def ping(self) -> bool:
        """RESILIENCY-06: basic DB connectivity check for the health endpoint."""
        with self._connect() as conn:
            conn.execute("SELECT 1")
        return True
