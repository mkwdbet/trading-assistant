from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from app.schemas import SignalCreate as Signal

KST = timezone(timedelta(hours=9), name="KST")

BUY_COLOR = 0x2ECC71
SELL_COLOR = 0xE74C3C
TREND_CHANGE_COLOR = 0x3498DB
WARNING_COLOR = 0xF1C40F

SIGNAL_TEMPLATES = {
    "매수 관심": {
        "emoji": "🟢",
        "color": BUY_COLOR,
        "judgment": "매수 관심 구간입니다. 추격 진입이 아니라 눌림 확인용 알림입니다.",
    },
    "강한 매수 관심": {
        "emoji": "🟢",
        "color": BUY_COLOR,
        "judgment": "강한 매수 관심 구간입니다. 장기 기준선 반응을 확인하는 알림입니다.",
    },
    "매도 관심": {
        "emoji": "🔴",
        "color": SELL_COLOR,
        "judgment": "매도 관심 구간입니다. 추격 진입이 아니라 저항 확인용 알림입니다.",
    },
    "강한 매도 관심": {
        "emoji": "🔴",
        "color": SELL_COLOR,
        "judgment": "강한 매도 관심 구간입니다. 장기 기준선 저항을 확인하는 알림입니다.",
    },
    "상승 추세 전환": {
        "emoji": "🔵",
        "color": TREND_CHANGE_COLOR,
        "judgment": "상승 추세 전환 후보입니다. 정배열 완성 이후 후속 가격 반응을 확인합니다.",
    },
    "하락 추세 전환": {
        "emoji": "🔵",
        "color": TREND_CHANGE_COLOR,
        "judgment": "하락 추세 전환 후보입니다. 역배열 완성 이후 후속 가격 반응을 확인합니다.",
    },
}

SITUATION_SUMMARIES = {
    "21선 눌림": "4시간봉 상승 추세에서 SMA21 눌림 재접근",
    "60선 눌림": "4시간봉 상승 추세에서 SMA60 눌림 재접근",
    "21선 저항": "4시간봉 하락 추세에서 SMA21 저항 재접근",
    "60선 저항": "4시간봉 하락 추세에서 SMA60 저항 재접근",
    "정배열 완성": "4시간봉 SMA 정배열이 완성되었습니다.",
    "역배열 완성": "4시간봉 SMA 역배열이 완성되었습니다.",
}

FIELD_SITUATION_LABELS = {
    "21선 눌림": "SMA21 눌림",
    "60선 눌림": "SMA60 눌림",
    "21선 저항": "SMA21 저항",
    "60선 저항": "SMA60 저항",
}


def format_discord_signal_embed(signal: Signal) -> dict[str, Any]:
    template = _template_for_signal(signal.signal_type)
    title = f"{template['emoji']} {signal.symbol} | {signal.signal_type}"
    description = "\n\n".join(
        [
            f"**상황**\n{_summary_for_signal(signal)}",
            f"**판단**\n{template['judgment']}",
            f"**이유**\n{_format_reason(signal)}",
        ]
    )

    embed: dict[str, Any] = {
        "title": title,
        "description": description,
        "color": template["color"],
        "fields": [
            {"name": "Timeframe", "value": _format_timeframe(signal.timeframe), "inline": True},
            {"name": "State", "value": signal.market_state or "-", "inline": True},
            {"name": "Situation", "value": _format_situation_field(signal.situation), "inline": True},
            {"name": "Strategy", "value": signal.strategy_name, "inline": True},
            {"name": "Occurred At", "value": _format_kst(signal.occurred_at), "inline": False},
        ],
    }

    values = _format_market_values(signal)
    if values:
        embed["footer"] = {"text": values}

    return embed


def _template_for_signal(signal_type: str) -> dict[str, Any]:
    if signal_type in SIGNAL_TEMPLATES:
        return SIGNAL_TEMPLATES[signal_type]
    if "매수" in signal_type:
        return {"emoji": "🟢", "color": BUY_COLOR, "judgment": "매수 관점에서 확인할 구간입니다."}
    if "매도" in signal_type:
        return {"emoji": "🔴", "color": SELL_COLOR, "judgment": "매도 관점에서 확인할 구간입니다."}
    if "전환" in signal_type:
        return {"emoji": "🔵", "color": TREND_CHANGE_COLOR, "judgment": "추세 전환 가능성을 확인할 구간입니다."}
    return {"emoji": "🟡", "color": WARNING_COLOR, "judgment": "관망 또는 확인이 필요한 알림입니다."}


def _summary_for_signal(signal: Signal) -> str:
    if signal.situation in SITUATION_SUMMARIES:
        return SITUATION_SUMMARIES[signal.situation]
    if signal.market_state:
        return f"{_format_timeframe(signal.timeframe)} 기준 {signal.market_state} 상태에서 발생한 알림"
    return "트레이딩 조건이 감지되었습니다."


def _format_reason(signal: Signal) -> str:
    reasons = _extract_reasons(signal)
    if not reasons:
        return "- 상세 사유 없음"
    return "\n".join(f"- {reason}" for reason in reasons)


def _extract_reasons(signal: Signal) -> list[str]:
    payload_reason = signal.payload.get("reason")
    if isinstance(payload_reason, list):
        return [str(item).lstrip("*- ").strip() for item in payload_reason if str(item).strip()]

    reasons = []
    for line in signal.message.splitlines():
        cleaned = line.lstrip("*- ").strip()
        if cleaned:
            reasons.append(cleaned)
    return reasons


def _format_timeframe(timeframe: str) -> str:
    normalized = timeframe.upper()
    if normalized in {"240", "4H", "4HR", "4HOUR"}:
        return "4H"
    return normalized


def _format_situation_field(situation: str | None) -> str:
    if not situation:
        return "-"
    return FIELD_SITUATION_LABELS.get(situation, situation)


def _format_kst(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")


def _format_market_values(signal: Signal) -> str:
    metadata = signal.payload.get("metadata")
    if not isinstance(metadata, dict):
        return ""

    items = []
    for label in ("price", "sma7", "sma21", "sma60"):
        value = metadata.get(label)
        if isinstance(value, int | float):
            items.append(f"{label.upper()} {_format_number(float(value))}")

    return " | ".join(items)


def _format_number(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:,.2f}"
    if abs(value) >= 1:
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return f"{value:,.6f}".rstrip("0").rstrip(".")
