from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.models import AppSetting
from app.db.session import SessionLocal

DISCORD_WEBHOOK_KEY = "discord_webhook_url"


def get_setting(db: Session, key: str) -> str | None:
    try:
        row = db.get(AppSetting, key)
    except SQLAlchemyError:
        return None
    if row is None or not row.value.strip():
        return None
    return row.value.strip()


def set_setting(db: Session, key: str, value: str) -> str:
    normalized = value.strip()
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=normalized)
        db.add(row)
    else:
        row.value = normalized
        row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return normalized


def get_discord_webhook_url(db: Session | None = None) -> str:
    if db is not None:
        return get_setting(db, DISCORD_WEBHOOK_KEY) or settings.discord_webhook_url

    with SessionLocal() as session:
        return get_setting(session, DISCORD_WEBHOOK_KEY) or settings.discord_webhook_url


def set_discord_webhook_url(db: Session, value: str) -> str:
    normalized = value.strip()
    if normalized and not normalized.startswith("https://discord.com/api/webhooks/"):
        raise ValueError("Discord webhook URL must start with https://discord.com/api/webhooks/")
    return set_setting(db, DISCORD_WEBHOOK_KEY, normalized)


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 12:
        return "*" * len(value)
    return f"{value[:32]}...{value[-6:]}"
