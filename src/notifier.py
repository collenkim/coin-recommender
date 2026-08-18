import logging
from datetime import datetime, timedelta, timezone

import requests

from src.backtest import STOP_LOSS, TARGET_RETURN
from src.data_store import ENTRY_TOUCHED, STOP_HIT, TARGET_HIT
from src.long_track import (
    LONG_HOLD_BARS_4H,
    LONG_STOP_LOSS,
    LONG_TARGET_RETURN,
    cycle_position,
    next_open_at,
)
from src.market_phase import NOT_BULL, STRONG_BULL, WEAK_BULL

logger = logging.getLogger(__name__)

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


_HOLD_HOURS = 24
# 알림은 사람이 읽는 화면이므로 한국 시간으로 표기한다. 저장·API는 UTC를 유지한다 --
# 표시 형식과 저장 형식을 같이 바꾸면 과거 데이터 해석이 어긋난다.
_KST = timezone(timedelta(hours=9))


def _kst(moment: datetime, fmt: str = "%m-%d %H:%M") -> str:
    return moment.astimezone(_KST).strftime(fmt)


_LONG_HOLD_DAYS = LONG_HOLD_BARS_4H * 4 // 24


def _track_rules(r):
    """BR24: 트랙마다 목표·손절·보유기간이 다르다. 하나의 상수를 공유하면 장기 추천이 단기
    기준으로 잘못 표기된다."""
    if getattr(r, "track", "short") == "long":
        return LONG_TARGET_RETURN, LONG_STOP_LOSS, _LONG_HOLD_DAYS * 24
    return TARGET_RETURN, STOP_LOSS, _HOLD_HOURS


def _entry_guide_lines(r) -> list[str]:
    """BR16/BR18: the entry the backtest actually measured, so acting on it matches the published
    probability. 목표가·손절가는 진입가에서 파생하므로 백테스트 규칙과 어긋날 수 없다."""
    entry_price = getattr(r, "entry_price", None)
    entry_time = getattr(r, "entry_time", None)
    if entry_price is None or entry_time is None:
        return []
    target, stop, hold_hours = _track_rules(r)
    deadline = entry_time + timedelta(hours=hold_hours)
    horizon = f"진입 +{hold_hours // 24}일" if hold_hours >= 48 else f"진입 +{hold_hours}시간"
    return [
        f"· 진입가: {entry_price:,.6g}  ({_kst(entry_time)} KST 봉 마감 기준)",
        f"· 매도가: {entry_price * (1 + target):,.6g}  (+{target:.0%})",
        f"· 손절가: {entry_price * (1 - stop):,.6g}  (-{stop:.0%})",
        f"· 청산 기한: {_kst(deadline)} KST  ({horizon})",
    ]


