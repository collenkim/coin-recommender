from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.premium import (
    MEASURED_NOTE,
    REVERSE_PREMIUM_THRESHOLD,
    Premium,
    fetch_btc_premium,
    fetch_usd_krw,
    is_reverse,
)

UTC = timezone.utc


def _json(payload):
    r = MagicMock()
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


def _responses(fx=1400.0, upbit=140_000_000.0, binance=100_000.0):
    return [
        _json({"rates": {"KRW": fx}}),
        _json([{"trade_price": upbit}]),
        _json({"price": str(binance)}),
    ]


def test_premium_is_computed_against_the_real_usd_krw_rate():
    """업비트 KRW-USDT로 계산하면 USDT 자체의 한국 프리미엄이 상쇄되어 역프가 구조적으로
    작게 나온다 -- 같은 기간 -2% 사건이 713건 vs 0건으로 갈렸다."""
    with patch("src.premium.requests.get", side_effect=_responses(fx=1400.0, upbit=140_000_000, binance=100_000)):
        premium = fetch_btc_premium()
    assert premium is not None
    assert premium.value == 0.0  # 140,000,000 / (100,000 x 1400)
    assert premium.usd_krw == 1400.0


def test_reverse_premium_is_negative():
    with patch("src.premium.requests.get", side_effect=_responses(upbit=135_800_000)):
        premium = fetch_btc_premium()
    assert premium.value < 0
    assert is_reverse(premium)


def test_small_discount_does_not_trigger():
    with patch("src.premium.requests.get", side_effect=_responses(upbit=139_300_000)):
        premium = fetch_btc_premium()
    assert premium.value < 0
    assert not is_reverse(premium)  # -0.5% -> 문턱 미달


def test_threshold_is_inclusive():
    exactly = Premium(value=REVERSE_PREMIUM_THRESHOLD, upbit_krw=1, binance_usdt=1, usd_krw=1)
    assert is_reverse(exactly)


def test_missing_fx_rate_yields_no_premium():
    """환율을 모르면 계산하지 않는다 -- 추정하지 않는다."""
    with patch("src.premium.requests.get", side_effect=RuntimeError("fx down")):
        assert fetch_usd_krw() is None
        assert fetch_btc_premium() is None


def test_none_premium_is_not_reverse():
    assert not is_reverse(None)


def test_measured_note_states_it_is_not_a_buy_signal():
    """실측은 역프가 매수 신호라는 전제와 반대다(이후 24시간 상승확률 36% vs 기저 52%).
    문구가 그 사실을 담고 있어야 한다."""
    assert "매수 신호가 아닙니다" in MEASURED_NOTE
    assert "36%" in MEASURED_NOTE


# --- 상태 전환 알림 (BR35) ---


def test_reverse_premium_alerts_only_on_entry(tmp_path):
    """30분마다 도는데 역프는 몇 시간씩 이어질 수 있다. 유지되는 동안 매번 보내면 알림이 쌓인다."""
    from src.data_store import DataStore
    from src.pipeline import _reverse_premium_to_report

    store = DataStore(str(tmp_path / "p.db"))
    deep = Premium(value=-0.03, upbit_krw=1, binance_usdt=1, usd_krw=1400)

    with patch("src.pipeline.fetch_btc_premium", return_value=deep):
        first = _reverse_premium_to_report(store, datetime.now(UTC))
        second = _reverse_premium_to_report(store, datetime.now(UTC))

    assert first is deep  # 진입 시 1회
    assert second is None  # 유지 중에는 침묵


def test_reverse_premium_alerts_again_after_recovering(tmp_path):
    from src.data_store import DataStore
    from src.pipeline import _reverse_premium_to_report

    store = DataStore(str(tmp_path / "p.db"))
    deep = Premium(value=-0.03, upbit_krw=1, binance_usdt=1, usd_krw=1400)
    normal = Premium(value=0.01, upbit_krw=1, binance_usdt=1, usd_krw=1400)

    with patch("src.pipeline.fetch_btc_premium", return_value=deep):
        assert _reverse_premium_to_report(store, datetime.now(UTC)) is deep
    with patch("src.pipeline.fetch_btc_premium", return_value=normal):
        assert _reverse_premium_to_report(store, datetime.now(UTC)) is None
    with patch("src.pipeline.fetch_btc_premium", return_value=deep):
        assert _reverse_premium_to_report(store, datetime.now(UTC)) is deep  # 재진입 시 다시 알림


def test_premium_failure_does_not_break_the_run(tmp_path):
    from src.data_store import DataStore
    from src.pipeline import _reverse_premium_to_report

    store = DataStore(str(tmp_path / "p.db"))
    with patch("src.pipeline.fetch_btc_premium", return_value=None):
        assert _reverse_premium_to_report(store, datetime.now(UTC)) is None
