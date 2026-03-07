from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.db import SessionLocal
from app.services.sync_service import run_sync


router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/sync-rss")
def internal_sync_rss(x_sync_secret: str | None = Header(default=None)):
    if x_sync_secret != settings.sync_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with SessionLocal() as db:
        result = run_sync(db, triggered_by="internal")
    return {"ok": True, **result}
