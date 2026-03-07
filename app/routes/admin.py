import uuid

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

router = APIRouter()


def _require_admin(request: Request):
    current_user = getattr(request.state, "current_user", None)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    if current_user.role != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    return None


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        stats = {
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "topics": db.scalar(select(func.count()).select_from(Topic)) or 0,
            "sources": db.scalar(select(func.count()).select_from(Source)) or 0,
            "articles": db.scalar(select(func.count()).select_from(Article)) or 0,
        }
        latest_sync = db.scalar(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(1))

    return request.app.state.templates.TemplateResponse(
        "admin_dashboard.html",
        template_context(request, stats=stats, latest_sync=latest_sync),
    )


@router.get("/admin/topics", response_class=HTMLResponse)
def admin_topics(request: Request):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        topics = db.scalars(select(Topic).order_by(Topic.sort_order.asc(), Topic.name.asc())).all()

    return request.app.state.templates.TemplateResponse(
        "admin_topics.html",
        template_context(request, topics=topics),
    )


@router.get("/admin/topics/new", response_class=HTMLResponse)
def admin_topics_new_form(request: Request):
    guard = _require_admin(request)
    if guard:
        return guard

    return request.app.state.templates.TemplateResponse(
        "admin_topic_form.html",
        template_context(request, topic=None, error=None),
    )


@router.post("/admin/topics/new")
def admin_topics_new_submit(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    price_czk: int = Form(0),
    sort_order: int = Form(0),
    is_active: str | None = Form(None),
):
    guard = _require_admin(request)
    if guard:
        return guard

    slug = slugify(name)
    if not slug:
        return request.app.state.templates.TemplateResponse(
            "admin_topic_form.html",
            template_context(request, topic=None, error="Název okruhu není platný."),
            status_code=400,
        )

    with SessionLocal() as db:
        existing = db.scalar(select(Topic).where(Topic.slug == slug))
        if existing:
            return request.app.state.templates.TemplateResponse(
                "admin_topic_form.html",
                template_context(request, topic=None, error="Okruh s tímto názvem už existuje."),
                status_code=400,
            )

        topic = Topic(
            name=name.strip(),
            slug=slug,
            description=description.strip() or None,
            price_czk=price_czk,
            sort_order=sort_order,
            is_active=is_active == "on",
        )
        db.add(topic)
        db.commit()

    return RedirectResponse(url="/admin/topics", status_code=303)


@router.get("/admin/topics/{topic_id}/edit", response_class=HTMLResponse)
def admin_topics_edit_form(request: Request, topic_id: uuid.UUID):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        topic = db.get(Topic, topic_id)
        if not topic:
            return RedirectResponse(url="/admin/topics", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "admin_topic_form.html",
        template_context(request, topic=topic, error=None),
    )


@router.post("/admin/topics/{topic_id}/edit")
def admin_topics_edit_submit(
    request: Request,
    topic_id: uuid.UUID,
    name: str = Form(...),
    description: str = Form(""),
    price_czk: int = Form(0),
    sort_order: int = Form(0),
    is_active: str | None = Form(None),
):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        topic = db.get(Topic, topic_id)
        if not topic:
            return RedirectResponse(url="/admin/topics", status_code=303)

        slug = slugify(name)
        conflict = db.scalar(select(Topic).where(Topic.slug == slug, Topic.id != topic.id))
        if conflict:
            return request.app.state.templates.TemplateResponse(
                "admin_topic_form.html",
                template_context(request, topic=topic, error="Jiný okruh už používá stejný název."),
                status_code=400,
            )

        topic.name = name.strip()
        topic.slug = slug
        topic.description = description.strip() or None
        topic.price_czk = price_czk
        topic.sort_order = sort_order
        topic.is_active = is_active == "on"
        db.add(topic)
        db.commit()

    return RedirectResponse(url="/admin/topics", status_code=303)


@router.get("/admin/sources", response_class=HTMLResponse)
def admin_sources(request: Request):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        sources = db.scalars(select(Source).options(joinedload(Source.topic)).order_by(Source.name.asc())).unique().all()

    return request.app.state.templates.TemplateResponse(
        "admin_sources.html",
        template_context(request, sources=sources),
    )


@router.get("/admin/sources/new", response_class=HTMLResponse)
def admin_sources_new_form(request: Request):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        topics = db.scalars(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.name.asc())).all()

    return request.app.state.templates.TemplateResponse(
        "admin_source_form.html",
        template_context(request, source=None, topics=topics, error=None),
    )


@router.post("/admin/sources/new")
def admin_sources_new_submit(
    request: Request,
    topic_id: str = Form(...),
    name: str = Form(...),
    website_url: str = Form(...),
    rss_url: str = Form(...),
    is_active: str | None = Form(None),
):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        source = Source(
            topic_id=topic_id,
            name=name.strip(),
            website_url=website_url.strip(),
            rss_url=rss_url.strip(),
            is_active=is_active == "on",
        )
        db.add(source)
        db.commit()

    return RedirectResponse(url="/admin/sources", status_code=303)


@router.get("/admin/sources/{source_id}/edit", response_class=HTMLResponse)
def admin_sources_edit_form(request: Request, source_id: uuid.UUID):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        source = db.get(Source, source_id)
        topics = db.scalars(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.name.asc())).all()
        if not source:
            return RedirectResponse(url="/admin/sources", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "admin_source_form.html",
        template_context(request, source=source, topics=topics, error=None),
    )


@router.post("/admin/sources/{source_id}/edit")
def admin_sources_edit_submit(
    request: Request,
    source_id: uuid.UUID,
    topic_id: str = Form(...),
    name: str = Form(...),
    website_url: str = Form(...),
    rss_url: str = Form(...),
    is_active: str | None = Form(None),
):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        source = db.get(Source, source_id)
        topics = db.scalars(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.name.asc())).all()
        if not source:
            return RedirectResponse(url="/admin/sources", status_code=303)

        source.topic_id = topic_id
        source.name = name.strip()
        source.website_url = website_url.strip()
        source.rss_url = rss_url.strip()
        source.is_active = is_active == "on"
        db.add(source)
        db.commit()

    return RedirectResponse(url="/admin/sources", status_code=303)


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.created_at.desc())).all()

    return request.app.state.templates.TemplateResponse(
        "admin_users.html",
        template_context(request, users=users),
    )


@router.get("/admin/sync-runs", response_class=HTMLResponse)
def admin_sync_runs(request: Request):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        runs = db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(30)).all()

    return request.app.state.templates.TemplateResponse(
        "admin_sync_runs.html",
        template_context(request, runs=runs),
    )


@router.post("/admin/sync/run")
def admin_sync_run(request: Request):
    guard = _require_admin(request)
    if guard:
        return guard

    with SessionLocal() as db:
        run_sync(db, triggered_by="admin_manual")

    return RedirectResponse(url="/admin/sync-runs", status_code=303)
