from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.db import SessionLocal
from app.models.article import Article
from app.models.brief import Brief
from app.models.provider import ExternalProvider, UserProviderPreference
from app.models.source import Source
from app.models.sync import SyncRun
from app.models.topic import Topic
from app.models.user import User
from app.services.brief_service import (
    generate_all_briefs,
    generate_topic_brief,
    publish_all_briefs,
    publish_brief,
    render_and_publish_all_briefs,
)
from app.services.sync_service import run_sync
from app.utils.templates import template_context
from app.utils.text import slugify
from app.services.auth_service import create_user, get_user_by_email, get_user_by_username


router = APIRouter(prefix='/admin', tags=['admin'])


def require_admin(request: Request):
    user = getattr(request.state, 'current_user', None)
    if not user or getattr(request.state, 'current_role', user.role) != 'admin':
        return False
    return True


@router.get('', response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        topic_count = db.scalar(select(func.count()).select_from(Topic)) or 0
        source_count = db.scalar(select(func.count()).select_from(Source)) or 0
        article_count = db.scalar(select(func.count()).select_from(Article)) or 0
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
        brief_count = db.scalar(select(func.count()).select_from(Brief)) or 0
        published_brief_count = db.scalar(select(func.count()).select_from(Brief).where(Brief.status == 'published')) or 0
        provider_count = db.scalar(select(func.count()).select_from(ExternalProvider).where(ExternalProvider.is_active.is_(True))) or 0
        total_topic_price = db.scalar(select(func.coalesce(func.sum(Topic.price_czk), 0)).where(Topic.is_active.is_(True))) or 0
        last_runs = db.scalars(select(SyncRun).order_by(SyncRun.created_at.desc()).limit(8)).all()
    return request.app.state.templates.TemplateResponse(
        'admin_dashboard.html',
        template_context(
            request,
            topic_count=topic_count,
            source_count=source_count,
            article_count=article_count,
            user_count=user_count,
            brief_count=brief_count,
            published_brief_count=published_brief_count,
            provider_count=provider_count,
            total_topic_price=total_topic_price,
            last_runs=last_runs,
        ),
    )


@router.post('/sync')
def admin_sync(request: Request):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        result = run_sync(db, triggered_by='admin')
    return RedirectResponse(url=f"/admin?sync={result['articles_created']}", status_code=303)


@router.get('/briefs', response_class=HTMLResponse)
def admin_briefs(request: Request):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        topics = db.scalars(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order.asc(), Topic.name.asc())).all()
        briefs = db.scalars(select(Brief).options(joinedload(Brief.topic)).order_by(Brief.updated_at.desc())).unique().all()
        briefs_by_topic = {brief.topic_id: brief for brief in briefs}
        draft_count = sum(1 for brief in briefs if brief.status != 'published')
    return request.app.state.templates.TemplateResponse(
        'admin_briefs.html',
        template_context(request, topics=topics, briefs=briefs, briefs_by_topic=briefs_by_topic, draft_count=draft_count),
    )


@router.post('/briefs/generate-all')
def admin_generate_all_briefs(request: Request):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        generate_all_briefs(db)
    return RedirectResponse(url='/admin/briefs', status_code=303)


@router.post('/briefs/publish-all')
def admin_publish_all_briefs(request: Request):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        publish_all_briefs(db)
    return RedirectResponse(url='/admin/briefs', status_code=303)


@router.post('/briefs/render-publish-all')
def admin_render_publish_all_briefs(request: Request):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        render_and_publish_all_briefs(db)
    return RedirectResponse(url='/admin/briefs', status_code=303)


@router.post('/briefs/generate/{topic_id}')
def admin_generate_topic_brief(request: Request, topic_id: str):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        topic = db.get(Topic, topic_id)
        if topic:
            generate_topic_brief(db, topic)
    return RedirectResponse(url='/admin/briefs', status_code=303)


@router.post('/briefs/{brief_id}/publish')
def admin_publish_brief(request: Request, brief_id: str):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        publish_brief(db, brief_id, publish=True)
    return RedirectResponse(url='/admin/briefs', status_code=303)


@router.post('/briefs/{brief_id}/unpublish')
def admin_unpublish_brief(request: Request, brief_id: str):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        publish_brief(db, brief_id, publish=False)
    return RedirectResponse(url='/admin/briefs', status_code=303)


