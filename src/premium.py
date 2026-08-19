"""BR35: 역프(한국 가격이 해외보다 쌀 때) 알림 — **매수 신호가 아니다.**

사용자가 "역프 -2% 이하는 무조건 매수시점"이라고 보았으나, 8.9년 실측은 **반대**를 가리킨다:

| 문턱 | 사건 | 이후 8h | 이후 24h | 이후 48h |
|---|---|---|---|---|
| -1% | 270 | +0.02% / 47% | +0.20% / 50% | +0.45% / 56% |
| **-2%** | 106 | **-0.20% / 44%** | **-0.50% / 36%** | **-0.31% / 48%** |
| -3% | 37 | -0.12% / 41% | -0.43% / 38% | -0.63% / 49% |
| (무조건부 기저) | 19,476 | +0.05% / 52% | +0.15% / 52% | **+0.29% / 52%** |

특히 이후 24시간 상승확률이 36%로 기저 52%를 크게 밑돈다. 역프는 **한국 시장이 먼저 팔린 결과**라
하락의 중간이지 끝이 아니다. 시기별 재현성도 없다(2018년 -4.08% vs 2021년 +4.20%).

그래서 이 모듈은 **사실만 알리고 매수 판단을 표시하지 않는다.** 알림 문구에 위 통계를 함께 적어
잘못된 확신을 주지 않는다.

측정 방법 주의: 프리미엄은 **USD/KRW 실환율** 기준이다. 업비트 KRW-USDT로 계산하면 USDT 자체의
한국 프리미엄이 상쇄되어 역프가 구조적으로 작게 나온다(같은 기간 -2% 사건이 713건 vs 0건).
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

# 이 값 이하이면 알린다. 사용자 지정(-2%).
REVERSE_PREMIUM_THRESHOLD = -0.02

_FX_URL = "https://api.frankfurter.app/latest"
_UPBIT_TICKER_URL = "https://api.upbit.com/v1/ticker"
_BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"

_UPBIT_MARKET = "KRW-BTC"
_BINANCE_SYMBOL = "BTCUSDT"

# 실측 근거. 알림에 함께 실어 "드문 이벤트"와 "매수 신호"를 혼동하지 않게 한다.
MEASURED_NOTE = "과거 106건 기준 이후 24시간 상승확률 36% (무조건부 52%) — 매수 신호가 아닙니다"


@dataclass(frozen=True)
class Premium:
    value: float  # 프리미엄 (음수면 역프)
    upbit_krw: float
    binance_usdt: float
    usd_krw: float


def _get_json(url: str, params: dict | None, timeout: float):
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_usd_krw(timeout_seconds: float = 10.0) -> float | None:
    """USD/KRW 실환율. 실패하면 None -- 환율을 모르면 프리미엄을 계산하지 않는다(추정하지 않는다)."""
    try:
        data = _get_json(_FX_URL, {"from": "USD", "to": "KRW"}, timeout_seconds)
        return float(data["rates"]["KRW"])
    except Exception:
        logger.warning("Failed to fetch USD/KRW rate; skipping premium check", exc_info=True)
        return None


def fetch_btc_premium(timeout_seconds: float = 10.0) -> Premium | None:
    """BTC의 한국-해외 가격차. 어느 한쪽이라도 못 받으면 None."""
    usd_krw = fetch_usd_krw(timeout_seconds)
    if usd_krw is None or usd_krw <= 0:
        return None
    try:
        upbit = _get_json(_UPBIT_TICKER_URL, {"markets": _UPBIT_MARKET}, timeout_seconds)
        binance = _get_json(_BINANCE_PRICE_URL, {"symbol": _BINANCE_SYMBOL}, timeout_seconds)
    except Exception:
        logger.warning("Failed to fetch BTC prices for premium check", exc_info=True)
        return None
    if not upbit:
        return None
    upbit_krw = float(upbit[0]["trade_price"])
    binance_usdt = float(binance["price"])
    converted = binance_usdt * usd_krw
    if converted <= 0:
        return None
    return Premium(
        value=upbit_krw / converted - 1,
        upbit_krw=upbit_krw,
        binance_usdt=binance_usdt,
        usd_krw=usd_krw,
    )


def is_reverse(premium: Premium | None) -> bool:
    return premium is not None and premium.value <= REVERSE_PREMIUM_THRESHOLD
