import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

Source = Literal["upbit", "binance"]

# 1m은 BR22 가격 감시 전용 (저장하지 않고 조회만 한다). 빠지면 drop_unclosed가 KeyError를
# 내고, 감시 루프의 예외 처리에 먹혀 "이벤트 0건"으로 조용히 넘어간다.
# 1m은 BR22 가격 감시 전용(저장하지 않고 조회만). 나머지는 BR25 4트랙이 쓰는 수집 대상이다.
# 여기 빠진 타임프레임을 조회하면 drop_unclosed가 KeyError를 내고, 수집 루프의 예외 처리에
# 먹혀 "봉 0건"으로 조용히 넘어간다 -- 새 타임프레임을 늘릴 때 반드시 함께 등록한다.
# 1M(월봉)은 길이가 고르지 않아 30일 근사값이다 (마감 판정에만 쓰므로 오차가 문제되지 않는다).
TIMEFRAME_HOURS = {
    "1m": 1 / 60,
    "15m": 0.25,
    "30m": 0.5,
    "1h": 1,
    "4h": 4,
    "1d": 24,
    "1w": 168,
    "1M": 720,
}

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
    track: str = "regime"


@dataclass(frozen=True)
class PipelineRunResult:
    run_time: datetime | None
    regime_bullish: bool
    recommendations: list[RecommendationRecord]


# BR22: 가격 감시 이벤트 이름 -> 컬럼. 이름을 그대로 SQL에 넣지 않기 위한 화이트리스트이기도 하다.
ENTRY_TOUCHED = "entry"
TARGET_HIT = "target"
STOP_HIT = "stop"
_PRICE_EVENT_COLUMNS = {
    ENTRY_TOUCHED: "entry_touched_at",
    TARGET_HIT: "target_hit_at",
    STOP_HIT: "stop_hit_at",
}


@dataclass(frozen=True)
class MonitoredRecommendation:
    """BR22: 아직 종료되지 않은 추천 1건 -- 감시에 필요한 필드만 담는다."""

    run_time: datetime
    market: str
    entry_price: float
    entry_time: datetime
    entry_touched_at: datetime | None
    track: str = "regime"


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
    track TEXT NOT NULL DEFAULT 'regime',
    PRIMARY KEY (run_time, market, track)
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
    # BR22 가격 감시: 각 이벤트가 최초로 발생한 시각. NULL이면 아직 미발생이며, 값이 채워진
    # 뒤에는 다시 알리지 않는다 (5분마다 같은 알림이 반복되는 것을 막는 기록이 곧 상태다).
    ("entry_touched_at", "TEXT"),
    ("target_hit_at", "TEXT"),
    ("stop_hit_at", "TEXT"),
    # BR24/BR25 다중 트랙. 기존 행은 전부 레짐 게이트 트랙이므로 기본값 'regime'이 그대로 맞다.
    ("track", "TEXT NOT NULL DEFAULT 'regime'"),
]

# BR24: PK를 (run_time, market)에서 (run_time, market, track)으로 넓히는 마이그레이션.
# 같은 종목이 같은 회차에 단기·장기 양쪽에 뽑힐 수 있으므로 기존 PK로는 한쪽이 IntegrityError로
# 사라진다. SQLite는 PK를 ALTER로 못 바꾸므로 테이블을 다시 만들고 행을 옮긴다.
_RECOMMENDATIONS_PK_REBUILD = """
CREATE TABLE recommendations_new (
    run_time TEXT NOT NULL,
    market TEXT NOT NULL,
    expected_return REAL NOT NULL,
    n INTEGER NOT NULL,
    hit_count INTEGER NOT NULL,
    target_reached INTEGER,
    realized_return REAL,
    evaluated_at TEXT,
    source TEXT,
    entry_time TEXT,
    entry_price REAL,
    max_drawdown REAL,
    entry_touched_at TEXT,
    target_hit_at TEXT,
    stop_hit_at TEXT,
    track TEXT NOT NULL DEFAULT 'regime',
    PRIMARY KEY (run_time, market, track)
);
"""
_REBUILD_COLUMNS = (
    "run_time, market, expected_return, n, hit_count, target_reached, realized_return, evaluated_at, "
    "source, entry_time, entry_price, max_drawdown, entry_touched_at, target_hit_at, stop_hit_at, track"
)


_RECOMMENDATIONS_SELECT = (
    "SELECT market, expected_return, n, hit_count, target_reached, realized_return, evaluated_at, source, "
    "entry_time, entry_price, max_drawdown, track FROM recommendations"
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
        track,
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
        track=track or "regime",
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
            self._widen_recommendations_primary_key(conn)

    @staticmethod
    def _widen_recommendations_primary_key(conn) -> None:
        """BR24: 이미 배포된 DB의 PK가 (run_time, market)이면 track을 포함하도록 재구성한다.

        재구성이 필요한지 먼저 확인하고 필요할 때만 수행한다 -- 매 기동마다 테이블을 다시 만들면
        불필요한 쓰기가 반복되고 실패 지점만 늘어난다."""
        pk = [row[1] for row in conn.execute("PRAGMA table_info(recommendations)") if row[5]]
        if "track" in pk:
            return
        conn.execute("DROP TABLE IF EXISTS recommendations_new")
        conn.execute(_RECOMMENDATIONS_PK_REBUILD)
        conn.execute(
            f"INSERT INTO recommendations_new ({_REBUILD_COLUMNS}) SELECT {_REBUILD_COLUMNS} FROM recommendations"
        )
        conn.execute("DROP TABLE recommendations")
        conn.execute("ALTER TABLE recommendations_new RENAME TO recommendations")

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
                    getattr(r, "track", "regime"),
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
                    "entry_time, entry_price, max_drawdown, track) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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

    def get_monitorable_recommendations(self, since: datetime) -> list[MonitoredRecommendation]:
        """BR22: `since` 이후에 나온 추천 중 아직 종료되지 않은 것들.

        목표가나 손절가에 이미 닿은 건은 포지션이 끝난 것이므로 제외한다 -- 감시를 계속하면
        같은 종목을 24시간 내내 조회하게 된다. 진입가 정보가 없는 과거 행도 감시 대상이 아니다."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT run_time, market, entry_price, entry_time, entry_touched_at, target_hit_at, stop_hit_at, track
                FROM recommendations
                WHERE run_time >= ? AND entry_price IS NOT NULL AND entry_time IS NOT NULL
                  AND target_hit_at IS NULL AND stop_hit_at IS NULL
                ORDER BY run_time
                """,
                (since.isoformat(),),
            ).fetchall()
        return [
            MonitoredRecommendation(
                run_time=datetime.fromisoformat(run_time),
                market=market,
                entry_price=entry_price,
                entry_time=datetime.fromisoformat(entry_time),
                entry_touched_at=None if entry_touched_at is None else datetime.fromisoformat(entry_touched_at),
                track=track or "regime",
            )
            for run_time, market, entry_price, entry_time, entry_touched_at, _, _, track in rows
        ]

    def mark_price_event(self, run_time: datetime, market: str, event: str, at: datetime) -> None:
        """BR22: 이벤트 발생 시각을 기록한다. 이미 값이 있으면 덮어쓰지 않는다 -- 최초 도달
        시각이어야 의미가 있고, 이 컬럼이 곧 "이미 알림을 보냈다"는 표시이기도 하다."""
        column = _PRICE_EVENT_COLUMNS[event]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE recommendations SET {column} = ? WHERE run_time = ? AND market = ? AND {column} IS NULL",
                (at.isoformat(), run_time.isoformat(), market),
            )

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
