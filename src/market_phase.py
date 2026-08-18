"""BR23: BTC/ETH 상승 모멘텀 국면 판정 — **표시 전용**.

여기서 나온 판정은 추천을 낼지 말지에 **관여하지 않는다**. 진입 게이트는 `backtest.build_regime_series`
(BTC 4시간봉 30일 수익률 단독)가 계속 담당하며, 발표하는 적중률은 그 게이트가 켜진 구간에서 측정된
값이다. 이 모듈이 게이트를 건드리면 그 수치들이 측정된 조건과 어긋난다.

두 개를 별도 모듈로 분리한 이유가 그것이다 -- 같은 파일에 두면 `STRONG_BULL` 이름이 겹치고,
표시용 판정이 매매 경로로 새어 들어가기 쉽다.

5년 실측(2021-01~2026-08, BTC/ETH 4시간봉 각 12,245봉) 요약:
- 판정 빈도: 강상승장 4% / 약상승장 46% / 상승장 아님 50%
- 그 시점 BTC 30일 수익률 중앙값: +36.0% / +8.1% / -7.4% (현재 상태는 뚜렷이 분리된다)
- 강상승장 416봉은 **전부** 기존 게이트의 `strong_bull` 구간 안에 있었다 -- 문구와 게이트가 서로
  모순되는 경우는 관측되지 않았다.
- 예측력은 주장하지 않는다: 강상승장 15개 에피소드 중 이후 30일 양수는 9개(60%)이고 그중 6개가
  2024-11 한 달에 몰려 있다. BR20-c 기준 ③④에 걸려 "이후에 오른다"고 말할 근거가 못 된다.
  문구는 **지금 상태의 설명**이지 전망이 아니다.
"""

from dataclasses import dataclass

from src.data_store import Candle

# 4시간봉 기준 구간 길이. 사용자 요청("일 주 30일, 월, 년 데이터 전체")에 따라 5구간을 쓴다.
# "월"은 30일과 겹치지 않도록 90일(3개월)로 두었다 -- 30일이 이미 한 달을 담당한다.
MOMENTUM_HORIZONS = {
    "1d": 6,
    "7d": 42,
    "30d": 180,
    "90d": 540,
    "365d": 2190,
}
# 가장 긴 구간. 이만큼의 이력이 없으면 그 자산은 판정하지 않는다(추정하지 않는다).
MOMENTUM_WARMUP_BARS = max(MOMENTUM_HORIZONS.values())

# 강상승 문턱. 기존 게이트의 STRONG_BULL_30D와 같은 값이지만 상수를 따로 둔다 --
# 표시용 문구를 조정하려다 매매 게이트가 함께 움직이면 안 된다.
STRONG_30D = 0.20
# 강상승은 단기 급등만으로 인정하지 않는다. 90일·365일이 함께 양수여야 "장기 추세와 같은 방향"이다.
# 약상승은 30일이 양수이면서 5구간 중 과반이 양수인 경우.
WEAK_MIN_POSITIVE = 3

STRONG_BULL = "strong_bull"
WEAK_BULL = "weak_bull"
NOT_BULL = "not_bull"


@dataclass(frozen=True)
class AssetMomentum:
    market: str
    label: str  # STRONG_BULL | WEAK_BULL | NOT_BULL
    returns: dict[str, float]  # 구간 이름 -> 수익률


@dataclass(frozen=True)
class MarketPhase:
    phase: str  # STRONG_BULL | WEAK_BULL | NOT_BULL
    assets: list[AssetMomentum]


def momentum_returns(closes: list[float], i: int) -> dict[str, float] | None:
    """`i`번째 봉 기준 5구간 수익률. 가장 긴 구간을 채울 이력이 없으면 None."""
    if i < MOMENTUM_WARMUP_BARS:
        return None
    return {name: closes[i] / closes[i - bars] - 1 for name, bars in MOMENTUM_HORIZONS.items()}


def classify(returns: dict[str, float]) -> str:
    """BR23: 5구간 수익률 -> 강상승 / 약상승 / 비상승."""
    if returns["30d"] > STRONG_30D and returns["90d"] > 0 and returns["365d"] > 0:
        return STRONG_BULL
    positive = sum(1 for value in returns.values() if value > 0)
    if returns["30d"] > 0 and positive >= WEAK_MIN_POSITIVE:
        return WEAK_BULL
    return NOT_BULL


def classify_asset(candles: list[Candle], market: str) -> AssetMomentum | None:
    """가장 최근 마감봉 기준 판정. 이력이 모자라면 None -- 짧은 이력으로 365일 모멘텀을
    추정하지 않는다."""
    if not candles:
        return None
    closes = [c.close for c in candles]
    returns = momentum_returns(closes, len(closes) - 1)
    if returns is None:
        return None
    return AssetMomentum(market=market, label=classify(returns), returns=returns)


def combine(assets: list[AssetMomentum]) -> str:
    """BR23: 강상승장은 둘 다 강상승, 약상승장은 둘 다 상승(약 이상). 하나라도 비상승이면 상승장이 아니다.

    사용자 요청이 "BTC, ETH 강세장일 경우"였으므로 두 자산의 합의를 요구한다 -- 알트는 BTC/ETH에
    끌려다니므로 둘 중 하나만 오른 국면을 '상승장'이라 부르면 과장이 된다.

    실측에서 실제로 걸린 문제라 규칙을 조인다: 2026-08-18 라이브 데이터가 BTC 비상승(365일 -45.0%,
    90일 -16.0%) + ETH 약상승이었는데, 느슨한 규칙("하나라도 상승이면 약상승장")은 이걸 '약상승장'으로
    표시했다. 헤드라인이 본문의 두 줄과 정면으로 어긋난다."""
    labels = [a.label for a in assets]
    if all(label == STRONG_BULL for label in labels):
        return STRONG_BULL
    if all(label != NOT_BULL for label in labels):
        return WEAK_BULL
    return NOT_BULL


def current_phase(candles_by_market: dict[str, list[Candle]]) -> MarketPhase | None:
    """판정 가능한 자산만 모아 종합한다. 하나도 판정할 수 없으면 None (문구를 생략한다)."""
    assets = [
        asset
        for market, candles in candles_by_market.items()
        if (asset := classify_asset(candles, market)) is not None
    ]
    if not assets:
        return None
    return MarketPhase(phase=combine(assets), assets=assets)
