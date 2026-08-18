from datetime import datetime, timedelta, timezone

import pytest

from src.data_store import Candle
from src.market_phase import (
    BULL,
    MOMENTUM_HORIZONS,
    MOMENTUM_WARMUP_BARS,
    NOT_BULL,
    STRONG_BULL,
    WEAK_BULL,
    AssetMomentum,
    classify,
    classify_asset,
    combine,
    current_phase,
    momentum_returns,
)

_START = datetime(2021, 1, 1, tzinfo=timezone.utc)


def _candles(closes: list[float], market: str = "BTCUSDT") -> list[Candle]:
    return [
        Candle(
            market=market,
            timeframe="4h",
            candle_time=_START + timedelta(hours=4 * i),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1.0,
        )
        for i, close in enumerate(closes)
    ]


def _returns(**overrides: float) -> dict[str, float]:
    base = {key: 0.0 for key in MOMENTUM_HORIZONS}
    base.update(overrides)
    return base


# --- classify: 문턱 자체 ---


def test_strong_requires_30d_above_threshold_and_long_horizons_positive():
    assert classify(_returns(**{"1d": 0.01, "7d": 0.05, "30d": 0.25, "90d": 0.1, "365d": 0.5})) == STRONG_BULL


def test_strong_rejected_when_long_term_is_negative():
    """단기 급등만으로 강상승이라 부르지 않는다 -- 90일/365일이 음수면 추세와 반대 방향이다."""
    spike = _returns(**{"1d": 0.05, "7d": 0.2, "30d": 0.3, "90d": -0.1, "365d": 0.5})
    assert classify(spike) == WEAK_BULL
    spike_year_down = _returns(**{"1d": 0.05, "7d": 0.2, "30d": 0.3, "90d": 0.1, "365d": -0.2})
    assert classify(spike_year_down) == WEAK_BULL


def test_strong_threshold_is_exclusive():
    assert classify(_returns(**{"30d": 0.20, "90d": 0.1, "365d": 0.1, "1d": 0.01, "7d": 0.01})) == WEAK_BULL
    assert classify(_returns(**{"30d": 0.2001, "90d": 0.1, "365d": 0.1, "1d": 0.01, "7d": 0.01})) == STRONG_BULL


def test_weak_needs_positive_30d_and_majority_of_horizons():
    assert classify(_returns(**{"1d": 0.01, "7d": 0.01, "30d": 0.05, "90d": -0.2, "365d": -0.3})) == WEAK_BULL
    # 30일이 양수여도 과반이 음수면 약상승이 아니다 (양수 2개)
    assert classify(_returns(**{"1d": -0.01, "7d": -0.02, "30d": 0.05, "90d": -0.2, "365d": 0.3})) == NOT_BULL


def test_not_bull_when_30d_is_negative_even_if_long_term_is_up():
    assert classify(_returns(**{"1d": 0.01, "7d": 0.02, "30d": -0.01, "90d": 0.5, "365d": 1.0})) == NOT_BULL


# --- momentum_returns: 워밍업과 구간 계산 ---


def test_momentum_returns_none_without_full_year_of_history():
    closes = [100.0] * MOMENTUM_WARMUP_BARS
    assert momentum_returns(closes, len(closes) - 1) is None


def test_momentum_returns_computes_each_horizon_from_its_own_offset():
    closes = [100.0] * (MOMENTUM_WARMUP_BARS + 1)
    i = len(closes) - 1
    closes[i] = 110.0
    returns = momentum_returns(closes, i)
    assert returns is not None
    for key, bars in MOMENTUM_HORIZONS.items():
        assert returns[key] == pytest.approx(110.0 / closes[i - bars] - 1)


def test_classify_asset_returns_none_on_short_history():
    assert classify_asset(_candles([100.0] * 10), "BTCUSDT") is None
    assert classify_asset([], "BTCUSDT") is None


def test_classify_asset_uses_the_latest_closed_bar():
    closes = [100.0] * MOMENTUM_WARMUP_BARS + [130.0]
    asset = classify_asset(_candles(closes), "BTCUSDT")
    assert asset is not None
    assert asset.label == STRONG_BULL
    assert asset.returns["30d"] == pytest.approx(0.30)


# --- combine: BTC/ETH 합의 규칙 ---


def _asset(market: str, label: str) -> AssetMomentum:
    return AssetMomentum(market=market, label=label, returns=_returns())


@pytest.mark.parametrize(
    "btc,eth,expected",
    [
        (STRONG_BULL, STRONG_BULL, STRONG_BULL),
        (STRONG_BULL, WEAK_BULL, BULL),
        (STRONG_BULL, NOT_BULL, WEAK_BULL),
        (WEAK_BULL, WEAK_BULL, BULL),
        (WEAK_BULL, NOT_BULL, WEAK_BULL),
        (NOT_BULL, NOT_BULL, NOT_BULL),
    ],
)
def test_combine_grades_by_how_much_the_two_assets_agree(btc, eth, expected):
    """BR25: 약상승장이 독립 등급이 되면서 '하나만 상승'을 상승장 아님으로 묶지 않는다."""
    assert combine([_asset("BTCUSDT", btc), _asset("ETHUSDT", eth)]) == expected


def test_current_phase_skips_assets_without_enough_history():
    """ETH 수집이 아직 얕아도 BTC만으로 판정한다 -- 문구가 통째로 사라지는 것보다 낫다."""
    strong = [100.0] * MOMENTUM_WARMUP_BARS + [130.0]
    phase = current_phase({"BTCUSDT": _candles(strong), "ETHUSDT": _candles([100.0] * 5, "ETHUSDT")})
    assert phase is not None
    assert [a.market for a in phase.assets] == ["BTCUSDT"]
    assert phase.phase == STRONG_BULL


def test_current_phase_is_none_when_nothing_can_be_judged():
    assert current_phase({"BTCUSDT": [], "ETHUSDT": []}) is None
