import asyncio

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.db.session import init_db
from app.services.outcome_tracker import run_outcome_tracker


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Assistant",
        version="0.1.0",
        description="TradingView webhook receiver and KakaoTalk alert system.",
    )

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        if settings.enable_outcome_tracking:
            asyncio.create_task(
                run_outcome_tracker(
                    interval_seconds=settings.outcome_tracker_interval_seconds,
                )
            )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()

