from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests

from src.notifier import send_notification

UTC = timezone.utc
RUN_TIME = datetime(2024, 1, 1, tzinfo=UTC)


class FakeRecommendation:
    def __init__(self, market, expected_return, n, hit_count, source="upbit",
                 entry_time=None, entry_price=None, max_drawdown=None):
        self.market = market
        self.expected_return = expected_return
        self.n = n
        self.hit_count = hit_count
        self.source = source
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.max_drawdown = max_drawdown


def ok_response():
    r = MagicMock()
    r.raise_for_status.return_value = None
    return r


def test_sends_to_no_channel_when_none_configured():
    with patch("src.notifier.requests.post") as mock_post:
        send_notification([], RUN_TIME, None, None, None)
    mock_post.assert_not_called()


def test_sends_to_telegram_only_when_only_telegram_configured():
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification([], RUN_TIME, "TOKEN123", "CHAT456", None)

    mock_post.assert_called_once()
    url = mock_post.call_args.args[0]
    assert url == "https://api.telegram.org/botTOKEN123/sendMessage"
    assert mock_post.call_args.kwargs["json"]["chat_id"] == "CHAT456"


def test_sends_to_discord_only_when_only_discord_configured():
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification([], RUN_TIME, None, None, "https://discord.example/webhook")

    mock_post.assert_called_once()
    assert mock_post.call_args.args[0] == "https://discord.example/webhook"
    assert "content" in mock_post.call_args.kwargs["json"]


def test_sends_to_both_channels_when_both_configured():
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification([], RUN_TIME, "TOKEN123", "CHAT456", "https://discord.example/webhook")

    assert mock_post.call_count == 2


def test_telegram_failure_does_not_prevent_discord_send():
    telegram_error = requests.RequestException("boom")
    with patch("src.notifier.requests.post", side_effect=[telegram_error, ok_response()]) as mock_post:
        send_notification([], RUN_TIME, "TOKEN123", "CHAT456", "https://discord.example/webhook")

    assert mock_post.call_count == 2  # both attempted despite telegram failing


def test_sends_to_slack_only_when_only_slack_configured():
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification([], RUN_TIME, None, None, None, "https://hooks.slack.com/services/T/B/X")

    mock_post.assert_called_once()
    assert mock_post.call_args.args[0] == "https://hooks.slack.com/services/T/B/X"
    # Slack은 Discord의 `content`가 아니라 `text` 키를 쓴다
    assert list(mock_post.call_args.kwargs["json"]) == ["text"]


def test_sends_to_all_three_channels_when_all_configured():
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification(
            [], RUN_TIME, "TOKEN123", "CHAT456", "https://discord.example/webhook", "https://hooks.slack.com/services/T/B/X"
        )

    assert mock_post.call_count == 3


def test_discord_failure_does_not_prevent_slack_send():
    with patch("src.notifier.requests.post", side_effect=[requests.RequestException("boom"), ok_response()]) as mock_post:
        send_notification([], RUN_TIME, None, None, "https://discord.example/webhook", "https://hooks.slack.com/services/T/B/X")

    assert mock_post.call_count == 2  # 한 채널이 죽어도 나머지는 계속 시도한다
    assert mock_post.call_args_list[-1].args[0] == "https://hooks.slack.com/services/T/B/X"


def test_slack_failure_does_not_raise():
    """알림은 best-effort -- 실패해도 파이프라인 실행 자체는 성공으로 취급한다 (BR3)."""
    with patch("src.notifier.requests.post", side_effect=requests.RequestException("boom")):
        send_notification([], RUN_TIME, None, None, None, "https://hooks.slack.com/services/T/B/X")


def test_slack_message_body_matches_the_other_channels():
    recs = [FakeRecommendation("SOLUSDT", 0.01, 5, 3, source="binance")]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification(recs, RUN_TIME, None, None, "https://discord.example/webhook", "https://hooks.slack.com/services/T/B/X")

    discord_body = mock_post.call_args_list[0].kwargs["json"]["content"]
    slack_body = mock_post.call_args_list[1].kwargs["json"]["text"]
    assert discord_body == slack_body


def test_telegram_partial_config_does_not_send():
    with patch("src.notifier.requests.post") as mock_post:
        send_notification([], RUN_TIME, "TOKEN123", None, None)  # missing chat_id
    mock_post.assert_not_called()


