import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.services.market_data import BinanceFuturesMarketData
from app.services.outcome_calculator import calculate_outcome
from app.services.signal_repository import (
    create_signal_outcome,
    list_trackable_signals,
    signal_outcome_exists,
)

logger = logging.getLogger(__name__)

OUTCOME_HORIZONS_HOURS = (12, 24, 48, 72)


async def record_due_outcomes(
    *,
    market_data: BinanceFuturesMarketData | None = None,
    now: datetime | None = None,
) -> int:
    current_time = now or datetime.now(timezone.utc)
    market_data = market_data or BinanceFuturesMarketData()
    recorded_count = 0

    with SessionLocal() as db:
        for signal in list_trackable_signals(db):
            if signal.entry_price is None or signal.direction is None:
                continue

            signal_time = _as_utc(signal.occurred_at)
            for horizon_hours in OUTCOME_HORIZONS_HOURS:
                target_time = signal_time + timedelta(hours=horizon_hours)
                if target_time > current_time:
                    continue
                if signal_outcome_exists(db, signal_id=signal.id, horizon_hours=horizon_hours):
                    continue

                try:
                    window = await market_data.get_price_window(
                        symbol=signal.symbol,
                        start_time=signal_time,
                        end_time=target_time,
                    )
                    if window is None:
                        continue

                    performance = calculate_outcome(
                        direction=signal.direction,
                        entry_price=signal.entry_price,
                        price_after=window.price_after,
                        max_price=window.max_price,
                        min_price=window.min_price,
                    )
                    create_signal_outcome(
                        db,
                        signal_id=signal.id,
                        horizon_hours=horizon_hours,
                        target_time=target_time,
                        evaluated_at=current_time,
                        price_after=window.price_after,
                        return_pct=performance.return_pct,
                        max_price=window.max_price,
                        min_price=window.min_price,
                        max_favorable_return_pct=performance.max_favorable_return_pct,
                        max_adverse_return_pct=performance.max_adverse_return_pct,
                    )
                    recorded_count += 1
                except Exception:
                    logger.exception(
                        "Failed to record %sh outcome for signal %s",
                        horizon_hours,
                        signal.id,
                    )

    return recorded_count


async def run_outcome_tracker(interval_seconds: int = 300) -> None:
    while True:
        try:
            await record_due_outcomes()
        except Exception:
            logger.exception("Outcome tracker loop failed")
        await asyncio.sleep(interval_seconds)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
