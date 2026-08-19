import logging
from datetime import datetime, timedelta, timezone

from src.binance_client import BinanceClient
from src.upbit_client import UpbitClient

logger = logging.getLogger(__name__)

# 바이낸스 개장(2017-07)보다 이르면 충분하다.
_EXCHANGE_EPOCH = datetime(2017, 1, 1, tzinfo=timezone.utc)

_EXCLUDED_MARKETS = {"KRW-BTC", "KRW-ETH"}

_BINANCE_EXCLUDED_MARKETS = {"BTCUSDT", "ETHUSDT"}
_BINANCE_STABLECOIN_BASES = {
    "USDC", "FDUSD", "TUSD", "DAI", "USDP", "BUSD", "PAX", "USTC", "PYUSD", "GUSD", "SUSD", "EUR", "GBP", "TRY", "BRL",
    # 2026-08-11 추가: 실측상 거래대금 상위권에 올라와 후보 슬롯을 차지하고 있었음.
    # 전부 현재가 ~1.00에 24시간 변동폭 0.02~0.29%로 페그가 확인됨.
    "USD1", "RLUSD", "U", "XUSD", "EURI",
}
# 금 현물 연동 토큰. 스테이블은 아니지만 모멘텀 전략의 대상이 아니다.
_BINANCE_COMMODITY_BASES = {"XAUT", "PAXG"}
_BINANCE_LEVERAGE_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")


class MarketSelector:
    def __init__(self, upbit_client: UpbitClient, top_n: int = 20):
        self._upbit_client = upbit_client
        self._top_n = top_n

    def get_candidate_markets(self) -> list[str]:
        tickers = self._upbit_client.get_tickers_by_volume()
        candidates = [t for t in tickers if t.market not in _EXCLUDED_MARKETS]
        candidates.sort(key=lambda t: t.trade_price_24h, reverse=True)
        return [t.market for t in candidates[: self._top_n]]


def _is_binance_stablecoin_or_leveraged(symbol: str) -> bool:
    """BR8: filters out pairs that are noise for a momentum strategy -- stablecoin pairs (no real
    price movement), 금 연동 토큰, and leveraged/inverse tokens (3x BULL/BEAR-style products).

    이름 목록으로 거르는 이유(2026-08-11 실측): 24시간 변동폭 하한으로 자동 배제하려 했으나
    금 토큰(XAUT 2.53%, PAXG 2.65%)이 같은 날 정상 알트(TRX 0.63%, DOGE 1.38%, BNB 1.55%,
    SOL 2.30%)보다 더 크게 움직였다. 금이 걸리는 임계값은 메이저 알트를 함께 지운다 --
    변동성만으로는 분리할 수 없어 명시 목록을 유지한다. 대신 신규 페그 자산이 상위권에
    올라오면 목록에 추가해야 한다."""
    base = symbol.removesuffix("USDT")
    return (
        base in _BINANCE_STABLECOIN_BASES
        or base in _BINANCE_COMMODITY_BASES
        or base.endswith(_BINANCE_LEVERAGE_SUFFIXES)
    )


# BR33: 후보로 삼을 최소 상장 경과일. 거래량 상위권에는 상장 직후 종목이 자주 올라오는데,
# 이력이 없어 표본을 만들 수 없으므로 추천이 원천 불가하면서 슬롯만 차지한다.
#
# 2026-08-19 실측: 상위 30 중 7종(SNDKB/SPCXB/SNXXB/SKHYB/KORUB/SOXLB/MUB)이 상장 0.1~0.2년으로
# 트랙 표본이 1~4건이었다(하한 10건). 제외하면 LTC/UNI/AAVE/XLM/TAO 등 검증된 종목이 들어온다.
#
# 6개월로 잡은 근거: 가장 짧은 트랙(단타)이 표본 하한 10건을 채우려면 진입 기회가 그만큼 필요한데,
# 실측상 종목당 골든크로스가 연 41회이므로 6개월이면 약 20회가 쌓인다.
MIN_LISTING_DAYS = 180

# 상장일 확인을 위해 훑을 최대 범위. 거래량 상위 이만큼만 보고 그중 조건을 만족하는 순서대로
# top_n을 채운다 -- 전체 USDT 페어(약 500종)를 매번 확인하면 요청이 폭증한다.
_MAX_SCAN = 60


class BinanceMarketSelector:
    def __init__(
        self,
        binance_client: BinanceClient,
        top_n: int = 20,
        data_store=None,
        min_listing_days: int = MIN_LISTING_DAYS,
    ):
        self._binance_client = binance_client
        self._top_n = top_n
        # 상장일은 바뀌지 않는 값이라 BR28의 `collection_state` 캐시를 그대로 쓴다. 없으면 조회 1회.
        self._data_store = data_store
        self._min_listing_days = min_listing_days

    def _listed_at(self, market: str) -> datetime | None:
        """거래소의 가장 오래된 일봉 시각. 확인 불가면 None (그 경우 후보에서 제외하지 않는다)."""
        if self._data_store is not None:
            cached = self._data_store.get_exchange_earliest("binance", market, "1d")
            if cached is not None:
                return cached
        try:
            first = self._binance_client.get_klines(market, "1d", start_time=_EXCHANGE_EPOCH, limit=1)
        except Exception:
            logger.warning("Failed to check listing date for %s; keeping it as a candidate", market, exc_info=True)
            return None
        if not first:
            return None
        if self._data_store is not None:
            self._data_store.set_exchange_earliest(
                "binance", market, "1d", first[0].candle_time, datetime.now(timezone.utc)
            )
        return first[0].candle_time

    def get_candidate_markets(self) -> list[str]:
        tickers = self._binance_client.get_tickers_by_volume()
        candidates = [
            t
            for t in tickers
            if t.market not in _BINANCE_EXCLUDED_MARKETS and not _is_binance_stablecoin_or_leveraged(t.market)
        ]
        candidates.sort(key=lambda t: t.trade_price_24h, reverse=True)

        cutoff = datetime.now(timezone.utc) - timedelta(days=self._min_listing_days)
        selected: list[str] = []
        for ticker in candidates[:_MAX_SCAN]:
            listed_at = self._listed_at(ticker.market)
            # 확인 실패는 통과시킨다 -- 조회 실패로 검증된 종목이 빠지는 쪽이 더 나쁘다.
            if listed_at is not None and listed_at > cutoff:
                continue
            selected.append(ticker.market)
            if len(selected) >= self._top_n:
                break
        return selected
