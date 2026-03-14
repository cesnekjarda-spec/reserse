import base64
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.db import SessionLocal
from app.services.auth_service import (
    authenticate_user,
    create_session,
    create_user,
    get_user_by_email,
    get_user_by_username,
    revoke_session,
    upsert_vip_user,
)
from app.utils.templates import template_context


router = APIRouter()


def _set_session_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )



def _set_mode_cookie(response: RedirectResponse, mode: str | None) -> None:
    if mode in ("admin", "user"):
        response.set_cookie(
            key="research_mode",
            value=mode,
            httponly=True,
            secure=settings.is_production,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )
    else:
        response.delete_cookie("research_mode")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _verify_vip_sso_token(token: str) -> dict:
    if not settings.vip_sso_enabled:
        raise HTTPException(status_code=503, detail="VIP SSO disabled")
    secret = (settings.vip_sso_shared_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="VIP SSO secret missing")
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
    if claims.get("aud") != "reserse":
        raise HTTPException(status_code=401, detail="Invalid token audience")
    if int(claims.get("exp") or 0) < now:
        raise HTTPException(status_code=401, detail="Token expired")
    return claims


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    if not settings.allow_public_registration:
        return request.app.state.templates.TemplateResponse("register.html", template_context(request, error="Veřejná registrace je vypnutá. Účet vytváří administrátor."), status_code=403)
    return request.app.state.templates.TemplateResponse("register.html", template_context(request, error=None))


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    if not settings.allow_public_registration:
        return request.app.state.templates.TemplateResponse("register.html", template_context(request, error="Veřejná registrace je vypnutá. Účet vytváří administrátor."), status_code=403)
    with SessionLocal() as db:
        username = username.strip()
        email = email.strip().lower()
        if not username:
            return request.app.state.templates.TemplateResponse(
                "register.html", template_context(request, error="Zadej uživatelské jméno."), status_code=400
            )
        if "@" not in email:
            return request.app.state.templates.TemplateResponse(
                "register.html", template_context(request, error="Zadej platný e-mail."), status_code=400
            )
        if len(password) < 8:
            return request.app.state.templates.TemplateResponse(
                "register.html", template_context(request, error="Heslo musí mít alespoň 8 znaků."), status_code=400
            )
        if password != password_confirm:
            return request.app.state.templates.TemplateResponse(
                "register.html", template_context(request, error="Hesla se neshodují."), status_code=400
            )
        if get_user_by_email(db, email):
            return request.app.state.templates.TemplateResponse(
                "register.html", template_context(request, error="Tento e-mail už existuje."), status_code=400
            )
        if get_user_by_username(db, username):
            return request.app.state.templates.TemplateResponse(
                "register.html", template_context(request, error="Toto uživatelské jméno už existuje."), status_code=400
            )
        user = create_user(db, username=username, email=email, password=password, role="user")
        token = create_session(
            db,
            user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        response = RedirectResponse(url="/dashboard", status_code=303)
        _set_session_cookie(response, token)
        return response



@router.get("/sso/consume")
def sso_consume(request: Request, token: str):
    claims = _verify_vip_sso_token(token)
    email = str(claims.get("email") or "").strip().lower()
    username = str(claims.get("username") or "").strip()
    vip_role = str(claims.get("vip_role") or "user").lower()
    effective_role = "admin" if str(claims.get("effective_role") or "user").lower() == "admin" and vip_role == "admin" else "user"
    if not email or not username:
        raise HTTPException(status_code=400, detail="Missing email/username in token")

    stored_role = "admin" if vip_role == "admin" else "user"

    with SessionLocal() as db:
        user = upsert_vip_user(db, username=username, email=email, role=stored_role, is_active=True)
        token_value = create_session(
            db,
            user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    target_url = "/admin" if effective_role == "admin" else "/dashboard"
    response = RedirectResponse(url=target_url, status_code=303)
    _set_session_cookie(response, token_value)
    _set_mode_cookie(response, effective_role if vip_role == "admin" else "user")
    return response


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return request.app.state.templates.TemplateResponse("login.html", template_context(request, error=None))


@router.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, identity: str = Form(...), password: str = Form(...)):
    with SessionLocal() as db:
        user = authenticate_user(db, identity=identity, password=password)
        if not user:
            return request.app.state.templates.TemplateResponse(
                "login.html", template_context(request, error="Neplatné jméno / e-mail nebo heslo."), status_code=400
            )

        target_url = "/admin" if user.role == "admin" else "/dashboard"

        token = create_session(
            db,
            user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        response = RedirectResponse(url=target_url, status_code=303)
        _set_session_cookie(response, token)
        _set_mode_cookie(response, user.role if user.role == "admin" else "user")
        return response


@router.get("/logout")
def logout(request: Request):
    raw_token = request.cookies.get(settings.session_cookie_name)
    with SessionLocal() as db:
        revoke_session(db, raw_token)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    response.delete_cookie("research_mode")
    return response
