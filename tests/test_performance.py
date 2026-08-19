from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.data_store import STOP_HIT, TARGET_HIT, DataStore

UTC = timezone.utc
RUN = datetime(2026, 8, 20, tzinfo=UTC)


class Rec:
    def __init__(self, market="SOLUSDT", track="day", entry_time=RUN):
        self.market = market
        self.track = track
        self.entry_time = entry_time
        self.expected_return = 0.01
        self.n = 100
        self.hit_count = 30
        self.source = "binance"
        self.entry_price = 100.0
        self.max_drawdown = -0.01


def test_no_resolved_recommendations_yields_empty_totals(tmp_path):
    store = DataStore(str(tmp_path / "p.db"))
    store.save_run(RUN, True, [Rec()])
    assert store.get_live_performance()["total"] == {"resolved": 0, "hit": 0}


def test_only_resolved_recommendations_are_counted(tmp_path):
    """진행 중인 건을 넣으면 BR24에서 겪은 '미완료 매매를 타임아웃으로 집계' 결함이 반복된다."""
    store = DataStore(str(tmp_path / "p.db"))
    store.save_run(RUN, True, [Rec(market="AAAUSDT"), Rec(market="BBBUSDT")])
    store.mark_price_event(RUN, "AAAUSDT", TARGET_HIT, RUN, "day")

    perf = store.get_live_performance()
    assert perf["total"] == {"resolved": 1, "hit": 1}  # BBB는 미결이라 제외


def test_stop_hit_counts_as_resolved_but_not_a_hit(tmp_path):
    store = DataStore(str(tmp_path / "p.db"))
    store.save_run(RUN, True, [Rec()])
    store.mark_price_event(RUN, "SOLUSDT", STOP_HIT, RUN, "day")

    assert store.get_live_performance()["total"] == {"resolved": 1, "hit": 0}


def test_repeated_saves_of_the_same_entry_count_once(tmp_path):
    """파이프라인이 30분마다 돌면서 같은 4시간봉 진입을 반복 저장한 이력이 있다
    (실측: 원시 118행 = 고유 진입 17건). 중복을 세면 회전이 빠른 종목이 통계를 지배한다."""
    store = DataStore(str(tmp_path / "p.db"))
    for offset in (0, 30, 60):
        run = RUN + timedelta(minutes=offset)
        store.save_run(run, True, [Rec(entry_time=RUN)])  # 진입봉은 동일
        store.mark_price_event(run, "SOLUSDT", TARGET_HIT, run, "day")

    perf = store.get_live_performance()
    assert perf["total"]["resolved"] == 1


def test_tracks_are_reported_separately(tmp_path):
    store = DataStore(str(tmp_path / "p.db"))
    store.save_run(RUN, True, [Rec(track="day"), Rec(track="long")])
    store.mark_price_event(RUN, "SOLUSDT", TARGET_HIT, RUN, "day")
    store.mark_price_event(RUN, "SOLUSDT", STOP_HIT, RUN, "long")

    by = store.get_live_performance()["by_track"]
    assert by["day"] == {"resolved": 1, "hit": 1}
    assert by["long"] == {"resolved": 1, "hit": 0}


# --- 알림 표기 ---


def test_small_sample_is_flagged_as_too_early():
    """트랙 실측 도달률이 21~36%인데 표본 20건이면 우연히 88%가 나올 수 있다
    -- 실제로 첫날 17건에서 88%가 나왔다."""
    from src.notifier import _performance_lines

    lines = _performance_lines({"total": {"resolved": 17, "hit": 15}, "by_track": {}})
    assert "88%" in lines[0]
    assert "아직 판단하기 이릅니다" in lines[0]


def test_large_sample_drops_the_caveat():
    from src.notifier import _performance_lines

    lines = _performance_lines({"total": {"resolved": 135, "hit": 41}, "by_track": {}})
    assert "30%" in lines[0]
    assert "아직 판단하기" not in lines[0]


def test_no_results_yet_is_stated_plainly():
    from src.notifier import _performance_lines

    lines = _performance_lines({"total": {"resolved": 0, "hit": 0}, "by_track": {}})
    assert lines == ["[실적] 아직 결과가 확정된 추천이 없습니다"]


def test_performance_block_is_omitted_when_unavailable():
    from src.notifier import _performance_lines

    assert _performance_lines(None) == []


def test_duplicate_entries_cannot_be_stored_twice(tmp_path):
    """BR37: (종목, 트랙, 진입봉)이 하나의 추천이다. 애플리케이션 중복 제거가 실패해도
    DB 레벨에서 막힌다 -- INSERT OR IGNORE라 예외가 아니라 조용히 무시된다."""
    store = DataStore(str(tmp_path / "u.db"))
    store.save_run(RUN, True, [Rec(entry_time=RUN)])
    store.save_run(RUN + timedelta(minutes=30), True, [Rec(entry_time=RUN)])

    import sqlite3

    with sqlite3.connect(str(tmp_path / "u.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 1
