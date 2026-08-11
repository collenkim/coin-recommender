from src.binance_client import BinanceClient
from src.upbit_client import UpbitClient

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


class BinanceMarketSelector:
    def __init__(self, binance_client: BinanceClient, top_n: int = 20):
        self._binance_client = binance_client
        self._top_n = top_n

    def get_candidate_markets(self) -> list[str]:
        tickers = self._binance_client.get_tickers_by_volume()
        candidates = [
            t
            for t in tickers
            if t.market not in _BINANCE_EXCLUDED_MARKETS and not _is_binance_stablecoin_or_leveraged(t.market)
        ]
        candidates.sort(key=lambda t: t.trade_price_24h, reverse=True)
        return [t.market for t in candidates[: self._top_n]]
