from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EdgeAlertRule
from app.schemas import SignalCreate, TradingViewWebhookPayload

STRATEGY_NAME = "rare_edge_rules"


def list_edge_alert_rules(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(EdgeAlertRule).order_by(EdgeAlertRule.updated_at.desc()))
    return [_rule_to_dict(row) for row in rows]


def create_edge_alert_rule(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    rule = EdgeAlertRule(
        name=_required_text(payload, "name"),
        symbol=_normalize_symbol(_required_text(payload, "symbol")),
        timeframe=_normalize_timeframe(_required_text(payload, "timeframe")),
        direction=str(payload.get("direction") or "LONG").upper(),
        ma_type=str(payload.get("ma_type") or "sma").lower(),
        ma_period=int(payload.get("ma_period") or 60),
        tolerance_pct=float(payload.get("tolerance_pct") or 0.005),
        thesis=str(payload.get("thesis") or "").strip(),
        judgment=str(payload.get("judgment") or "").strip(),
        enabled=1 if payload.get("enabled", True) else 0,
        cooldown_hours=int(payload.get("cooldown_hours") or 168),
    )
    _validate_rule(rule)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_to_dict(rule)


def delete_edge_alert_rule(db: Session, rule_id: int) -> bool:
    row = db.get(EdgeAlertRule, rule_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def evaluate_edge_alert_rules(
    db: Session,
    payload: TradingViewWebhookPayload,
) -> list[tuple[EdgeAlertRule, SignalCreate]]:
    rules = db.scalars(select(EdgeAlertRule).where(EdgeAlertRule.enabled == 1))
    matches: list[tuple[EdgeAlertRule, SignalCreate]] = []
    for rule in rules:
        signal = _evaluate_rule(rule, payload)
        if signal is not None:
            matches.append((rule, signal))
    return matches


def _evaluate_rule(
    rule: EdgeAlertRule,
    payload: TradingViewWebhookPayload,
) -> SignalCreate | None:
    if not _symbol_matches(rule.symbol, payload.symbol):
        return None
    if _normalize_timeframe(payload.timeframe) != rule.timeframe:
        return None

    price = _to_float(payload.price, payload.data.get("close"))
    moving_average = _extract_moving_average(payload.data, rule.ma_type, rule.ma_period)
    if price is None or moving_average in (None, 0):
        return None

    distance_pct = abs(price - moving_average) / moving_average
    if distance_pct > rule.tolerance_pct:
        return None

    signal_type = _signal_type_for(rule)
    situation = f"{rule.ma_type.upper()}{rule.ma_period} {'지지' if rule.direction == 'LONG' else '저항'}"
    reasons = _reasons_for(rule, price=price, moving_average=moving_average, distance_pct=distance_pct)
    metadata = {
        "price": price,
        f"{rule.ma_type}{rule.ma_period}": moving_average,
        "distance_pct": distance_pct * 100,
        "rule_id": rule.id,
        "rule_name": rule.name,
    }

    return SignalCreate(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        strategy_name=STRATEGY_NAME,
        signal_type=signal_type,
        direction=rule.direction if rule.direction in {"LONG", "SHORT"} else None,
        analysis_signal_type=f"rare_{rule.ma_type}{rule.ma_period}_touch",
        market_state="RARE_EDGE",
        situation=situation,
        dedupe_key=f"edge_rule_{rule.id}_{rule.ma_type}{rule.ma_period}_touch",
        entry_price=price,
        current_price=price,
        message="\n".join(f"* {reason}" for reason in reasons),
        occurred_at=payload.occurred_at,
        payload={
            "tradingview": payload.model_dump(mode="json"),
            "reason": reasons,
            "metadata": metadata,
            "edge_rule": _rule_to_dict(rule),
        },
    )


def _signal_type_for(rule: EdgeAlertRule) -> str:
    if rule.direction == "LONG":
        return "희귀 매수 우위"
    if rule.direction == "SHORT":
        return "희귀 매도 우위"
    return "희귀 기술적 우위"


def _reasons_for(
    rule: EdgeAlertRule,
    *,
    price: float,
    moving_average: float,
    distance_pct: float,
) -> list[str]:
    reasons = [
        f"{_format_timeframe_label(rule.timeframe)} {rule.symbol} 가격이 {rule.ma_type.upper()}{rule.ma_period}에 재접근",
        f"현재가 {price:,.2f}, 기준선 {moving_average:,.2f}, 이격 {distance_pct * 100:.2f}%",
        rule.thesis or "장기투자 관점에서 드문 기술적 우위 구간",
    ]
    return reasons


def _extract_moving_average(data: dict[str, Any], ma_type: str, period: int) -> float | None:
    candidates = [
        f"{ma_type}{period}",
        f"{ma_type}_{period}",
        f"{ma_type.upper()}{period}",
        f"{ma_type.upper()}_{period}",
    ]
    for key in candidates:
        value = _to_float(data.get(key))
        if value is not None:
            return value
    return None


def _symbol_matches(rule_symbol: str, payload_symbol: str) -> bool:
    normalized_payload = _normalize_symbol(payload_symbol)
    normalized_rule = _normalize_symbol(rule_symbol)
    return normalized_payload == normalized_rule or normalized_payload.endswith(f":{normalized_rule}")


def _normalize_symbol(value: str) -> str:
    return value.strip().upper()


def _normalize_timeframe(value: str) -> str:
    normalized = str(value).strip()
    aliases = {
        "W": "1w",
        "1W": "1w",
        "WEEK": "1w",
        "D": "1d",
        "1D": "1d",
        "240": "4h",
        "4H": "4h",
    }
    return aliases.get(normalized.upper(), normalized)


def _format_timeframe_label(value: str) -> str:
    return {"1w": "주봉", "1d": "일봉", "4h": "4시간봉"}.get(value, value)


def _to_float(*values: object) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _validate_rule(rule: EdgeAlertRule) -> None:
    if rule.direction not in {"LONG", "SHORT", "WATCH"}:
        raise ValueError("direction must be LONG, SHORT, or WATCH")
    if rule.ma_type != "sma":
        raise ValueError("Only SMA rules are supported in MVP")
    if rule.ma_period <= 0:
        raise ValueError("ma_period must be positive")
    if rule.tolerance_pct < 0:
        raise ValueError("tolerance_pct must be zero or positive")
    if rule.cooldown_hours < 1:
        raise ValueError("cooldown_hours must be at least 1")
    if not rule.judgment:
        rule.judgment = "장기투자 관점에서 희귀한 기술적 우위 후보입니다. 즉시 진입이 아니라 확인용 알림입니다."


def _rule_to_dict(row: EdgeAlertRule) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "direction": row.direction,
        "ma_type": row.ma_type,
        "ma_period": row.ma_period,
        "tolerance_pct": row.tolerance_pct,
        "thesis": row.thesis,
        "judgment": row.judgment,
        "enabled": bool(row.enabled),
        "cooldown_hours": row.cooldown_hours,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
