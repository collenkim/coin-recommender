import logging
from datetime import datetime, timedelta, timezone

import requests

from src.backtest import STOP_LOSS, TARGET_RETURN
from src.data_store import ENTRY_TOUCHED, STOP_HIT, TARGET_HIT
from src.market_phase import BULL, NOT_BULL, STRONG_BULL, WEAK_BULL
from src.premium import MEASURED_NOTE, REVERSE_PREMIUM_THRESHOLD
from src.tracks import TRACK_BY_KEY, TRACKS

logger = logging.getLogger(__name__)

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


_HOLD_HOURS = 24
# 알림은 사람이 읽는 화면이므로 한국 시간으로 표기한다. 저장·API는 UTC를 유지한다 --
# 표시 형식과 저장 형식을 같이 바꾸면 과거 데이터 해석이 어긋난다.
_KST = timezone(timedelta(hours=9))


def _kst(moment: datetime, fmt: str = "%m-%d %H:%M") -> str:
    return moment.astimezone(_KST).strftime(fmt)


def _track_rules(r):
    """BR25: 트랙마다 목표·손절·보유기간이 다르다. 하나의 상수를 공유하면 장기 추천이 단기
    기준으로 잘못 표기된다."""
    spec = TRACK_BY_KEY.get(getattr(r, "track", "regime"))
    if spec is not None:
        return spec.target, spec.stop, spec.hold_hours
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
        f"· 손절가: {entry_price * (1 - stop):,.6g}  (-{stop:.0%}, 아래 확률의 전제)",
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


# BR36: 같은 종목이 여러 트랙에 뽑힐 수 있으므로 어느 트랙의 도달인지 표시한다.
_TRACK_LABELS = {t.key: f"[{t.label}] " for t in TRACKS} | {"regime": "[기존] "}

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
                    f"({order}) {event.market} · {_TRACK_LABELS.get(getattr(event, 'track', 'regime'), '')}{title}",
                    f"· {price_label}: {event.price:,.6g}  ({note})",
                    f"· 도달 시각: {_kst(event.at)} KST",
                ]
            )
        )
    return header + "\n\n" + "\n\n".join(blocks)


# 문구는 **지금 상태의 설명**이지 전망이 아니다 (BR23) -- "오른다"는 뜻이 읽히는 표현을 쓰지 않는다.
_PHASE_HEADLINE = {
    STRONG_BULL: "강세장 — BTC·ETH 둘 다 상승 모멘텀이 강합니다",
    BULL: "상승장 — BTC·ETH 둘 다 상승 중이지만 강세까지는 아닙니다",
    WEAK_BULL: "약상승장 — 둘 중 하나만 상승 중입니다",
    NOT_BULL: "상승장 아님 — BTC·ETH 모두 상승 모멘텀이 없습니다",
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


def _hours_text(hours: int) -> str:
    return f"{hours // 24}일" if hours >= 48 else f"{hours}시간"


def _regime_section(recommendations: list) -> list[str]:
    """BR18~BR21 레짐 게이트 트랙. BR25 4트랙과 게이트·진입조건이 달라 섹션을 따로 둔다.

    BR36: 추천이 없으면 **섹션 자체를 뺀다.** 이전에는 "어느 트랙이 왜 비었는지 드러내려고"
    제목을 남겼으나, 대부분의 회차가 0건이라 메시지가 빈 제목으로만 채워졌다."""
    if not recommendations:
        return []
    header = f"[기존] 레짐 게이트 · 24시간 내 +{TARGET_RETURN:.0%} 목표 · {len(recommendations)}개"
    return [header] + [_recommendation_block(i, r) for i, r in enumerate(recommendations, 1)]


def _track_section(spec, recommendations: list) -> list[str]:
    """BR25/BR36: 트랙 하나 = 섹션 하나. **추천이 없으면 섹션을 통째로 뺀다.**"""
    if not recommendations:
        return []
    signal = f"{spec.timeframe} 골든크로스" + (" + 구름 위" if spec.require_above_cloud else "")
    # BR34: 손절 집행은 사용자 몫이다. 다만 발표하는 확률은 **표시된 손절을 전제로** 계산된
    # 값이므로, 다른 손절을 쓰면 그 확률은 더 이상 맞지 않는다는 점을 함께 적는다.
    header = (
        f"[{spec.label}] {_hours_text(spec.hold_hours)} 내 +{spec.target:.0%} 목표"
        f" (손절 -{spec.stop:.0%}, {signal}) · {len(recommendations)}개"
    )
    return [header] + [_recommendation_block(i, r) for i, r in enumerate(recommendations, 1)]


def _premium_lines(premium) -> list[str]:
    """BR35: 역프 알림. **매수 신호가 아니다** -- 실측은 오히려 반대를 가리키므로 그 통계를
    함께 적어 잘못된 확신을 주지 않는다."""
    if premium is None:
        return []
    return [
        f"[시장 이벤트] BTC 역프 {premium.value:.2%} (기준 {REVERSE_PREMIUM_THRESHOLD:.0%} 이하)",
        f"· 업비트 {premium.upbit_krw:,.0f}원 / 바이낸스 {premium.binance_usdt:,.6g} USDT"
        f" (환율 {premium.usd_krw:,.2f})",
        f"· {MEASURED_NOTE}",
    ]


def _format_message(
    run_time: datetime, recommendations: list, phase=None, tracks=None, now=None, premium=None
) -> str:
    """BR5/BR23/BR25: 상단에 총 개수와 시장 국면, 그 아래 트랙별 섹션.

    트랙을 별도 발송하지 않는 이유: 시간당 알림이 다섯 배가 되고, 어느 트랙이 왜 0건인지
    구분할 수 없다."""
    tracks = tracks or {}
    stamp = f"{_kst(run_time, '%Y-%m-%d %H:%M')} KST"
    total = len(recommendations) + sum(len(v) for v in tracks.values())
    parts = [f"[coin-recommender] 추천 코인 {total}개\n{stamp}"]

    phase_block = _phase_lines(phase)
    if phase_block:
        parts.append("\n".join(phase_block))

    premium_block = _premium_lines(premium)
    if premium_block:
        parts.append("\n".join(premium_block))

    for spec in TRACKS:
        parts.extend(_track_section(spec, tracks.get(spec.key, [])))
    parts.extend(_regime_section(recommendations))
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
    tracks=None,
    now=None,
    premium=None,
) -> None:
    """BR4: sends to every configured channel independently; a failure on one channel does not
    prevent the others from being attempted. Caller (Pipeline) treats this as best-effort (BR3)."""
    _dispatch(
        _format_message(run_time, recommendations, phase, tracks, now, premium),
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
