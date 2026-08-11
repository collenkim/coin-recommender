import logging
from datetime import datetime, timedelta, timezone

import requests

from src.backtest import STOP_LOSS, TARGET_RETURN
from src.data_store import ENTRY_TOUCHED, STOP_HIT, TARGET_HIT

logger = logging.getLogger(__name__)

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


_HOLD_HOURS = 24
# 알림은 사람이 읽는 화면이므로 한국 시간으로 표기한다. 저장·API는 UTC를 유지한다 --
# 표시 형식과 저장 형식을 같이 바꾸면 과거 데이터 해석이 어긋난다.
_KST = timezone(timedelta(hours=9))


def _kst(moment: datetime, fmt: str = "%m-%d %H:%M") -> str:
    return moment.astimezone(_KST).strftime(fmt)


def _entry_guide_lines(r) -> list[str]:
    """BR16/BR18: the entry the backtest actually measured, so acting on it matches the published
    probability. 목표가·손절가는 진입가에서 파생하므로 백테스트 규칙과 어긋날 수 없다."""
    entry_price = getattr(r, "entry_price", None)
    entry_time = getattr(r, "entry_time", None)
    if entry_price is None or entry_time is None:
        return []
    deadline = entry_time + timedelta(hours=_HOLD_HOURS)
    return [
        f"· 진입가: {entry_price:,.6g}  ({_kst(entry_time)} KST 봉 마감 기준)",
        f"· 매도가: {entry_price * (1 + TARGET_RETURN):,.6g}  (+{TARGET_RETURN:.0%})",
        f"· 손절가: {entry_price * (1 - STOP_LOSS):,.6g}  (-{STOP_LOSS:.0%})",
        f"· 청산 기한: {_kst(deadline)} KST  (진입 +{_HOLD_HOURS}시간)",
    ]


def _recommendation_block(order: int, r) -> str:
    """추천 1건 = 한 단락. 번호를 붙여 몇 번째 종목인지 바로 보이게 한다."""
    hit_rate = getattr(r, "hit_rate", None)
    if hit_rate is None and r.n:
        hit_rate = r.hit_count / r.n
    rate_text = "-" if hit_rate is None else f"{hit_rate:.0%}"
    lines = [
        f"({order}) {r.market} · {getattr(r, 'source', 'binance')}",
        f"· 24시간 내 +{TARGET_RETURN:.0%} 도달 확률: {rate_text}"
        f"  (과거 {r.n}회 중 {r.hit_count}회, 손절 -{STOP_LOSS:.0%} 적용 기준)",
    ]
    lines.extend(_entry_guide_lines(r))
    return "\n".join(lines)


_EVENT_LABELS = {
    ENTRY_TOUCHED: ("진입가 도달 (지금 진입 가능)", "진입가", f"기준"),
    TARGET_HIT: ("매도가 도달", "매도가", f"+{TARGET_RETURN:.0%}"),
    STOP_HIT: ("손절가 도달", "손절가", f"-{STOP_LOSS:.0%}"),
}


def _format_price_alert(now: datetime, events: list) -> str:
    """BR22: 도달 알림도 추천 알림과 같은 형식 규칙 -- 상단에 건수, 종목마다 번호 붙인 단락."""
    header = f"[coin-recommender] 가격 알림 {len(events)}건\n{_kst(now, '%Y-%m-%d %H:%M')} KST"
    blocks = []
    for order, event in enumerate(events, 1):
        title, price_label, note = _EVENT_LABELS[event.kind]
        blocks.append(
            "\n".join(
                [
                    f"({order}) {event.market} · {title}",
                    f"· {price_label}: {event.price:,.6g}  ({note})",
                    f"· 도달 시각: {_kst(event.at)} KST",
                ]
            )
        )
    return header + "\n\n" + "\n\n".join(blocks)


def _format_message(run_time: datetime, recommendations: list) -> str:
    """BR5: Korean notification message format. 상단에 추천 개수, 종목마다 번호 붙인 단락."""
    stamp = f"{_kst(run_time, '%Y-%m-%d %H:%M')} KST"
    if not recommendations:
        return f"[coin-recommender] 추천 코인 0개\n{stamp}\n\n이번 회차 추천 없음"

    header = f"[coin-recommender] 추천 코인 {len(recommendations)}개\n{stamp}"
    blocks = [_recommendation_block(i, r) for i, r in enumerate(recommendations, 1)]
    return header + "\n\n" + "\n\n".join(blocks)


def send_notification(
    recommendations: list,
    run_time: datetime,
    telegram_bot_token: str | None,
    telegram_chat_id: str | None,
    discord_webhook_url: str | None,
    slack_webhook_url: str | None = None,
    timeout_seconds: float = 10.0,
) -> None:
    """BR4: sends to every configured channel independently; a failure on one channel does not
    prevent the others from being attempted. Caller (Pipeline) treats this as best-effort (BR3)."""
    _dispatch(
        _format_message(run_time, recommendations),
        telegram_bot_token,
        telegram_chat_id,
        discord_webhook_url,
        slack_webhook_url,
        timeout_seconds,
    )


def send_price_alert(
    events: list,
    now: datetime,
    telegram_bot_token: str | None,
    telegram_chat_id: str | None,
    discord_webhook_url: str | None,
    slack_webhook_url: str | None = None,
    timeout_seconds: float = 10.0,
) -> None:
    """BR22: 가격 도달 알림. 발생한 이벤트가 없으면 아무것도 보내지 않는다 -- 5분마다
    "변화 없음"을 보내면 하루 288통이 된다."""
    if not events:
        return
    _dispatch(
        _format_price_alert(now, events),
        telegram_bot_token,
        telegram_chat_id,
        discord_webhook_url,
        slack_webhook_url,
        timeout_seconds,
    )


def _dispatch(
    message: str,
    telegram_bot_token: str | None,
    telegram_chat_id: str | None,
    discord_webhook_url: str | None,
    slack_webhook_url: str | None,
    timeout_seconds: float,
) -> None:
    if telegram_bot_token and telegram_chat_id:
        _send_telegram(telegram_bot_token, telegram_chat_id, message, timeout_seconds)
    if discord_webhook_url:
        _send_discord(discord_webhook_url, message, timeout_seconds)
    if slack_webhook_url:
        _send_slack(slack_webhook_url, message, timeout_seconds)
    if not any((telegram_bot_token and telegram_chat_id, discord_webhook_url, slack_webhook_url)):
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


def _send_slack(webhook_url: str, message: str, timeout_seconds: float) -> None:
    """Slack Incoming Webhook. Discord와 같은 단일 URL POST 방식이고 페이로드 키만 `text`로 다르다
    (Telegram처럼 토큰+대상 조합이 필요하지 않다)."""
    try:
        response = requests.post(webhook_url, json={"text": message}, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.RequestException:
        logger.warning("Slack notification failed", exc_info=True)
