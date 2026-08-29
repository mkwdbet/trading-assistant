from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas import SignalCreate, TradingViewWebhookPayload
from app.services.dashboard_analytics import (
    build_dashboard_summary,
    build_settings_summary,
    build_signal_detail,
    build_signal_rows,
)
from app.services.edge_alert_rules import (
    create_edge_alert_rule,
    delete_edge_alert_rule,
    evaluate_edge_alert_rules,
    list_edge_alert_rules,
)
from app.services.edge_rule_evaluator import evaluate_saved_edge_rules
from app.services.notifier import NotificationService
from app.services.signal_repository import create_signal, has_recent_duplicate_signal

router = APIRouter()


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


@router.post("/webhooks/tradingview/{secret}", tags=["webhooks"])
async def tradingview_webhook(
    secret: str,
    payload: TradingViewWebhookPayload,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    if secret != settings.tradingview_webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")

    notifier = NotificationService()
    created_count = 0
    skipped_duplicate_count = 0

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
def get_dashboard(db: Session = Depends(get_db)) -> dict:
    return build_dashboard_summary(db)


@router.get("/signals", tags=["signals"])
def get_signals(
    symbol: str | None = None,
    timeframe: str | None = None,
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


@router.get("/settings", tags=["dashboard"])
def get_settings_summary() -> dict:
    return build_settings_summary()


@router.post("/notifications/discord/test", tags=["notifications"])
async def post_discord_test_notification() -> dict[str, str]:
    if not settings.enable_discord_notifications:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord notifications are disabled.",
        )
    if not settings.discord_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DISCORD_WEBHOOK_URL is not configured.",
        )

    signal = SignalCreate(
        symbol="SYSTEM",
        timeframe="test",
        strategy_name="long_term_edge_radar",
        signal_type="희귀 기술적 우위",
        market_state="SYSTEM_CHECK",
        situation="Discord 연결 확인",
        dedupe_key=None,
        message="Discord alert path is connected.",
        occurred_at=datetime.now(timezone.utc),
        payload={
            "reason": ["웹 대시보드에서 보낸 테스트 알림", "Discord webhook 연결 확인"],
            "edge_rule": {
                "thesis": "Long-Term Edge Radar 알림 경로 테스트",
                "judgment": "이 메시지가 보이면 저장된 신호 발생 시 Discord 알림을 받을 수 있습니다.",
            },
        },
    )
    await NotificationService().send_signal(signal)
    return {"status": "sent"}
