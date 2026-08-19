from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from src.data_store import TickerInfo
from src.market_selector import BinanceMarketSelector, MarketSelector


def make_ticker(market: str, volume: float) -> TickerInfo:
    return TickerInfo(market=market, trade_price_24h=volume)


def test_excludes_btc_and_eth():
    upbit_client = MagicMock()
    upbit_client.get_tickers_by_volume.return_value = [
        make_ticker("KRW-BTC", 1_000_000),
        make_ticker("KRW-ETH", 900_000),
        make_ticker("KRW-XRP", 500_000),
    ]
    selector = MarketSelector(upbit_client, top_n=20)

    result = selector.get_candidate_markets()

    assert result == ["KRW-XRP"]


def test_returns_top_n_by_volume_descending():
    upbit_client = MagicMock()
    upbit_client.get_tickers_by_volume.return_value = [
        make_ticker("KRW-A", 100),
        make_ticker("KRW-B", 300),
        make_ticker("KRW-C", 200),
    ]
    selector = MarketSelector(upbit_client, top_n=2)

    result = selector.get_candidate_markets()

    assert result == ["KRW-B", "KRW-C"]


def test_returns_empty_list_when_no_tickers():
    upbit_client = MagicMock()
    upbit_client.get_tickers_by_volume.return_value = []
    selector = MarketSelector(upbit_client, top_n=20)

    assert selector.get_candidate_markets() == []


# --- BinanceMarketSelector (BR8) ---

def test_binance_excludes_btc_and_eth():
    binance_client = MagicMock()
    binance_client.get_klines.return_value = []  # 상장일 확인 불가 -> 필터 미적용
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("BTCUSDT", 1_000_000),
        make_ticker("ETHUSDT", 900_000),
        make_ticker("SOLUSDT", 500_000),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=20)

    result = selector.get_candidate_markets()

    assert result == ["SOLUSDT"]


def test_binance_excludes_stablecoin_pairs():
    binance_client = MagicMock()
    binance_client.get_klines.return_value = []  # 상장일 확인 불가 -> 필터 미적용
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("USDCUSDT", 5_000_000),
        make_ticker("FDUSDUSDT", 4_000_000),
        make_ticker("SOLUSDT", 500_000),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=20)

    result = selector.get_candidate_markets()

    assert result == ["SOLUSDT"]


def test_binance_excludes_leveraged_tokens():
    binance_client = MagicMock()
    binance_client.get_klines.return_value = []  # 상장일 확인 불가 -> 필터 미적용
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("BTCUPUSDT", 2_000_000),
        make_ticker("BTCDOWNUSDT", 1_500_000),
        make_ticker("SOLUSDT", 500_000),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=20)

    result = selector.get_candidate_markets()

    assert result == ["SOLUSDT"]


def test_binance_returns_top_n_by_volume_descending():
    binance_client = MagicMock()
    binance_client.get_klines.return_value = []  # 상장일 확인 불가 -> 필터 미적용
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("AUSDT", 100),
        make_ticker("BUSDT", 300),
        make_ticker("CUSDT", 200),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=2)

    result = selector.get_candidate_markets()

    assert result == ["BUSDT", "CUSDT"]


def test_binance_excludes_newer_pegged_assets_seen_in_the_top_20():
    """2026-08-11 실측: 이 4종이 거래대금 상위권을 차지해 후보 슬롯을 낭비하고 있었다."""
    binance_client = MagicMock()
    binance_client.get_klines.return_value = []  # 상장일 확인 불가 -> 필터 미적용
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("USD1USDT", 9_000_000),
        make_ticker("RLUSDUSDT", 8_000_000),
        make_ticker("UUSDT", 7_000_000),
        make_ticker("XUSDUSDT", 6_000_000),
        make_ticker("EURIUSDT", 5_000_000),
        make_ticker("SOLUSDT", 500_000),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=20)

    assert selector.get_candidate_markets() == ["SOLUSDT"]


