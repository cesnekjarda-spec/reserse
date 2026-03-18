import base64
import hashlib
import hmac
import json
import time

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.subscription import UserTopicSubscription
from app.models.user import User
from app.services.pricing_service import get_user_monthly_topic_pricing


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _sign_vip_token(claims: dict) -> str | None:
    secret = (settings.vip_sso_shared_secret or "").strip()
    if not secret:
        return None
    payload = _b64url(json.dumps(claims, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sig = _b64url(hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def vip_pricing_sync_ready() -> bool:
    return bool((settings.vip_pricing_sync_url or '').strip() and (settings.vip_sso_shared_secret or '').strip())


def push_pricing_summary_to_vip(pricing_summary: dict, *, vip_member_id: str | None = None, sync_trigger: str = 'manual') -> dict:
    target_url = (settings.vip_pricing_sync_url or '').strip()
    if not target_url:
        return {'ok': False, 'status': 'sync_url_missing'}
    token = _sign_vip_token({
        'iss': settings.vip_sso_issuer,
        'aud': 'vip-research-pricing-sync',
        'iat': int(time.time()),
        'exp': int(time.time()) + 120,
        'email': str(pricing_summary.get('email') or '').strip().lower(),
        'username': str(pricing_summary.get('username') or '').strip(),
        'vip_member_id': str(vip_member_id or '').strip(),
        'scope': 'pricing:write',
        'mode': 'reserse_push_sync',
        'trigger': sync_trigger,
    })
    if not token:
        return {'ok': False, 'status': 'shared_secret_missing'}
    payload = dict(pricing_summary or {})
    payload['vip_member_id'] = str(vip_member_id or '').strip() or None
    payload['sync_trigger'] = sync_trigger
    payload['last_synced_at'] = payload.get('last_synced_at') or None
    try:
        response = requests.post(
            target_url,
            headers={
    'X-Access-Token': f'Bearer {token}',
    'Content-Type': 'application/json',
},
            json=payload,
            timeout=max(3, int(settings.vip_pricing_sync_timeout_seconds or 12)),
        )
    except Exception as exc:
        return {'ok': False, 'status': 'request_failed', 'detail': str(exc)}
    body_text = response.text or ''
    try:
        body_json = response.json() if body_text.strip() else {}
    except Exception:
        body_json = {}
    if response.status_code != 200:
        return {
            'ok': False,
            'status': 'remote_error',
            'http_status': response.status_code,
            'detail': (body_text or '')[:500],
        }
    return {
        'ok': True,
        'status': 'synced',
        'http_status': response.status_code,
        'stored': body_json.get('stored') if isinstance(body_json, dict) else None,
    }


def push_user_pricing_to_vip(db: Session, user: User | None, *, vip_member_id: str | None = None, sync_trigger: str = 'manual') -> dict:
    if not user:
        return {'ok': False, 'status': 'user_missing'}
    summary = get_user_monthly_topic_pricing(db, user_id=user.id)
    summary['email'] = user.email
    summary['username'] = user.username
    return push_pricing_summary_to_vip(summary, vip_member_id=vip_member_id, sync_trigger=sync_trigger)


def push_pricing_for_identity(db: Session, *, email: str | None = None, username: str | None = None, vip_member_id: str | None = None, sync_trigger: str = 'manual') -> dict:
    stmt = select(User)
    if email:
        stmt = stmt.where(User.email == str(email).strip().lower())
    elif username:
        stmt = stmt.where(User.username == str(username).strip())
    else:
        return {'ok': False, 'status': 'missing_identity'}
    user = db.scalar(stmt.limit(1))
    return push_user_pricing_to_vip(db, user, vip_member_id=vip_member_id, sync_trigger=sync_trigger)


def push_pricing_for_topic_subscribers(db: Session, topic_id: str, *, sync_trigger: str = 'topic_update') -> dict:
    user_ids = db.scalars(select(UserTopicSubscription.user_id).where(UserTopicSubscription.topic_id == topic_id)).all()
    synced = 0
    failed = 0
    for user_id in dict.fromkeys(user_ids):
        user = db.get(User, user_id)
        result = push_user_pricing_to_vip(db, user, sync_trigger=sync_trigger)
        if result.get('ok'):
            synced += 1
        else:
            failed += 1
    return {'ok': True, 'status': 'completed', 'synced_users': synced, 'failed_users': failed}


def push_pricing_for_all_subscribed_users(db: Session, *, sync_trigger: str = 'topic_bulk_update') -> dict:
    user_ids = db.scalars(select(UserTopicSubscription.user_id).distinct()).all()
    synced = 0
    failed = 0
    for user_id in dict.fromkeys(user_ids):
        user = db.get(User, user_id)
        result = push_user_pricing_to_vip(db, user, sync_trigger=sync_trigger)
        if result.get('ok'):
            synced += 1
        else:
            failed += 1
    return {'ok': True, 'status': 'completed', 'synced_users': synced, 'failed_users': failed}
