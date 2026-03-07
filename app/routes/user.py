from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from app.db import SessionLocal
from app.models.article import Article
from app.models.source import Source
from app.models.subscription import UserArticleRead, UserTopicSubscription
from app.models.topic import Topic
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
        topic_rows = db.scalars(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order.asc(), Topic.name.asc())).all()
        selected_ids = set(
            db.scalars(
                select(UserTopicSubscription.topic_id).where(UserTopicSubscription.user_id == current_user.id)
            ).all()
        )
        read_ids = set(
            db.scalars(select(UserArticleRead.article_id).where(UserArticleRead.user_id == current_user.id)).all()
        )
        if selected_ids:
            articles = db.scalars(
                select(Article)
                .join(Source, Source.id == Article.source_id)
                .where(Source.topic_id.in_(selected_ids))
                .order_by(desc(Article.published_at), desc(Article.created_at))
                .limit(150)
            ).all()
        else:
            articles = []
    return request.app.state.templates.TemplateResponse(
        "user_dashboard.html",
        template_context(
            request,
            topics=topic_rows,
            selected_ids=selected_ids,
            articles=articles,
            read_ids=read_ids,
        ),
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