def test_binance_excludes_gold_backed_tokens():
    """금 토큰은 스테이블이 아니지만 모멘텀 대상이 아니다. 변동성으로는 걸러지지 않아
    (실측상 정상 알트보다 더 움직인 날이 있음) 이름으로 제외한다."""
    binance_client = MagicMock()
    binance_client.get_klines.return_value = []  # 상장일 확인 불가 -> 필터 미적용
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("XAUTUSDT", 3_000_000),
        make_ticker("PAXGUSDT", 2_000_000),
        make_ticker("SOLUSDT", 500_000),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=20)

    assert selector.get_candidate_markets() == ["SOLUSDT"]


def test_binance_keeps_low_volatility_majors():
    """제외 규칙이 이름 기반이라 조용한 날의 메이저를 지우지 않는다는 회귀 방지."""
    binance_client = MagicMock()
    binance_client.get_klines.return_value = []  # 상장일 확인 불가 -> 필터 미적용
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("TRXUSDT", 3_000_000),
        make_ticker("DOGEUSDT", 2_000_000),
        make_ticker("BNBUSDT", 1_000_000),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=20)

    assert selector.get_candidate_markets() == ["TRXUSDT", "DOGEUSDT", "BNBUSDT"]


# --- BR33: 신규 상장 제외 ---

def _listed(days_ago: int):
    from src.data_store import Candle

    t = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return [Candle("X", "1d", t, 1.0, 1.0, 1.0, 1.0, 1.0)]


def test_recently_listed_markets_are_skipped():
    """상장 직후 종목은 표본을 만들 수 없어 추천이 원천 불가한데 슬롯만 차지한다
    (실측: 상위 30 중 7종이 표본 1~4건)."""
    binance_client = MagicMock()
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("NEWUSDT", 900_000),
        make_ticker("SOLUSDT", 500_000),
    ]
    binance_client.get_klines.side_effect = lambda market, *a, **k: (
        _listed(30) if market == "NEWUSDT" else _listed(2000)
    )
    selector = BinanceMarketSelector(binance_client, top_n=20)

    assert selector.get_candidate_markets() == ["SOLUSDT"]


def test_the_slot_freed_by_a_new_listing_is_filled_by_an_older_market():
    """제외로 생긴 자리는 다음 순위가 채운다 -- 후보 수가 줄어들면 안 된다."""
    binance_client = MagicMock()
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("NEWUSDT", 900_000),
        make_ticker("SOLUSDT", 500_000),
        make_ticker("XRPUSDT", 400_000),
    ]
    binance_client.get_klines.side_effect = lambda market, *a, **k: (
        _listed(30) if market == "NEWUSDT" else _listed(2000)
    )
    selector = BinanceMarketSelector(binance_client, top_n=2)

    assert selector.get_candidate_markets() == ["SOLUSDT", "XRPUSDT"]


def test_listing_date_lookup_failure_keeps_the_market():
    """조회 실패로 검증된 종목이 빠지는 쪽이 더 나쁘다."""
    binance_client = MagicMock()
    binance_client.get_tickers_by_volume.return_value = [make_ticker("SOLUSDT", 500_000)]
    binance_client.get_klines.side_effect = RuntimeError("network")
    selector = BinanceMarketSelector(binance_client, top_n=20)

    assert selector.get_candidate_markets() == ["SOLUSDT"]


def test_listing_date_is_cached_so_later_runs_skip_the_lookup(tmp_path):
    """상장일은 바뀌지 않는 값이다 -- 매 실행 후보마다 1요청을 더 쓸 이유가 없다."""
    from src.data_store import DataStore

    store = DataStore(str(tmp_path / "s.db"))
    binance_client = MagicMock()
    binance_client.get_tickers_by_volume.return_value = [make_ticker("SOLUSDT", 500_000)]
    binance_client.get_klines.side_effect = lambda *a, **k: _listed(2000)
    selector = BinanceMarketSelector(binance_client, top_n=20, data_store=store)

    assert selector.get_candidate_markets() == ["SOLUSDT"]
    first_calls = binance_client.get_klines.call_count
    assert selector.get_candidate_markets() == ["SOLUSDT"]
    assert binance_client.get_klines.call_count == first_calls  # 캐시 적중
