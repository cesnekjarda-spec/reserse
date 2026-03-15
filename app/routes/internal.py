from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.db import SessionLocal
from app.services.sync_service import run_sync
from app.services.auth_service import upsert_vip_user


router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/sync-rss")
def internal_sync_rss(x_sync_secret: str | None = Header(default=None)):
    if x_sync_secret != settings.sync_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with SessionLocal() as db:
        result = run_sync(db, triggered_by="internal")
    return {"ok": True, **result}


# -----------------------------------------------------------------------------
# BEGIN LEGACY_H2B_REMOTE_UPSERT_BRANCH
# Old VIP -> Reserse server-to-server provisioning bridge.
# Intentionally kept in code as a reversible fallback, but NOT the preferred
# active integration path anymore. Preferred active path is H2C-R:
# VIP signed SSO URL -> /sso/consume -> JIT upsert + session.
# Future cleanup can remove this payload model and the endpoint below together.
# -----------------------------------------------------------------------------
class VipUpsertUserPayload(BaseModel):
    email: str
    username: str
    role: str = "user"
    is_active: bool = True
    mode: str | None = None


@router.post("/vip/upsert-user")
def internal_vip_upsert_user(payload: VipUpsertUserPayload, x_vip_shared_secret: str | None = Header(default=None)):
    # LEGACY H2B endpoint: preserved only for rollback safety / temporary fallback.
    secret = (settings.vip_internal_shared_secret or settings.vip_sso_shared_secret or "").strip()
    if not secret or x_vip_shared_secret != secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with SessionLocal() as db:
        user = upsert_vip_user(
            db,
            username=payload.username.strip(),
            email=payload.email.strip().lower(),
            role="admin" if payload.role == "admin" else "user",
            is_active=bool(payload.is_active),
        )
    return {"ok": True, "user": {"id": user.id, "email": user.email, "username": user.username, "role": user.role, "is_active": user.is_active}}

# END LEGACY_H2B_REMOTE_UPSERT_BRANCH
