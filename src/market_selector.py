from src.upbit_client import UpbitClient

_EXCLUDED_MARKETS = {"KRW-BTC", "KRW-ETH"}


class MarketSelector:
    def __init__(self, upbit_client: UpbitClient, top_n: int = 20):
        self._upbit_client = upbit_client
        self._top_n = top_n

    def get_candidate_markets(self) -> list[str]:
        tickers = self._upbit_client.get_tickers_by_volume()
        candidates = [t for t in tickers if t.market not in _EXCLUDED_MARKETS]
        candidates.sort(key=lambda t: t.trade_price_24h, reverse=True)
        return [t.market for t in candidates[: self._top_n]]