@router.get('/providers', response_class=HTMLResponse)
def admin_providers(request: Request):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        providers = db.scalars(select(ExternalProvider).order_by(ExternalProvider.sort_order.asc(), ExternalProvider.name.asc())).all()
        preference_count = db.scalar(select(func.count()).select_from(UserProviderPreference)) or 0
    return request.app.state.templates.TemplateResponse('admin_providers.html', template_context(request, providers=providers, preference_count=preference_count))


@router.post('/providers/{provider_id}/toggle')
def admin_toggle_provider(request: Request, provider_id: str):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        provider = db.get(ExternalProvider, provider_id)
        if provider:
            provider.is_active = not provider.is_active
            db.add(provider)
            db.commit()
    return RedirectResponse(url='/admin/providers', status_code=303)


@router.get('/topics', response_class=HTMLResponse)
def admin_topics(request: Request):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        topics = db.scalars(select(Topic).order_by(Topic.sort_order.asc(), Topic.name.asc())).all()
        total_price = db.scalar(select(func.coalesce(func.sum(Topic.price_czk), 0)).where(Topic.is_active.is_(True))) or 0
    return request.app.state.templates.TemplateResponse('admin_topics.html', template_context(request, topics=topics, total_price=total_price))


@router.post('/topics')
def admin_topics_create(request: Request, name: str = Form(...), description: str = Form(''), price_czk: int = Form(1), sort_order: int = Form(0)):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        slug = slugify(name)
        existing = db.scalar(select(Topic).where(Topic.slug == slug))
        if not existing:
            db.add(Topic(name=name.strip(), slug=slug, description=description.strip() or None, price_czk=price_czk, sort_order=sort_order, is_active=True))
            db.commit()
    return RedirectResponse(url='/admin/topics', status_code=303)


@router.post('/topics/{topic_id}/update')
def admin_topics_update(
    request: Request,
    topic_id: str,
    name: str = Form(...),
    description: str = Form(''),
    price_czk: int = Form(1),
    sort_order: int = Form(0),
    is_active: str | None = Form(None),
):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        topic = db.get(Topic, topic_id)
        if topic:
            topic.name = name.strip()
            topic.slug = slugify(name)
            topic.description = description.strip() or None
            topic.price_czk = max(0, price_czk)
            topic.sort_order = sort_order
            topic.is_active = is_active == 'on'
            db.add(topic)
            db.commit()
    return RedirectResponse(url='/admin/topics', status_code=303)


@router.post('/topics/set-all-price')
def admin_topics_set_all_price(request: Request, price_czk: int = Form(1)):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        topics = db.scalars(select(Topic)).all()
        for topic in topics:
            topic.price_czk = max(0, price_czk)
            db.add(topic)
        db.commit()
    return RedirectResponse(url='/admin/topics', status_code=303)


@router.get('/sources', response_class=HTMLResponse)
def admin_sources(request: Request):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        topics = db.scalars(select(Topic).order_by(Topic.sort_order.asc(), Topic.name.asc())).all()
        sources = db.scalars(select(Source).options(joinedload(Source.topic)).order_by(Source.created_at.desc()).limit(400)).unique().all()
    return request.app.state.templates.TemplateResponse('admin_sources.html', template_context(request, topics=topics, sources=sources))


@router.post('/sources')
def admin_sources_create(request: Request, topic_id: str = Form(...), name: str = Form(...), rss_url: str = Form(...), website_url: str = Form('')):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        existing = db.scalar(select(Source).where(Source.topic_id == topic_id, Source.rss_url == rss_url.strip()))
        if not existing:
            db.add(Source(topic_id=topic_id, name=name.strip(), rss_url=rss_url.strip(), website_url=website_url.strip() or None, is_active=True))
            db.commit()
    return RedirectResponse(url='/admin/sources', status_code=303)


@router.get('/users', response_class=HTMLResponse)
def admin_users(request: Request):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return request.app.state.templates.TemplateResponse('admin_users.html', template_context(request, users=users))


@router.post('/users')
def admin_users_create(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form('user'),
):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        username = username.strip()
        email = email.strip().lower()
        if username and email and password and not get_user_by_email(db, email) and not get_user_by_username(db, username):
            create_user(db, username=username, email=email, password=password, role='admin' if role == 'admin' else 'user')
    return RedirectResponse(url='/admin/users', status_code=303)


@router.post('/users/{user_id}/toggle')
def admin_users_toggle(request: Request, user_id: str):
    if not require_admin(request):
        return RedirectResponse(url='/login', status_code=303)
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user:
            user.is_active = not user.is_active
            db.add(user)
            db.commit()
    return RedirectResponse(url='/admin/users', status_code=303)
