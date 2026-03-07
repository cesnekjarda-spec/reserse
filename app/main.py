from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.db import SessionLocal, init_db
from app.routes import admin, auth, internal, public, user
from app.services.auth_service import ensure_admin_exists, get_user_from_session_token


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.app_name)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.middleware("http")
async def load_current_user(request: Request, call_next):
    request.state.current_user = None
    raw_token = request.cookies.get(settings.session_cookie_name)

    if raw_token:
        with SessionLocal() as db:
            user = get_user_from_session_token(db, raw_token)
            if user and user.is_active:
                request.state.current_user = user

    response = await call_next(request)
    return response


@app.on_event("startup")
def startup() -> None:
    init_db()
    with SessionLocal() as db:
        ensure_admin_exists(db, settings.admin_email, settings.admin_password)


app.include_router(public.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(admin.router)
app.include_router(internal.router)
