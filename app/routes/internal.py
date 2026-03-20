import base64
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.db import SessionLocal
from app.services.sync_service import run_sync
from app.services.brief_service import render_and_publish_all_briefs
from app.services.auth_service import upsert_vip_user
from app.services.pricing_service import get_user_monthly_topic_pricing


router = APIRouter(prefix="/internal", tags=["internal"])


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _verify_vip_token(token: str, *, expected_audience: str) -> dict:
    secret = (settings.vip_sso_shared_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="VIP shared secret missing")
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token format")
    expected = base64.urlsafe_b64encode(
        hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    if not hmac.compare_digest(expected, sig_b64):
        raise HTTPException(status_code=401, detail="Invalid token signature")
    try:
        claims = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token payload")
    now = int(time.time())
    if claims.get("iss") != settings.vip_sso_issuer:
        raise HTTPException(status_code=401, detail="Invalid token issuer")
    if claims.get("aud") != expected_audience:
        raise HTTPException(status_code=401, detail="Invalid token audience")
    if int(claims.get("exp") or 0) < now:
        raise HTTPException(status_code=401, detail="Token expired")
    return claims




@router.post("/render-publish-briefs")
def internal_render_publish_briefs(x_sync_secret: str | None = Header(default=None)):
    if x_sync_secret != settings.sync_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with SessionLocal() as db:
        result = render_and_publish_all_briefs(db)
    return {"ok": True, **result}


@router.post("/pipeline-hourly")
def internal_pipeline_hourly(x_sync_secret: str | None = Header(default=None)):
    if x_sync_secret != settings.sync_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with SessionLocal() as db:
        sync_result = run_sync(db, triggered_by="internal-hourly")
        brief_result = render_and_publish_all_briefs(db)
    return {"ok": True, "sync": sync_result, "briefs": brief_result}

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


@router.get("/vip/user-pricing")
def internal_vip_user_pricing(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    claims = _verify_vip_token(authorization.split(" ", 1)[1].strip(), expected_audience="reserse-pricing")
    with SessionLocal() as db:
        summary = get_user_monthly_topic_pricing(
            db,
            email=str(claims.get("email") or "").strip().lower() or None,
            username=str(claims.get("username") or "").strip() or None,
        )
    return {"ok": True, **summary}
