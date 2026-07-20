import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.db.session import init_db
from app.services.outcome_tracker import run_outcome_tracker


def create_app() -> FastAPI:
    app = FastAPI(
        title="AlphaForge",
        version="0.1.0",
        description="Build, backtest, and validate crypto trading strategies.",
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

    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=static_path), name="static")

        @app.get("/dashboard", include_in_schema=False)
        def dashboard() -> RedirectResponse:
            return RedirectResponse(url="/static/dashboard/index.html")

    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()

