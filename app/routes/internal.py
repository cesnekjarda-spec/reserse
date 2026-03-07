from fastapi import APIRouter, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.services.sync_service import run_sync

router = APIRouter()


@router.post("/internal/sync-rss")
def sync_rss(x_sync_secret: str | None = Header(default=None)):
    if x_sync_secret != settings.sync_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    with SessionLocal() as db:
        result = run_sync(db, triggered_by="github_actions")
    return result
