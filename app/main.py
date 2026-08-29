import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.db.session import init_db
from app.services.edge_rule_evaluator import run_edge_rule_evaluator


def create_app() -> FastAPI:
    app = FastAPI(
        title="Long-Term Edge Radar",
        version="0.2.0",
        description="Personal long-term investing radar for rare technical edge alerts.",
    )

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        if settings.enable_edge_rule_evaluator:
            asyncio.create_task(
                run_edge_rule_evaluator(
                    interval_seconds=settings.edge_rule_evaluator_interval_seconds,
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
