from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from io import BytesIO

from app.db import SessionLocal
from app.models.article import Article
from app.models.brief import Brief
from app.models.source import Source
from app.models.subscription import UserArticleRead, UserTopicSubscription
from app.models.topic import Topic
from app.services.audio_service import build_audio_research_text, synthesize_mp3_bytes
from app.services.external_provider_service import (
    build_article_prompt,
    build_brief_prompt,
    build_provider_url,
    build_topic_prompt,
    get_enabled_providers_for_user,
    get_user_provider_preferences,
    save_user_provider_preferences,
)
from app.utils.templates import template_context


router = APIRouter(tags=["user"])


def require_user(request: Request):
    return getattr(request.state, "current_user", None)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    with SessionLocal() as db:
        topic_rows = db.scalars(
            select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order.asc(), Topic.name.asc())
        ).all()
        selected_ids = set(
            db.scalars(
                select(UserTopicSubscription.topic_id).where(UserTopicSubscription.user_id == current_user.id)
            ).all()
        )
        read_ids = set(
            db.scalars(select(UserArticleRead.article_id).where(UserArticleRead.user_id == current_user.id)).all()
        )
        provider_preferences = get_user_provider_preferences(db, current_user)
        enabled_providers = get_enabled_providers_for_user(db, current_user)

        if selected_ids:
            articles = db.scalars(
                select(Article)
                .options(joinedload(Article.source).joinedload(Source.topic))
                .join(Source, Source.id == Article.source_id)
                .where(Source.topic_id.in_(selected_ids))
                .order_by(desc(Article.published_at), desc(Article.created_at))
                .limit(60)
            ).unique().all()
            briefs = db.scalars(
                select(Brief)
                .options(joinedload(Brief.topic))
                .where(Brief.topic_id.in_(selected_ids), Brief.status == "published")
                .order_by(Brief.published_at.desc(), Brief.generated_at.desc())
            ).unique().all()
            selected_topics = [topic for topic in topic_rows if topic.id in selected_ids][:8]
        else:
            articles = []
            briefs = []
            selected_topics = []

        related_article_ids = []
        for brief in briefs:
            related_article_ids.extend(brief.article_ids)
        related_articles = {}
        if related_article_ids:
            related_rows = db.scalars(
                select(Article)
                .options(joinedload(Article.source).joinedload(Source.topic))
                .where(Article.id.in_(related_article_ids))
            ).unique().all()
            related_articles = {article.id: article for article in related_rows}
        brief_related = {
            brief.id: [related_articles[article_id] for article_id in brief.article_ids if article_id in related_articles]
            for brief in briefs
        }

        brief_external_links = {
            brief.id: [
                {
                    "name": provider.name,
                    "url": build_provider_url(provider, build_brief_prompt(brief)),
                }
                for provider in enabled_providers
            ]
            for brief in briefs
        }
        topic_external_links = {
            topic.id: [
                {
                    "name": provider.name,
                    "url": build_provider_url(provider, build_topic_prompt(topic, mode="topic")),
                }
                for provider in enabled_providers
            ]
            for topic in selected_topics
        }
        article_external_links = {
            article.id: [
                {
                    "name": provider.name,
                    "url": build_provider_url(
                        provider,
                        build_article_prompt(
                            article.source.topic.name if article.source and article.source.topic else "obecné téma",
                            article.title,
                            article.summary,
                        ),
                    ),
                }
                for provider in enabled_providers
            ]
            for article in articles[:20]
        }

    return request.app.state.templates.TemplateResponse(
        "user_dashboard.html",
        template_context(
            request,
            topics=topic_rows,
            selected_ids=selected_ids,
            briefs=briefs,
            brief_related=brief_related,
            brief_external_links=brief_external_links,
            topic_external_links=topic_external_links,
            article_external_links=article_external_links,
            provider_preferences=provider_preferences,
            selected_topics=selected_topics,
            articles=articles,
            read_ids=read_ids,
        ),
    )




@router.get("/briefs/{brief_id}/audio.mp3")
def brief_audio(request: Request, brief_id: str):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    with SessionLocal() as db:
        brief = db.scalar(select(Brief).options(joinedload(Brief.topic)).where(Brief.id == brief_id))
        if not brief:
            return RedirectResponse(url="/dashboard", status_code=303)
        if getattr(request.state, "current_role", current_user.role) != "admin" and brief.status != "published":
            return RedirectResponse(url="/dashboard", status_code=303)

        related_rows = []
        if brief.article_ids:
            related_rows = db.scalars(
                select(Article)
                .options(joinedload(Article.source).joinedload(Source.topic))
                .where(Article.id.in_(brief.article_ids))
            ).unique().all()

        audio_text = build_audio_research_text(brief, related_rows)
        mp3_bytes = synthesize_mp3_bytes(audio_text)
        filename = f"briefing-{brief.id}.mp3"
        return StreamingResponse(
            BytesIO(mp3_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

@router.post("/dashboard/subscriptions")
def update_subscriptions(request: Request, topic_ids: list[str] = Form(default=[])):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        existing = db.scalars(select(UserTopicSubscription).where(UserTopicSubscription.user_id == current_user.id)).all()
        for row in existing:
            db.delete(row)
        db.commit()
        for topic_id in topic_ids:
            db.add(UserTopicSubscription(user_id=current_user.id, topic_id=topic_id))
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/dashboard/providers")
def update_provider_preferences(request: Request, provider_ids: list[str] = Form(default=[])):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        fresh_user = db.get(type(current_user), current_user.id)
        if fresh_user:
            save_user_provider_preferences(db, fresh_user, provider_ids)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/articles/{article_id}/read")
def mark_read(request: Request, article_id: str):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        existing = db.scalar(
            select(UserArticleRead).where(
                UserArticleRead.user_id == current_user.id,
                UserArticleRead.article_id == article_id,
            )
        )
        if not existing:
            db.add(UserArticleRead(user_id=current_user.id, article_id=article_id))
            db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)