def test_message_format_with_recommendations():
    recs = [FakeRecommendation("KRW-XRP", 0.051, 3, 2)]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification(recs, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "KRW-XRP" in message
    assert "67%" in message  # 3회 중 2회 = 목표 도달 확률
    assert "과거 3회 중 2회" in message


def test_message_format_includes_exchange_source():
    recs = [
        FakeRecommendation("KRW-XRP", 0.051, 3, 2, source="upbit"),
        FakeRecommendation("SOLUSDT", 0.07, 2, 1, source="binance"),
    ]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification(recs, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "(1) KRW-XRP · upbit" in message
    assert "(2) SOLUSDT · binance" in message


def test_message_includes_entry_guide():
    entry_time = datetime(2026, 8, 10, 7, tzinfo=UTC)
    recs = [
        FakeRecommendation("BANKUSDT", 0.086, 7, 3, source="binance",
                           entry_time=entry_time, entry_price=100.0, max_drawdown=-0.062)
    ]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification(recs, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "진입가: 100" in message
    assert "매도가: 103" in message  # +3%
    assert "손절가: 98" in message  # -2%
    # 알림은 KST 표기 (진입 07:00 UTC = 16:00 KST), 청산 기한은 진입 +24h
    assert "08-10 16:00 KST" in message
    assert "08-11 16:00 KST" in message


def test_message_omits_entry_guide_when_entry_data_missing():
    """Legacy rows stored before the entry guide existed must not crash or fabricate values."""
    recs = [FakeRecommendation("KRW-XRP", 0.051, 3, 2)]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification(recs, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "KRW-XRP" in message
    assert "진입" not in message


def test_message_format_with_no_recommendations():
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification([], RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    # BR36: 추천이 없으면 섹션을 통째로 뺀다 -- 대부분의 회차가 0건이라 빈 제목만 남았었다.
    for label in ("[단타]", "[중기]", "[장기]", "[기존]"):
        assert label not in message
    assert "추천 코인 0개" in message


def test_header_reports_the_recommendation_count_and_kst_run_time():
    recs = [
        FakeRecommendation("AAAUSDT", 0.01, 5, 3, source="binance"),
        FakeRecommendation("BBBUSDT", 0.01, 5, 3, source="binance"),
    ]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification(recs, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert message.startswith("[coin-recommender] 추천 코인 2개")
    assert "2024-01-01 09:00 KST" in message  # RUN_TIME 00:00 UTC = 09:00 KST
    assert "UTC" not in message


def test_each_recommendation_is_its_own_numbered_paragraph():
    recs = [FakeRecommendation(f"SYM{i}USDT", 0.01, 5, 3, source="binance") for i in range(3)]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification(recs, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    short_body = message.split("[기존]", 1)[1]
    blocks = [b for b in short_body.split("\n\n") if b.strip().startswith("(")]
    assert len(blocks) == 3  # 종목마다 빈 줄로 분리된 한 단락
    for order in (1, 2, 3):
        assert f"({order}) SYM{order - 1}USDT" in message


def test_zero_recommendations_still_reports_a_count():
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification([], RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "추천 코인 0개" in message
    assert "[단타]" not in message  # BR36: 빈 섹션 제거


# --- 가격 도달 알림 (BR22) ---

class FakePriceEvent:
    def __init__(self, market, kind, price, at):
        self.market, self.kind, self.price, self.at = market, kind, price, at


def test_price_alert_is_not_sent_when_nothing_happened():
    """5분마다 '변화 없음'을 보내면 하루 288통이 된다."""
    from src.notifier import send_price_alert

    with patch("src.notifier.requests.post") as mock_post:
        send_price_alert([], RUN_TIME, None, None, "https://discord.example/webhook")
    mock_post.assert_not_called()


def test_price_alert_lists_each_event_as_a_numbered_paragraph():
    from src.data_store import ENTRY_TOUCHED, STOP_HIT, TARGET_HIT
    from src.notifier import send_price_alert

    at = datetime(2026, 8, 11, 6, 32, tzinfo=UTC)
    events = [
        FakePriceEvent("SOLUSDT", TARGET_HIT, 103.0, at),
        FakePriceEvent("ADAUSDT", STOP_HIT, 98.0, at),
        FakePriceEvent("WLDUSDT", ENTRY_TOUCHED, 100.0, at),
    ]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_price_alert(events, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert message.startswith("[coin-recommender] 가격 알림 3건")
    # BR36: 같은 종목이 여러 트랙에 뽑힐 수 있어 어느 트랙의 도달인지 함께 표시한다.
    assert "(1) SOLUSDT · [기존] 매도가 도달" in message
    assert "(2) ADAUSDT · [기존] 손절가 도달" in message
    assert "(3) WLDUSDT · [기존] 진입가 도달" in message
    assert "08-11 15:32 KST" in message  # 06:32 UTC = 15:32 KST
    assert "UTC" not in message


def test_price_alert_goes_to_every_configured_channel():
    from src.data_store import TARGET_HIT
    from src.notifier import send_price_alert

    events = [FakePriceEvent("SOLUSDT", TARGET_HIT, 103.0, datetime(2026, 8, 11, 6, 32, tzinfo=UTC))]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_price_alert(
            events, RUN_TIME, "TOKEN123", "CHAT456", "https://discord.example/webhook", "https://hooks.slack.com/services/T/B/X"
        )

    assert mock_post.call_count == 3


# --- 시장 국면 문구 (BR23) ---

def _phase(phase_label, *assets):
    """MarketPhase/AssetMomentum 대역. notifier는 속성만 읽으므로 실제 타입이 필요 없다."""
    from types import SimpleNamespace

    return SimpleNamespace(
        phase=phase_label,
        assets=[
            SimpleNamespace(market=market, label=label, returns=returns)
            for market, label, returns in assets
        ],
    )


_FULL = {"1d": 0.012, "7d": 0.034, "30d": 0.256, "90d": 0.41, "365d": 1.2}


def _send_with_phase(recs, phase):
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification(recs, RUN_TIME, None, None, "https://discord.example/webhook", phase=phase)
    return mock_post.call_args.kwargs["json"]["content"]


def test_each_phase_grade_has_its_own_headline():
    """BR25: 강세장 / 상승장 / 약상승장 3단계가 각각 다른 문구로 나가야 한다."""
    strong = _send_with_phase([], _phase("strong_bull", ("BTCUSDT", "strong_bull", _FULL)))
    bull = _send_with_phase([], _phase("bull", ("BTCUSDT", "weak_bull", _FULL)))
    weak = _send_with_phase([], _phase("weak_bull", ("BTCUSDT", "weak_bull", _FULL)))
    assert "강세장" in strong
    assert "상승장" in bull and "강세장" not in bull
    assert "약상승장" in weak


def test_not_bull_phrase_is_reported_too():
    message = _send_with_phase([], _phase("not_bull", ("BTCUSDT", "not_bull", _FULL)))
    assert "상승장 아님" in message


def test_phase_line_appears_even_with_zero_recommendations():
    """게이트가 닫혀 0건인지, 통과한 코인이 없어 0건인지 구분되게 하는 것이 이 줄의 목적이다."""
    message = _send_with_phase([], _phase("strong_bull", ("BTCUSDT", "strong_bull", _FULL)))
    assert "추천 코인 0개" in message
    assert "강세장" in message  # 국면 문구는 추천이 0건이어도 남는다


def test_phase_lists_btc_and_eth_separately_with_all_five_horizons():
    message = _send_with_phase(
        [],
        _phase(
            "weak_bull",
            ("BTCUSDT", "strong_bull", _FULL),
            ("ETHUSDT", "not_bull", {"1d": -0.01, "7d": -0.02, "30d": -0.05, "90d": -0.1, "365d": -0.2}),
        ),
    )
    assert "· BTCUSDT 강상승:" in message
    assert "· ETHUSDT 비상승:" in message
    for horizon in ("일", "주", "30일", "월", "년"):
        assert horizon in message
    assert "+25.6%" in message  # BTC 30일
    assert "-20.0%" in message  # ETH 365일


def test_phase_line_is_omitted_when_phase_is_unknown():
    """이력 부족을 '상승장 아님'으로 적으면 데이터 결손이 시장 판단으로 둔갑한다."""
    message = _send_with_phase([], None)
    assert "강세장" not in message and "약상승장" not in message
    assert "추천 코인 0개" in message


def test_recommendations_still_render_below_the_phase_line():
    recs = [FakeRecommendation("AAAUSDT", 0.01, 5, 3, source="binance")]
    message = _send_with_phase(recs, _phase("strong_bull", ("BTCUSDT", "strong_bull", _FULL)))
    assert message.index("강세장") < message.index("(1) AAAUSDT")
    assert message.startswith("[coin-recommender] 추천 코인 1개")


def test_phase_is_optional_so_existing_callers_are_unaffected():
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification([], RUN_TIME, None, None, "https://discord.example/webhook")
    assert "추천 코인 0개" in mock_post.call_args.kwargs["json"]["content"]


def test_price_alert_shows_which_track_reached_the_price():
    """BR36: 단타(+2%)와 장기(+10%)가 같은 종목에 동시에 걸릴 수 있다 -- 어느 쪽 도달인지
    구분되지 않으면 사용자가 어떤 포지션을 정리해야 할지 알 수 없다."""
    from src.data_store import TARGET_HIT
    from src.notifier import send_price_alert

    at = datetime(2026, 8, 11, 6, 32, tzinfo=UTC)
    day = FakePriceEvent("SOLUSDT", TARGET_HIT, 78.5, at)
    day.track = "day"
    long = FakePriceEvent("SOLUSDT", TARGET_HIT, 85.0, at)
    long.track = "long"

    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_price_alert([day, long], RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "[단타] 매도가 도달" in message
    assert "[장기] 매도가 도달" in message


def test_price_alert_sends_one_message_for_all_events():
    """여러 도달이 한 번에 발생해도 메시지는 하나다 -- 종목마다 따로 보내면 알림이 쌓인다."""
    from src.data_store import TARGET_HIT
    from src.notifier import send_price_alert

    at = datetime(2026, 8, 11, 6, 32, tzinfo=UTC)
    events = [FakePriceEvent(f"SYM{i}USDT", TARGET_HIT, 100.0, at) for i in range(4)]

    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_price_alert(events, RUN_TIME, None, None, "https://discord.example/webhook")

    assert mock_post.call_count == 1  # 채널 1개 = 요청 1회
    assert "가격 알림 4건" in mock_post.call_args.kwargs["json"]["content"]


# --- BR38: 가격 알림 병합 / 트랙별 비율 표기 ---

def _evt(market, kind, price, track, at=None):
    e = FakePriceEvent(market, kind, price, at or datetime(2026, 8, 20, 1, tzinfo=UTC))
    e.track = track
    return e


def test_entry_touch_is_merged_across_tracks():
    """진입가는 트랙과 무관하게 같은 값(진입봉 종가)이라 여러 번 알릴 이유가 없다."""
    from src.data_store import ENTRY_TOUCHED
    from src.notifier import send_price_alert

    events = [_evt("ACEUSDT", ENTRY_TOUCHED, 0.1982, "day"), _evt("ACEUSDT", ENTRY_TOUCHED, 0.1982, "mid")]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_price_alert(events, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "가격 알림 1건" in message  # 2건 -> 1건으로 병합
    assert "[단타] [중기] 진입가 도달" in message


def test_stop_prices_are_not_merged_because_they_differ():
    """손절가는 트랙마다 값이 다르므로 합치면 안 된다 (단타 -2%, 중기 -4%)."""
    from src.data_store import STOP_HIT
    from src.notifier import send_price_alert

    events = [_evt("ACEUSDT", STOP_HIT, 0.194236, "day"), _evt("ACEUSDT", STOP_HIT, 0.190272, "mid")]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_price_alert(events, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "가격 알림 2건" in message


def test_each_track_shows_its_own_stop_percentage():
    """BR38 이전에는 기존 트랙 상수(-2%)를 하드코딩해 중기 손절가 0.190272를 '-2%'로 표기했다."""
    from src.data_store import STOP_HIT
    from src.notifier import send_price_alert

    events = [_evt("ACEUSDT", STOP_HIT, 0.194236, "day"), _evt("ACEUSDT", STOP_HIT, 0.190272, "mid")]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_price_alert(events, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "0.194236  (-2%)" in message
    assert "0.190272  (-4%)" in message


def test_each_track_shows_its_own_target_percentage():
    from src.data_store import TARGET_HIT
    from src.notifier import send_price_alert

    events = [_evt("SOLUSDT", TARGET_HIT, 78.54, "day"), _evt("SOLUSDT", TARGET_HIT, 84.7, "long")]
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_price_alert(events, RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "78.54  (+2%)" in message
    assert "84.7  (+10%)" in message


def test_legacy_track_falls_back_to_the_regime_rules():
    from src.data_store import STOP_HIT
    from src.notifier import send_price_alert

    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_price_alert([_evt("OLDUSDT", STOP_HIT, 98.0, "regime")], RUN_TIME, None, None, "https://d.example/w")

    assert "(-2%)" in mock_post.call_args.kwargs["json"]["content"]  # 기존 트랙 STOP_LOSS
