from fastapi import APIRouter, Form, Request
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


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return request.app.state.templates.TemplateResponse("register.html", template_context(request, error=None))


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
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
        token = create_session(
            db,
            user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        response = RedirectResponse(url="/admin" if user.role == "admin" else "/dashboard", status_code=303)
        _set_session_cookie(response, token)
        return response


@router.get("/logout")
def logout(request: Request):
    raw_token = request.cookies.get(settings.session_cookie_name)
    with SessionLocal() as db:
        revoke_session(db, raw_token)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response
