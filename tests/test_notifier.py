from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests

from src.notifier import send_notification

UTC = timezone.utc
RUN_TIME = datetime(2024, 1, 1, tzinfo=UTC)


class FakeRecommendation:
    def __init__(self, market, expected_return, n, hit_count):
        self.market = market
        self.expected_return = expected_return
        self.n = n
        self.hit_count = hit_count


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
    assert "5.1%" in message
    assert "3회 중 2회 적중" in message


def test_message_format_with_no_recommendations():
    with patch("src.notifier.requests.post", return_value=ok_response()) as mock_post:
        send_notification([], RUN_TIME, None, None, "https://discord.example/webhook")

    message = mock_post.call_args.kwargs["json"]["content"]
    assert "이번 회차 추천 없음" in message
