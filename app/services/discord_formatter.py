from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from app.schemas import SignalCreate as Signal

KST = timezone(timedelta(hours=9), name="KST")

BUY_COLOR = 0x2ECC71
SELL_COLOR = 0xE74C3C
TREND_CHANGE_COLOR = 0x3498DB
WARNING_COLOR = 0xF1C40F

SIGNAL_TEMPLATES = {
    "희귀 매수 우위": {
        "emoji": "🟢",
        "color": BUY_COLOR,
        "judgment": "장기투자 관점에서 드문 매수 우위 후보입니다. 즉시 진입이 아니라 확인용 알림입니다.",
    },
    "희귀 매도 우위": {
        "emoji": "🔴",
        "color": SELL_COLOR,
        "judgment": "장기투자 관점에서 드문 리스크 관리 또는 매도 우위 후보입니다. 포지션 점검용 알림입니다.",
    },
    "희귀 기술적 우위": {
        "emoji": "🟡",
        "color": WARNING_COLOR,
        "judgment": "자주 오지 않는 기술적 위치입니다. 차트 확인 가치가 있는 구간입니다.",
    },
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
    "21선 눌림": "4시간봉 상승 추세에서 SMA21이 가격을 아래에서 지지하고 재접근했습니다.",
    "60선 눌림": "4시간봉 상승 추세에서 장기 기준선 SMA60 부근까지 눌림이 발생했습니다.",
    "21선 저항": "4시간봉 하락 추세에서 SMA21이 가격을 위에서 저항하고 재접근했습니다.",
    "60선 저항": "4시간봉 하락 추세에서 장기 기준선 SMA60 부근 저항이 발생했습니다.",
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
            f"📈 **상황**\n{_summary_for_signal(signal)}",
            f"🎯 **판단**\n{_judgment_for_signal(signal, template)}",
            f"🔷 **이유**\n{_format_reason(signal)}",
        ]
    )

    embed: dict[str, Any] = {
        "title": title,
        "description": description,
        "color": template["color"],
        "fields": [
            {"name": "📊 상세 정보", "value": "아래 값은 신호 발생 시점 기준입니다.", "inline": False},
            {"name": "Timeframe", "value": _format_timeframe(signal.timeframe), "inline": True},
            {"name": "State", "value": signal.market_state or "-", "inline": True},
            {"name": "Situation", "value": _format_situation_field(signal.situation), "inline": True},
            {
                "name": "현재가 (Last Price)",
                "value": _format_price_usdt(signal.current_price or signal.entry_price),
                "inline": True,
            },
            {"name": "SMA7", "value": _format_optional_number(signal.sma7), "inline": True},
            {"name": "SMA21", "value": _format_optional_number(signal.sma21), "inline": True},
            {"name": "SMA60", "value": _format_optional_number(signal.sma60), "inline": True},
            {"name": "SMA21 대비", "value": _format_ma_distance(signal, signal.sma21), "inline": True},
            {"name": "Signal ID", "value": str(signal.id or "-"), "inline": True},
            {"name": "Signal Time (KST)", "value": _format_kst(signal.occurred_at), "inline": True},
            {
                "name": "⏳ 성과 추적 예정",
                "value": (
                    "이 신호는 가상 진입 후 아래 시간 기준으로 성과를 추적합니다.\n"
                    "12시간 후 / 24시간 후 / 48시간 후 / 72시간 후"
                ),
                "inline": False,
            },
        ],
        "footer": {"text": "본 알림은 참고용이며, 투자에 대한 최종 책임은 본인에게 있습니다."},
    }

    values = _format_market_values(signal)
    if values:
        embed["fields"].append({"name": "Raw Values", "value": values, "inline": False})

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
    edge_rule = signal.payload.get("edge_rule")
    if isinstance(edge_rule, dict) and edge_rule.get("thesis"):
        return str(edge_rule["thesis"])
    if signal.situation in SITUATION_SUMMARIES:
        return SITUATION_SUMMARIES[signal.situation]
    if signal.market_state:
        return f"{_format_timeframe(signal.timeframe)} 기준 {signal.market_state} 상태에서 발생한 알림"
    return "트레이딩 조건이 감지되었습니다."


def _judgment_for_signal(signal: Signal, template: dict[str, Any]) -> str:
    edge_rule = signal.payload.get("edge_rule")
    if isinstance(edge_rule, dict) and edge_rule.get("judgment"):
        return str(edge_rule["judgment"])
    return str(template["judgment"])


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
    return value.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")


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


def _format_optional_number(value: float | None) -> str:
    if value is None:
        return "-"
    return _format_number(value)


def _format_price_usdt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{_format_number(value)} USDT"


def _format_ma_distance(signal: Signal, moving_average: float | None) -> str:
    price = signal.current_price or signal.entry_price
    if price is None or moving_average in (None, 0):
        return "-"
    value = (price - moving_average) / moving_average * 100
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"
