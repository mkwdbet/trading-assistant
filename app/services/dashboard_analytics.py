from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import EdgeAlertRule, Signal


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


def build_settings_summary() -> dict[str, Any]:
    return {
        "product": {
            "name": "Long-Term Edge Radar",
            "mode": "rare_edge_alerts_only",
        },
        "discord": {
            "enabled": settings.enable_discord_notifications,
            "configured": bool(settings.discord_webhook_url),
            "masked_webhook": _mask_secret(settings.discord_webhook_url),
        },
        "edge_rule_evaluator": {
            "enabled": settings.enable_edge_rule_evaluator,
            "interval_seconds": settings.edge_rule_evaluator_interval_seconds,
        },
    }


def _signals(db: Session) -> list[Signal]:
    return list(db.scalars(select(Signal).order_by(Signal.occurred_at.asc())))


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


def _count_since(signals: list[Signal], cutoff: datetime) -> int:
    cutoff = _utc(cutoff)
    return sum(1 for signal in signals if _utc(signal.occurred_at) >= cutoff)


def _mask_secret(value: str) -> str | None:
    if not value:
        return None
    return f"{value[:30]}...{value[-6:]}"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
