import logging
from datetime import datetime, timedelta

import requests

from src.backtest import STOP_LOSS, TARGET_RETURN

logger = logging.getLogger(__name__)

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


_HOLD_HOURS = 24


def _entry_guide_lines(r) -> list[str]:
    """BR16/BR18: the entry the backtest actually measured, so acting on it matches the published
    probability. 목표가·손절가는 진입가에서 파생하므로 백테스트 규칙과 어긋날 수 없다."""
    entry_price = getattr(r, "entry_price", None)
    entry_time = getattr(r, "entry_time", None)
    if entry_price is None or entry_time is None:
        return []
    deadline = entry_time + timedelta(hours=_HOLD_HOURS)
    return [
        f"    진입 {entry_price:,.6g} ({entry_time.strftime('%m-%d %H:%M')} UTC 종가 기준)",
        f"    매도 {entry_price * (1 + TARGET_RETURN):,.6g} (+{TARGET_RETURN:.0%})"
        f"  /  손절 {entry_price * (1 - STOP_LOSS):,.6g} (-{STOP_LOSS:.0%})",
        f"    청산 기한 {deadline.strftime('%m-%d %H:%M')} UTC (진입 +{_HOLD_HOURS}시간)",
    ]


def _format_message(run_time: datetime, recommendations: list) -> str:
    """BR5: Korean notification message format."""
    header = f"[coin-recommender] {run_time.isoformat()} 추천 결과"
    if not recommendations:
        return f"{header}\n\n이번 회차 추천 없음"
    lines = []
    for r in recommendations:
        hit_rate = getattr(r, "hit_rate", None)
        if hit_rate is None and r.n:
            hit_rate = r.hit_count / r.n
        rate_text = "-" if hit_rate is None else f"{hit_rate:.0%}"
        lines.append(
            f"- [{getattr(r, 'source', 'binance')}] {r.market}: 24시간 내 목표 도달 확률 {rate_text}"
            f" (과거 {r.n}회 중 {r.hit_count}회, 손절 -{STOP_LOSS:.0%} 적용 기준)"
        )
        lines.extend(_entry_guide_lines(r))
    return header + "\n\n" + "\n".join(lines)


def send_notification(
    recommendations: list,
    run_time: datetime,
    telegram_bot_token: str | None,
    telegram_chat_id: str | None,
    discord_webhook_url: str | None,
    timeout_seconds: float = 10.0,
) -> None:
    """BR4: sends to every configured channel independently; a failure on one channel does not
    prevent the other from being attempted. Caller (Pipeline) treats this as best-effort (BR3)."""
    message = _format_message(run_time, recommendations)

    if telegram_bot_token and telegram_chat_id:
        _send_telegram(telegram_bot_token, telegram_chat_id, message, timeout_seconds)
    if discord_webhook_url:
        _send_discord(discord_webhook_url, message, timeout_seconds)
    if not (telegram_bot_token and telegram_chat_id) and not discord_webhook_url:
        logger.info("No notification channel configured; skipping notification")


def _send_telegram(bot_token: str, chat_id: str, message: str, timeout_seconds: float) -> None:
    """Telegram has no generic outbound webhook URL (unlike Discord) -- messages are sent via the
    Bot API's sendMessage endpoint, which requires a bot token and target chat id."""
    try:
        url = _TELEGRAM_API_URL.format(token=bot_token)
        response = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.RequestException:
        logger.warning("Telegram notification failed", exc_info=True)


def _send_discord(webhook_url: str, message: str, timeout_seconds: float) -> None:
    try:
        response = requests.post(webhook_url, json={"content": message}, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.RequestException:
        logger.warning("Discord notification failed", exc_info=True)
