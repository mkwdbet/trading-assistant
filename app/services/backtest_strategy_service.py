import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conditions.registry import normalize_entry_conditions
from app.db.models import BacktestRun, BacktestStrategy


def save_backtest_strategy(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Strategy name is required")

    conditions = normalize_entry_conditions(
        payload.get("entry_conditions")
        if "entry_conditions" in payload
        else payload.get("conditions", [])
    )
    risk = _normalize_risk(payload.get("risk") or payload)
    row = db.scalar(select(BacktestStrategy).where(BacktestStrategy.name == name))
    if row is None:
        row = BacktestStrategy(
            name=name,
            symbol=payload.get("symbol", "BTCUSDT.P"),
            direction=payload.get("direction", "BOTH"),
            timeframe=payload.get("timeframe", "4h"),
            conditions_json=json.dumps(conditions),
            risk_json=json.dumps(risk),
        )
        db.add(row)
    else:
        row.symbol = payload.get("symbol", row.symbol)
        row.direction = payload.get("direction", row.direction)
        row.timeframe = payload.get("timeframe", row.timeframe)
        row.conditions_json = json.dumps(conditions)
        row.risk_json = json.dumps(risk)
        row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)
    return _strategy_to_dict(row)


def list_backtest_strategies(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    rows = db.scalars(select(BacktestStrategy).order_by(BacktestStrategy.updated_at.desc()).limit(limit))
    return [_strategy_to_dict(row) for row in rows]


def delete_backtest_strategy(db: Session, strategy_id: int) -> bool:
    row = db.get(BacktestStrategy, strategy_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def build_backtest_strategy_performance(db: Session) -> list[dict[str, Any]]:
    strategies = list_backtest_strategies(db, limit=300)
    rows: list[dict[str, Any]] = []
    for strategy in strategies:
        runs = list(db.scalars(select(BacktestRun).where(BacktestRun.name == strategy["name"])))
        metrics = [json.loads(run.metrics_json) for run in runs]
        rows.append(
            {
                "id": strategy["id"],
                "name": strategy["name"],
                "symbol": strategy["symbol"],
                "direction": strategy["direction"],
                "timeframe": strategy["timeframe"],
                "run_count": len(runs),
                "total_trades": sum(int(item.get("total_trades") or 0) for item in metrics),
                "avg_return_pct": _avg_metric(metrics, "avg_return_pct"),
                "avg_win_rate_pct": _avg_metric(metrics, "win_rate_pct"),
                "avg_profit_factor": _avg_metric(metrics, "profit_factor"),
                "worst_mdd_pct": _min_metric(metrics, "mdd_pct"),
                "max_consecutive_losses": max(
                    [int(item.get("max_consecutive_losses") or 0) for item in metrics],
                    default=0,
                ),
                "last_run_at": max(
                    [run.created_at.isoformat() for run in runs if run.created_at],
                    default=None,
                ),
            }
        )
    return rows


def _normalize_risk(payload: dict[str, Any]) -> dict[str, float | int]:
    return {
        "sl_atr_multiplier": float(payload.get("sl_atr_multiplier", payload.get("atr_multiplier", 1.5))),
        "risk_reward_ratio": float(payload.get("risk_reward_ratio", 2.0)),
        "max_holding_hours": int(payload.get("max_holding_hours", 24)),
    }


def _avg_metric(metrics: list[dict[str, Any]], key: str) -> float | None:
    values = [float(item[key]) for item in metrics if item.get(key) is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _min_metric(metrics: list[dict[str, Any]], key: str) -> float | None:
    values = [float(item[key]) for item in metrics if item.get(key) is not None]
    if not values:
        return None
    return min(values)


def _strategy_to_dict(row: BacktestStrategy) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "symbol": row.symbol,
        "direction": row.direction,
        "timeframe": row.timeframe,
        "conditions": json.loads(row.conditions_json),
        "risk": json.loads(row.risk_json),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