def _recommendation_block(order: int, r) -> str:
    """추천 1건 = 한 단락. 번호를 붙여 몇 번째 종목인지 바로 보이게 한다."""
    hit_rate = getattr(r, "hit_rate", None)
    if hit_rate is None and r.n:
        hit_rate = r.hit_count / r.n
    rate_text = "-" if hit_rate is None else f"{hit_rate:.0%}"
    target, stop, hold_hours = _track_rules(r)
    window = f"{hold_hours // 24}일" if hold_hours >= 48 else f"{hold_hours}시간"
    lines = [
        f"({order}) {r.market} · {getattr(r, 'source', 'binance')}",
        f"· {window} 내 +{target:.0%} 도달 확률: {rate_text}"
        f"  (과거 {r.n}회 중 {r.hit_count}회, 손절 -{stop:.0%} 적용 기준)",
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


# 문구는 **지금 상태의 설명**이지 전망이 아니다 (BR23) -- "오른다"는 뜻이 읽히는 표현을 쓰지 않는다.
_PHASE_HEADLINE = {
    STRONG_BULL: "강상승장 — BTC·ETH 둘 다 상승 모멘텀이 강합니다",
    WEAK_BULL: "약상승장 — BTC·ETH 둘 다 상승 중이지만 강세까지는 아닙니다",
    NOT_BULL: "상승장 아님 — BTC·ETH가 함께 상승하고 있지는 않습니다",
}
_ASSET_LABELS = {STRONG_BULL: "강상승", WEAK_BULL: "약상승", NOT_BULL: "비상승"}
# 사람이 읽는 순서. 짧은 구간부터 긴 구간으로 늘어놓아야 추세가 한눈에 보인다.
_HORIZON_LABELS = (("1d", "일"), ("7d", "주"), ("30d", "30일"), ("90d", "월"), ("365d", "년"))


def _phase_lines(phase) -> list[str]:
    """BR23: 시장 국면 문구. 판정이 없으면(이력 부족) 아무 줄도 넣지 않는다 -- 모르는 것을
    "상승장 아님"으로 적으면 데이터 결손이 시장 판단으로 둔갑한다."""
    if phase is None:
        return []
    lines = [_PHASE_HEADLINE[phase.phase]]
    for asset in phase.assets:
        moves = "  ".join(
            f"{text} {asset.returns[key]:+.1%}" for key, text in _HORIZON_LABELS if key in asset.returns
        )
        lines.append(f"· {asset.market} {_ASSET_LABELS[asset.label]}:  {moves}")
    return lines


def _short_section(recommendations: list) -> list[str]:
    header = f"[단기] 24시간 내 +{TARGET_RETURN:.0%} 목표 · {len(recommendations)}개"
    if not recommendations:
        return [f"{header}\n· 조건을 만족한 종목 없음"]
    return [header] + [_recommendation_block(i, r) for i, r in enumerate(recommendations, 1)]


def _long_section(recommendations: list, now: datetime) -> list[str]:
    """BR24: 장기 트랙. 0건이어도 제목과 사유를 남긴다 -- 그래야 게이트가 닫혀서 0건인지,
    열렸는데 통과한 종목이 없어서 0건인지 구분된다."""
    header = (
        f"[장기] 반감기 구간 · {_LONG_HOLD_DAYS}일 내 +{LONG_TARGET_RETURN:.0%} 목표"
        f" · {len(recommendations)}개"
    )
    position = cycle_position(now)
    if position is None or not position.is_open:
        reason = (
            f"반감기 후 {position.elapsed_years:.1f}년차 — 개방 구간 아님"
            if position is not None
            else "사이클 판정 불가"
        )
        opens = next_open_at(now)
        if opens is not None:
            reason += f" (다음 개방 {opens.date()})"
        return [f"{header}\n· {reason}"]
    if not recommendations:
        return [f"{header}\n· 반감기 후 {position.elapsed_years:.1f}년차 (개방) — 조건을 만족한 종목 없음"]
    blocks = [header] + [_recommendation_block(i, r) for i, r in enumerate(recommendations, 1)]
    # 근거 강도를 함께 적는다. 단기 트랙(5년/876매매)과 같은 신뢰도로 읽히면 안 된다.
    blocks.append("· 근거: 반감기 사이클 표본 2개, out-of-sample 검증 아님 — 단기 트랙보다 근거가 약함")
    return blocks


def _format_message(run_time: datetime, recommendations: list, phase=None, long_recommendations=None, now=None) -> str:
    """BR5/BR23/BR24: 상단에 추천 개수와 시장 국면, 그 아래 트랙별 섹션.

    두 트랙을 별도 발송하지 않는 이유: 시간당 알림이 두 배가 되고, 한쪽만 0건일 때 "왜 안 왔는지"를
    구분할 수 없다."""
    long_recommendations = long_recommendations or []
    stamp = f"{_kst(run_time, '%Y-%m-%d %H:%M')} KST"
    total = len(recommendations) + len(long_recommendations)
    parts = [f"[coin-recommender] 추천 코인 {total}개\n{stamp}"]

    phase_block = _phase_lines(phase)
    if phase_block:
        parts.append("\n".join(phase_block))

    parts.extend(_short_section(recommendations))
    parts.extend(_long_section(long_recommendations, now or run_time))
    return "\n\n".join(parts)


def send_notification(
    recommendations: list,
    run_time: datetime,
    telegram_bot_token: str | None,
    telegram_chat_id: str | None,
    discord_webhook_url: str | None,
    slack_webhook_url: str | None = None,
    timeout_seconds: float = 10.0,
    phase=None,
    long_recommendations=None,
    now=None,
) -> None:
    """BR4: sends to every configured channel independently; a failure on one channel does not
    prevent the others from being attempted. Caller (Pipeline) treats this as best-effort (BR3)."""
    _dispatch(
        _format_message(run_time, recommendations, phase, long_recommendations, now),
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
