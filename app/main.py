from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.db.session import init_db


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Assistant",
        version="0.1.0",
        description="TradingView webhook receiver and KakaoTalk alert system.",
    )

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()

