import logging
from datetime import datetime, timedelta, timezone
from decimal import ROUND_FLOOR, Decimal

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


# BR42: 바이낸스 USDT 현물의 호가 단위는 종목마다 다르고(실측 484종: 0~8자리) 가장 잘게
# 쪼개는 종목이 8자리다. 표기는 그 최대치에서 자른다.
_PRICE_STEP = Decimal("1e-8")


def _price(value: float | None) -> str:
    """BR42: 가격 표기 — 소수 8자리에서 **내림**.

    `%g`는 값이 작아지면 지수 표기로 넘어가 PEPE 매도가를 `3.157e-06`으로 발송했다. 그렇다고
    자릿수를 짧게 고정할 수도 없다: 6자리로 반올림하면 PEPE 진입가 0.00000287과 매도가
    0.00000316이 **둘 다 `0.000003`**이 되어 구분 자체가 사라진다.

    자르기 전에 유효숫자 10자리로 한 번 정리한다. 목표·손절가는 곱셈으로 만들어져 부동소수점
    오차를 달고 있어서다 -- `6.56 * 1.02`는 6.6911999999999995이고, 이대로 8자리에서 내리면
    `6.69119999`가 되어 고치기 전보다 더 깨져 보인다.

    내림을 쓰는 이유: 매도가는 표시값이 실제 목표보다 높으면 그 지정가가 체결되지 않는다.
    """
    if value is None:
        return "-"
    if value <= 0:
        return f"{value:,.2f}"
    stepped = Decimal(f"{value:.10g}").quantize(_PRICE_STEP, rounding=ROUND_FLOOR)
    whole, _, frac = f"{stepped:,f}".partition(".")
    return f"{whole}.{frac.rstrip('0').ljust(2, '0')}"


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
        f"· 진입가: {_price(entry_price)}  ({_kst(entry_time)} KST 봉 마감 기준)",
        f"· 매도가: {_price(entry_price * (1 + target))}  (+{target:.0%})",
        f"· 손절가: {_price(entry_price * (1 - stop))}  (-{stop:.0%}, 아래 확률의 전제)",
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
    ENTRY_TOUCHED: ("진입가 도달 (지금 진입 가능)", "진입가"),
    TARGET_HIT: ("매도가 도달", "매도가"),
    STOP_HIT: ("손절가 도달", "손절가"),
}


def _event_note(kind: str, track: str) -> str:
    """BR38: 목표·손절 비율은 **트랙마다 다르다**. 이전에는 기존 레짐 트랙의 상수
    (+3%/-2%)를 하드코딩해, 중기 손절가 0.190272(-4%)를 "-2%"로 표기했다."""
    if kind == ENTRY_TOUCHED:
        return "기준"
    spec = TRACK_BY_KEY.get(track)
    target, stop = (spec.target, spec.stop) if spec else (TARGET_RETURN, STOP_LOSS)
    return f"+{target:.0%}" if kind == TARGET_HIT else f"-{stop:.0%}"


def _merge_events(events: list) -> list[tuple]:
    """BR38: **같은 가격을 가리키는 알림은 하나로 합친다.**

    진입가는 트랙과 무관하게 같은 값(진입봉 종가)이라, 트랙마다 따로 알리면 같은 내용이
    2~3번 반복된다. 목표·손절은 트랙마다 값이 다르므로 합치지 않는다.

    반환: (종목, 종류, 가격, 도달시각, [트랙...])"""
    merged: dict = {}
    for event in events:
        track = getattr(event, "track", "regime")
        key = (event.market, event.kind, round(event.price, 12))
        if key not in merged:
            merged[key] = [event.market, event.kind, event.price, event.at, []]
        if track not in merged[key][4]:
            merged[key][4].append(track)
    return [tuple(v) for v in merged.values()]


def _format_price_alert(now: datetime, events: list) -> str:
    """BR22: 도달 알림도 추천 알림과 같은 형식 규칙 -- 상단에 건수, 종목마다 번호 붙인 단락."""
    merged = _merge_events(events)
    header = f"[coin-recommender] 가격 알림 {len(merged)}건\n{_kst(now, '%Y-%m-%d %H:%M')} KST"
    blocks = []
    for order, (market, kind, price, at, tracks) in enumerate(merged, 1):
        title, price_label = _EVENT_LABELS[kind]
        labels = "".join(_TRACK_LABELS.get(t, "") for t in tracks)
        blocks.append(
            "\n".join(
                [
                    f"({order}) {market} · {labels}{title}",
                    f"· {price_label}: {_price(price)}  ({_event_note(kind, tracks[0])})",
                    f"· 도달 시각: {_kst(at)} KST",
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
        f"· 업비트 {premium.upbit_krw:,.0f}원 / 바이낸스 {_price(premium.binance_usdt)} USDT"
        f" (환율 {premium.usd_krw:,.2f})",
        f"· {MEASURED_NOTE}",
    ]


# BR37: 실적 표본이 이만큼 쌓이기 전에는 확률로 읽지 않도록 문구를 달리한다. 트랙 실측
# 도달률이 21~36%인데 표본 20건이면 우연히 88%가 나올 수 있다 -- 실제로 첫날 17건에서 88%가 나왔다.
_PERFORMANCE_MIN_SAMPLES = 30


def _performance_lines(performance) -> list[str]:
    """BR37: **실제 발송한 추천**의 매도가 도달률. 백테스트 확률과 다른 수치다.

    표본이 적을 때 확정된 실력으로 읽히지 않도록 건수를 항상 함께 적고, 하한 미만이면
    '표본 부족'을 명시한다."""
    if not performance:
        return []
    total = performance.get("total", {})
    resolved = total.get("resolved", 0)
    if not resolved:
        return ["[실적] 아직 결과가 확정된 추천이 없습니다"]
    rate = total.get("hit", 0) / resolved
    by = performance.get("by_track", {})
    parts = []
    for spec in TRACKS:
        stats = by.get(spec.key)
        if not stats or not stats["resolved"]:
            continue
        parts.append(f"{spec.label} {stats['hit'] / stats['resolved']:.0%}({stats['resolved']}건)")
    detail = "  ".join(parts)
    caveat = "" if resolved >= _PERFORMANCE_MIN_SAMPLES else f" — 표본 {resolved}건, 아직 판단하기 이릅니다"
    lines = [f"[실적] 매도가 도달 {total.get('hit', 0)}/{resolved}건 = {rate:.0%}{caveat}"]
    if detail:
        lines.append(f"· {detail}")
    return lines


def _format_message(
    run_time: datetime,
    recommendations: list,
    phase=None,
    tracks=None,
    now=None,
    premium=None,
    performance=None,
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

    performance_block = _performance_lines(performance)
    if performance_block:
        parts.append("\n".join(performance_block))

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
    performance=None,
) -> None:
    """BR4: sends to every configured channel independently; a failure on one channel does not
    prevent the others from being attempted. Caller (Pipeline) treats this as best-effort (BR3)."""
    _dispatch(
        _format_message(run_time, recommendations, phase, tracks, now, premium, performance),
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
