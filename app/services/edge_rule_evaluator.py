from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas import TradingViewWebhookPayload
from app.services.edge_alert_rules import evaluate_edge_alert_rules, list_edge_alert_rules
from app.services.edge_market_data import YahooEdgeMarketData
from app.services.notifier import NotificationService
from app.services.signal_repository import create_signal, has_recent_duplicate_signal


async def evaluate_saved_edge_rules(
    db: Session,
    *,
    market_data: YahooEdgeMarketData | None = None,
    notifier: NotificationService | None = None,
) -> dict[str, int]:
    market_data = market_data or YahooEdgeMarketData()
    notifier = notifier or NotificationService()
    rules = [rule for rule in list_edge_alert_rules(db) if rule["enabled"]]
    evaluated_count = 0
    matched_count = 0
    created_count = 0
    skipped_duplicate_count = 0
    failed_count = 0
    errors: list[str] = []

    for rule in rules:
        evaluated_count += 1
        try:
            snapshot = await market_data.get_snapshot(
                symbol=rule["symbol"],
                timeframe=rule["timeframe"],
                ma_type=rule["ma_type"],
                ma_period=rule["ma_period"],
            )
            if snapshot is None:
                continue

            payload = TradingViewWebhookPayload(
                symbol=rule["symbol"],
                timeframe=rule["timeframe"],
                event="server_edge_evaluation",
                message=f"{rule['name']} evaluation",
                price=snapshot.close,
                occurred_at=snapshot.occurred_at,
                data={snapshot.ma_key: snapshot.moving_average, "close": snapshot.close},
            )
            matches = [
                (candidate_rule, signal)
                for candidate_rule, signal in evaluate_edge_alert_rules(db, payload)
                if candidate_rule.id == rule["id"]
            ]
            matched_count += len(matches)

            for candidate_rule, signal in matches:
                if has_recent_duplicate_signal(
                    db,
                    symbol=signal.symbol,
                    timeframe=signal.timeframe,
                    strategy_name=signal.strategy_name,
                    dedupe_key=signal.dedupe_key,
                    market_state=signal.market_state,
                    occurred_at=signal.occurred_at,
                    cooldown_hours=candidate_rule.cooldown_hours,
                ):
                    skipped_duplicate_count += 1
                    continue

                saved_signal = create_signal(db, signal)
                signal.id = saved_signal.id
                await notifier.send_signal(signal)
                created_count += 1
        except Exception:
            failed_count += 1
            errors.append(f"{rule['symbol']} {rule['timeframe']} {rule['ma_type']}{rule['ma_period']}")

    result = {
        "rules_evaluated": evaluated_count,
        "rules_matched": matched_count,
        "signals_created": created_count,
        "duplicates_skipped": skipped_duplicate_count,
        "rules_failed": failed_count,
    }
    if errors:
        result["errors"] = errors[:5]
    return result


async def run_edge_rule_evaluator(interval_seconds: int = 3600) -> None:
    while True:
        with SessionLocal() as db:
            await evaluate_saved_edge_rules(db)
        await asyncio.sleep(interval_seconds)
