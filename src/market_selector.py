from src.binance_client import BinanceClient
from src.upbit_client import UpbitClient

_EXCLUDED_MARKETS = {"KRW-BTC", "KRW-ETH"}

_BINANCE_EXCLUDED_MARKETS = {"BTCUSDT", "ETHUSDT"}
_BINANCE_STABLECOIN_BASES = {
    "USDC", "FDUSD", "TUSD", "DAI", "USDP", "BUSD", "PAX", "USTC", "PYUSD", "GUSD", "SUSD", "EUR", "GBP", "TRY", "BRL",
}
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
    """BR8: filters out pairs that are noise for a momentum strategy -- stablecoin-vs-stablecoin
    pairs (no real price movement) and leveraged/inverse tokens (3x BULL/BEAR-style products)."""
    base = symbol.removesuffix("USDT")
    return base in _BINANCE_STABLECOIN_BASES or base.endswith(_BINANCE_LEVERAGE_SUFFIXES)


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
