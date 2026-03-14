from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.db import SessionLocal, init_db
from app.routes import admin, auth, internal, public, user
from app.services.auth_service import get_user_from_session_token
from app.services.bootstrap_service import ensure_system_accounts
from app.services.sync_service import run_sync


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.middleware("http")
async def load_current_user(request: Request, call_next):
    request.state.current_user = None
    request.state.current_role = None
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        with SessionLocal() as db:
            current_user = get_user_from_session_token(db, raw_token)
            if current_user and current_user.is_active:
                request.state.current_user = current_user
                current_role = current_user.role
                requested_mode = request.cookies.get("research_mode")
                if current_user.role == "admin" and requested_mode in ("admin", "user"):
                    current_role = requested_mode
                request.state.current_role = current_role
    response = await call_next(request)
    return response


@app.on_event("startup")
def startup() -> None:
    init_db()
    with SessionLocal() as db:
        ensure_system_accounts(db)
        if settings.auto_sync_on_startup:
            run_sync(db, triggered_by="startup")


app.include_router(public.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(admin.router)
app.include_router(internal.router)
