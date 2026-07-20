from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.conditions.registry import get_condition_registry
from app.db.session import get_db
from app.schemas import SignalCreate, TradingViewWebhookPayload
from app.services.backtest_service import (
    delete_backtest_run,
    get_backtest_run,
    list_backtest_runs,
    run_and_store_backtest,
)
from app.services.backtest_strategy_service import (
    build_backtest_strategy_performance,
    delete_backtest_strategy,
    list_backtest_strategies,
    save_backtest_strategy,
)
from app.services.dashboard_analytics import (
    build_dashboard_summary,
    build_performance_summary,
    build_research_summary,
    build_settings_summary,
    build_signal_detail,
    build_signal_rows,
    build_strategy_analysis,
)
from app.services.exit_optimizer_service import optimize_exit_backtest
from app.services.edge_alert_rules import (
    create_edge_alert_rule,
    delete_edge_alert_rule,
    evaluate_edge_alert_rules,
    list_edge_alert_rules,
)
from app.services.edge_rule_evaluator import evaluate_saved_edge_rules
from app.services.notifier import NotificationService
from app.services.outcome_tracker import record_due_outcomes
from app.services.signal_repository import (
    create_signal,
    get_strategy_state,
    has_recent_duplicate_signal,
    upsert_strategy_state,
)
from app.services.signal_stats import build_signal_stats
from app.services.stats_discord import send_stats_to_discord
from app.services.strategy_engine import StrategyEngine
from app.strategies.base import StrategyContext

router = APIRouter()


@router.get("/strategies", tags=["strategies"])
def get_strategies() -> list[dict[str, str]]:
    return StrategyEngine().list_strategies()


@router.get("/conditions", tags=["backtests"])
def get_conditions() -> list[dict]:
    return get_condition_registry()


@router.get("/edge-rules", tags=["edge-rules"])
def get_edge_rules(db: Session = Depends(get_db)) -> list[dict]:
    return list_edge_alert_rules(db)


@router.post("/edge-rules", tags=["edge-rules"])
def post_edge_rule(payload: dict, db: Session = Depends(get_db)) -> dict:
    try:
        return create_edge_alert_rule(db, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Edge rule save failed: {exc}",
        ) from exc


@router.post("/edge-rules/evaluate", tags=["edge-rules"])
async def post_evaluate_edge_rules(db: Session = Depends(get_db)) -> dict:
    return await evaluate_saved_edge_rules(db)


