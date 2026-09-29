import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import EdgeAlertRule, Signal
from app.services.runtime_settings import get_discord_webhook_url, mask_secret


def build_dashboard_summary(db: Session, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    signals = _signals(db)
    rules = list(db.scalars(select(EdgeAlertRule).order_by(EdgeAlertRule.updated_at.desc())))

    return {
        "counts": {
            "active_rules": sum(1 for rule in rules if rule.enabled),
            "total_rules": len(rules),
            "total_signals": len(signals),
            "signals_30d": _count_since(signals, now - timedelta(days=30)),
        },
        "latest_signal": _signal_row(signals[-1])["signal"] if signals else None,
        "rule_summaries": _rule_summaries(rules, signals, now=now),
        "rules_by_timeframe": dict(Counter(rule.timeframe for rule in rules)),
        "signals_by_symbol": dict(Counter(signal.symbol for signal in signals)),
        "recent_signals": [_signal_row(signal)["signal"] for signal in reversed(signals[-10:])],
    }


def build_signal_rows(
    db: Session,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    direction: str | None = None,
    signal_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(Signal).order_by(Signal.occurred_at.desc()).limit(limit)
    if symbol:
        stmt = stmt.where(Signal.symbol == symbol.upper())
    if timeframe:
        stmt = stmt.where(Signal.timeframe == timeframe)
    if direction:
        stmt = stmt.where(Signal.direction == direction.upper())
    if signal_type:
        stmt = stmt.where(Signal.analysis_signal_type == signal_type)
    if start:
        stmt = stmt.where(Signal.occurred_at >= start)
    if end:
        stmt = stmt.where(Signal.occurred_at <= end)

    return [_signal_row(signal) for signal in db.scalars(stmt)]


def build_signal_detail(db: Session, signal_id: int) -> dict[str, Any] | None:
    signal = db.get(Signal, signal_id)
    if signal is None:
        return None
    return _signal_row(signal)


def build_settings_summary(db: Session | None = None) -> dict[str, Any]:
    discord_webhook_url = get_discord_webhook_url(db)
    return {
        "product": {
            "name": "Long-Term Edge Radar",
            "mode": "rare_edge_alerts_only",
        },
        "discord": {
            "enabled": settings.enable_discord_notifications,
            "configured": bool(discord_webhook_url),
            "masked_webhook": mask_secret(discord_webhook_url),
        },
        "edge_rule_evaluator": {
            "enabled": settings.enable_edge_rule_evaluator,
            "interval_seconds": settings.edge_rule_evaluator_interval_seconds,
        },
    }


def _signals(db: Session) -> list[Signal]:
    return list(db.scalars(select(Signal).order_by(Signal.occurred_at.asc())))


def _rule_summaries(
    rules: list[EdgeAlertRule],
    signals: list[Signal],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    cutoff_30d = now - timedelta(days=30)
    signals_by_rule: dict[int, list[Signal]] = defaultdict(list)
    for signal in signals:
        rule_id = _rule_id_from_signal(signal)
        if rule_id is not None:
            signals_by_rule[rule_id].append(signal)

    summaries = []
    for rule in rules:
        rule_signals = signals_by_rule.get(rule.id, [])
        latest = rule_signals[-1] if rule_signals else None
        summaries.append(
            {
                "id": rule.id,
                "name": rule.name,
                "symbol": rule.symbol,
                "timeframe": rule.timeframe,
                "direction": rule.direction,
                "rule": f"{rule.ma_type.upper()}{rule.ma_period} touch",
                "tolerance_pct": rule.tolerance_pct,
                "cooldown_hours": rule.cooldown_hours,
                "enabled": bool(rule.enabled),
                "status": "watching" if rule.enabled else "paused",
                "signal_count": len(rule_signals),
                "signals_30d": sum(1 for signal in rule_signals if _utc(signal.occurred_at) >= _utc(cutoff_30d)),
                "last_signal_at": latest.occurred_at.isoformat() if latest else None,
                "last_price": latest.current_price or latest.entry_price if latest else None,
                "last_situation": latest.situation if latest else None,
            }
        )

    return summaries


def _signal_row(signal: Signal) -> dict[str, Any]:
    return {
        "signal": {
            "id": signal.id,
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            "strategy_name": signal.strategy_name,
            "signal_type": signal.signal_type,
            "analysis_signal_type": signal.analysis_signal_type,
            "direction": signal.direction,
            "market_state": signal.market_state,
            "situation": signal.situation,
            "entry_price": signal.entry_price,
            "current_price": signal.current_price,
            "sma7": signal.sma7,
            "sma21": signal.sma21,
            "sma60": signal.sma60,
            "message": signal.message,
            "payload": signal.payload_json,
            "occurred_at": signal.occurred_at.isoformat(),
            "created_at": signal.created_at.isoformat() if signal.created_at else None,
        }
    }


def _rule_id_from_signal(signal: Signal) -> int | None:
    try:
        payload = json.loads(signal.payload_json)
    except (TypeError, json.JSONDecodeError):
        return None
    edge_rule = payload.get("edge_rule") if isinstance(payload, dict) else None
    if not isinstance(edge_rule, dict):
        return None
    try:
        return int(edge_rule["id"])
    except (KeyError, TypeError, ValueError):
        return None


def _count_since(signals: list[Signal], cutoff: datetime) -> int:
    cutoff = _utc(cutoff)
    return sum(1 for signal in signals if _utc(signal.occurred_at) >= cutoff)
def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
