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
    assert "이번 회차 추천 없음" in message


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
    body = message.split("\n\n", 1)[1]
    assert len(body.split("\n\n")) == 3  # 종목마다 빈 줄로 분리된 한 단락
    for order in (1, 2, 3):
        assert f"({order}) SYM{order - 1}USDT" in message


def test_zero_recommendations_still_reports_a_count():
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification([], RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "추천 코인 0개" in message
    assert "이번 회차 추천 없음" in message