@router.delete("/edge-rules/{rule_id}", tags=["edge-rules"])
def delete_edge_rule_route(rule_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    if not delete_edge_alert_rule(db, rule_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge rule not found")
    return {"status": "deleted"}


@router.get("/backtests", tags=["backtests"])
def get_backtests(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_backtest_runs(db, limit=limit)


@router.get("/backtests/{run_id}", tags=["backtests"])
def get_backtest_run_route(run_id: int, db: Session = Depends(get_db)) -> dict:
    run = get_backtest_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest run not found")
    return run


@router.delete("/backtests/{run_id}", tags=["backtests"])
def delete_backtest_run_route(run_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    if not delete_backtest_run(db, run_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest run not found")
    return {"status": "deleted"}


@router.get("/backtest-strategies", tags=["backtests"])
def get_backtest_strategies(
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_backtest_strategies(db, limit=limit)


@router.get("/backtest-strategies/performance", tags=["backtests"])
def get_backtest_strategy_performance(db: Session = Depends(get_db)) -> list[dict]:
    return build_backtest_strategy_performance(db)


@router.post("/backtest-strategies", tags=["backtests"])
def post_backtest_strategy(payload: dict, db: Session = Depends(get_db)) -> dict:
    try:
        return save_backtest_strategy(db, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backtest strategy save failed: {exc}",
        ) from exc


@router.delete("/backtest-strategies/{strategy_id}", tags=["backtests"])
def delete_backtest_strategy_route(strategy_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    if not delete_backtest_strategy(db, strategy_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest strategy not found")
    return {"status": "deleted"}


@router.post("/backtests/run", tags=["backtests"])
async def post_backtest_run(payload: dict, db: Session = Depends(get_db)) -> dict:
    try:
        return await run_and_store_backtest(db, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backtest failed: {exc}",
        ) from exc


@router.post("/backtests/optimize-exit", tags=["backtests"])
async def post_optimize_exit(payload: dict) -> dict:
    try:
        return await optimize_exit_backtest(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exit optimization failed: {exc}",
        ) from exc


@router.post("/webhooks/tradingview/{secret}", tags=["webhooks"])
async def tradingview_webhook(
    secret: str,
    payload: TradingViewWebhookPayload,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    if secret != settings.tradingview_webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")

    engine = StrategyEngine()
    notifier = NotificationService()
    created_count = 0
    skipped_duplicate_count = 0
    contexts = {}

    for strategy in engine.strategies:
        previous = get_strategy_state(
            db,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            strategy_name=strategy.name,
        )
        contexts[strategy.name] = StrategyContext(
            previous_state=previous.current_state if previous else None
        )

    for strategy_signal in engine.evaluate(payload, contexts):
        if has_recent_duplicate_signal(
            db,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            strategy_name=strategy_signal.strategy_name,
            dedupe_key=strategy_signal.dedupe_key,
            market_state=strategy_signal.market_state,
            occurred_at=strategy_signal.occurred_at,
        ):
            skipped_duplicate_count += 1
            continue

        signal = SignalCreate(
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            strategy_name=strategy_signal.strategy_name,
            signal_type=strategy_signal.signal_type,
            market_state=strategy_signal.market_state,
            situation=strategy_signal.situation,
            dedupe_key=strategy_signal.dedupe_key,
            message=strategy_signal.message,
            occurred_at=strategy_signal.occurred_at,
            payload={
                "tradingview": payload.model_dump(mode="json"),
                "reason": strategy_signal.reason,
                "metadata": strategy_signal.metadata,
            },
        )
        saved_signal = create_signal(db, signal)
        signal.id = saved_signal.id
        await notifier.send_signal(signal)
        created_count += 1

    for strategy in engine.strategies:
        current_state = getattr(strategy, "last_evaluated_state", None)
        if current_state:
            upsert_strategy_state(
                db,
                symbol=payload.symbol,
                timeframe=payload.timeframe,
                strategy_name=strategy.name,
                current_state=current_state,
                payload=payload.model_dump(mode="json"),
                updated_at=payload.occurred_at,
            )

    for rule, edge_signal in evaluate_edge_alert_rules(db, payload):
        if has_recent_duplicate_signal(
            db,
            symbol=edge_signal.symbol,
            timeframe=edge_signal.timeframe,
            strategy_name=edge_signal.strategy_name,
            dedupe_key=edge_signal.dedupe_key,
            market_state=edge_signal.market_state,
            occurred_at=edge_signal.occurred_at,
            cooldown_hours=rule.cooldown_hours,
        ):
            skipped_duplicate_count += 1
            continue

        saved_signal = create_signal(db, edge_signal)
        edge_signal.id = saved_signal.id
        await notifier.send_signal(edge_signal)
        created_count += 1

    return {
        "signals_created": created_count,
        "duplicates_skipped": skipped_duplicate_count,
    }


@router.get("/dashboard", tags=["dashboard"])
def get_dashboard(
    strategy_name: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    return build_dashboard_summary(db, strategy_name=strategy_name)


@router.get("/signals", tags=["signals"])
def get_signals(
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy_name: str | None = None,
    direction: str | None = None,
    signal_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    return build_signal_rows(
        db=db,
        symbol=symbol,
        timeframe=timeframe,
        strategy_name=strategy_name,
        direction=direction,
        signal_type=signal_type,
        start=start,
        end=end,
        limit=limit,
    )


@router.get("/signals/{signal_id}", tags=["signals"])
def get_signal_detail(signal_id: int, db: Session = Depends(get_db)) -> dict:
    detail = build_signal_detail(db, signal_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")
    return detail


@router.get("/performance", tags=["dashboard"])
def get_performance(
    horizon_hours: int = Query(default=24, ge=1, le=168),
    strategy_name: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    return build_performance_summary(
        db,
        horizon_hours=horizon_hours,
        strategy_name=strategy_name,
    )


@router.get("/strategy-analysis", tags=["dashboard"])
def get_strategy_analysis(
    horizon_hours: int = Query(default=24, ge=1, le=168),
    strategy_name: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    return build_strategy_analysis(
        db,
        horizon_hours=horizon_hours,
        strategy_name=strategy_name,
    )


@router.get("/research", tags=["dashboard"])
def get_research(
    horizon_hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=20, ge=1, le=100),
    strategy_name: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    return build_research_summary(
        db,
        horizon_hours=horizon_hours,
        limit=limit,
        strategy_name=strategy_name,
    )


@router.get("/settings", tags=["dashboard"])
def get_settings_summary() -> dict:
    return build_settings_summary()


@router.get("/stats/signals", tags=["stats"])
def get_signal_stats(db: Session = Depends(get_db)) -> dict:
    return build_signal_stats(db)


@router.post("/stats/discord", tags=["stats"])
async def post_signal_stats_to_discord(db: Session = Depends(get_db)) -> dict[str, str]:
    stats = build_signal_stats(db)
    await send_stats_to_discord(stats)
    return {"status": "sent"}


@router.post("/outcomes/record-due", tags=["outcomes"])
async def post_record_due_outcomes() -> dict[str, int]:
    recorded_count = await record_due_outcomes()
    return {"outcomes_recorded": recorded_count}
