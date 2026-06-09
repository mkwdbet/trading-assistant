from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas import SignalCreate, SignalRead, TradingViewWebhookPayload
from app.services.notifier import NotificationService
from app.services.outcome_tracker import record_due_outcomes
from app.services.signal_repository import (
    create_signal,
    get_strategy_state,
    has_recent_duplicate_signal,
    list_signals,
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

    return {
        "signals_created": created_count,
        "duplicates_skipped": skipped_duplicate_count,
    }


@router.get("/signals", response_model=list[SignalRead], tags=["signals"])
def get_signals(
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy_name: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SignalRead]:
    return list_signals(
        db=db,
        symbol=symbol,
        timeframe=timeframe,
        strategy_name=strategy_name,
        limit=limit,
    )


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
