from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from app.schemas import SignalCreate as Signal

KST = timezone(timedelta(hours=9), name="KST")

BUY_COLOR = 0x2ECC71
SELL_COLOR = 0xE74C3C
WATCH_COLOR = 0xF1C40F

SIGNAL_TEMPLATES = {
    "희귀 매수 우위": {
        "emoji": "🟢",
        "color": BUY_COLOR,
        "judgment": "장기투자 관점에서 확인할 가치가 있는 매수 관심 구간입니다. 즉시 진입이 아니라 차트 확인용 알림입니다.",
    },
    "희귀 매도 우위": {
        "emoji": "🔴",
        "color": SELL_COLOR,
        "judgment": "리스크 관리나 비중 조절 관점에서 확인할 가치가 있는 구간입니다.",
    },
    "희귀 기술적 우위": {
        "emoji": "🟡",
        "color": WATCH_COLOR,
        "judgment": "자주 오지 않는 기술적 위치입니다. 방향성 판단 전에 차트를 확인하세요.",
    },
}


def format_discord_signal_embed(signal: Signal) -> dict[str, Any]:
    template = _template_for_signal(signal.signal_type)
    description = "\n\n".join(
        [
            f"**상황**\n{_summary_for_signal(signal)}",
            f"**판단**\n{_judgment_for_signal(signal, template)}",
            f"**이유**\n{_format_reason(signal)}",
        ]
    )

    fields = [
        {"name": "Timeframe", "value": _format_timeframe(signal.timeframe), "inline": True},
        {"name": "State", "value": signal.market_state or "RARE_EDGE", "inline": True},
        {"name": "Situation", "value": signal.situation or "-", "inline": True},
        {"name": "Strategy", "value": signal.strategy_name, "inline": True},
        {"name": "Price", "value": _format_price(signal.current_price or signal.entry_price), "inline": True},
        {"name": "Occurred At", "value": f"{_format_kst(signal.occurred_at)} KST", "inline": True},
    ]

    return {
        "title": f"{template['emoji']} {signal.symbol} | {signal.signal_type}",
        "description": description,
        "color": template["color"],
        "fields": fields,
        "footer": {"text": "Long-Term Edge Radar"},
    }


def _template_for_signal(signal_type: str) -> dict[str, Any]:
    if signal_type in SIGNAL_TEMPLATES:
        return SIGNAL_TEMPLATES[signal_type]
    if "Overbought" in signal_type:
        return SIGNAL_TEMPLATES["희귀 매도 우위"]
    if "Oversold" in signal_type or "Drawdown" in signal_type:
        return SIGNAL_TEMPLATES["희귀 매수 우위"]
    if "매수" in signal_type:
        return SIGNAL_TEMPLATES["희귀 매수 우위"]
    if "매도" in signal_type:
        return SIGNAL_TEMPLATES["희귀 매도 우위"]
    return SIGNAL_TEMPLATES["희귀 기술적 우위"]


def _summary_for_signal(signal: Signal) -> str:
    edge_rule = signal.payload.get("edge_rule")
    if isinstance(edge_rule, dict) and edge_rule.get("thesis"):
        return str(edge_rule["thesis"])
    if signal.situation:
        return f"{_format_timeframe(signal.timeframe)} {signal.symbol} {signal.situation}"
    return f"{_format_timeframe(signal.timeframe)} {signal.symbol} 장기 기술적 조건이 감지되었습니다."


def _judgment_for_signal(signal: Signal, template: dict[str, Any]) -> str:
    edge_rule = signal.payload.get("edge_rule")
    if isinstance(edge_rule, dict) and edge_rule.get("judgment"):
        return str(edge_rule["judgment"])
    return str(template["judgment"])


def _format_reason(signal: Signal) -> str:
    reasons = _extract_reasons(signal)
    if not reasons:
        return "- 상세 이유 없음"
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
    return {"1W": "1W", "W": "1W", "1D": "1D", "D": "1D", "4H": "4H", "240": "4H"}.get(
        normalized,
        normalized,
    )


def _format_kst(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(KST).strftime("%Y-%m-%d %H:%M")


def _format_price(value: float | None) -> str:
    if value is None:
        return "-"
    if abs(value) >= 100:
        return f"{value:,.2f}"
    if abs(value) >= 1:
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return f"{value:,.6f}".rstrip("0").rstrip(".")
