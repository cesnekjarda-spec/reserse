from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.db import SessionLocal
from app.models.article import Article
from app.models.source import Source
from app.models.sync import SyncRun
from app.models.topic import Topic
from app.models.user import User
from app.services.sync_service import run_sync
from app.utils.templates import template_context
from app.utils.text import slugify


router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(request: Request):
    user = getattr(request.state, "current_user", None)
    if not user or user.role != "admin":
        return False
    return True


@router.get("", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if not require_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        topic_count = db.scalar(select(func.count()).select_from(Topic)) or 0
        source_count = db.scalar(select(func.count()).select_from(Source)) or 0
        article_count = db.scalar(select(func.count()).select_from(Article)) or 0
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
        last_runs = db.scalars(select(SyncRun).order_by(SyncRun.created_at.desc()).limit(8)).all()
    return request.app.state.templates.TemplateResponse(
        "admin_dashboard.html",
        template_context(
            request,
            topic_count=topic_count,
            source_count=source_count,
            article_count=article_count,
            user_count=user_count,
            last_runs=last_runs,
        ),
    )


@router.post("/sync")
def admin_sync(request: Request):
    if not require_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        result = run_sync(db, triggered_by="admin")
    return RedirectResponse(url=f"/admin?sync={result['articles_created']}", status_code=303)


@router.get("/topics", response_class=HTMLResponse)
def admin_topics(request: Request):
    if not require_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        topics = db.scalars(select(Topic).order_by(Topic.sort_order.asc(), Topic.name.asc())).all()
    return request.app.state.templates.TemplateResponse(
        "admin_topics.html", template_context(request, topics=topics)
    )


@router.post("/topics")
def admin_topics_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    price_czk: int = Form(0),
    sort_order: int = Form(0),
):
    if not require_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        slug = slugify(name)
        existing = db.scalar(select(Topic).where(Topic.slug == slug))
        if not existing:
            db.add(
                Topic(
                    name=name.strip(),
                    slug=slug,
                    description=description.strip() or None,
                    price_czk=price_czk,
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            db.commit()
    return RedirectResponse(url="/admin/topics", status_code=303)


@router.get("/sources", response_class=HTMLResponse)
def admin_sources(request: Request):
    if not require_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        topics = db.scalars(select(Topic).order_by(Topic.sort_order.asc(), Topic.name.asc())).all()
        sources = db.scalars(select(Source).order_by(Source.created_at.desc()).limit(400)).all()
    return request.app.state.templates.TemplateResponse(
        "admin_sources.html", template_context(request, topics=topics, sources=sources)
    )


@router.post("/sources")
def admin_sources_create(
    request: Request,
    topic_id: str = Form(...),
    name: str = Form(...),
    rss_url: str = Form(...),
    website_url: str = Form(""),
):
    if not require_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        existing = db.scalar(select(Source).where(Source.topic_id == topic_id, Source.rss_url == rss_url.strip()))
        if not existing:
            db.add(
                Source(
                    topic_id=topic_id,
                    name=name.strip(),
                    rss_url=rss_url.strip(),
                    website_url=website_url.strip() or None,
                    is_active=True,
                )
            )
            db.commit()
    return RedirectResponse(url="/admin/sources", status_code=303)


@router.get("/users", response_class=HTMLResponse)
def admin_users(request: Request):
    if not require_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return request.app.state.templates.TemplateResponse(
        "admin_users.html", template_context(request, users=users)
    )
