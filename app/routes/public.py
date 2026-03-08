from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.db import SessionLocal
from app.models.article import Article
from app.models.brief import Brief
from app.models.source import Source
from app.models.topic import Topic
from app.models.user import User
from app.utils.templates import template_context


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    with SessionLocal() as db:
        topic_count = db.scalar(select(func.count()).select_from(Topic)) or 0
        source_count = db.scalar(select(func.count()).select_from(Source)) or 0
        article_count = db.scalar(select(func.count()).select_from(Article)) or 0
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
        brief_count = db.scalar(select(func.count()).select_from(Brief).where(Brief.status == "published")) or 0
        latest_topics = db.scalars(
            select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order.asc()).limit(8)
        ).all()
        published_briefs = db.scalars(
            select(Brief).options(joinedload(Brief.topic)).where(Brief.status == "published").order_by(Brief.published_at.desc()).limit(3)
        ).unique().all()
    return request.app.state.templates.TemplateResponse(
        "index.html",
        template_context(
            request,
            topic_count=topic_count,
            source_count=source_count,
            article_count=article_count,
            user_count=user_count,
            brief_count=brief_count,
            latest_topics=latest_topics,
            published_briefs=published_briefs,
        ),
    )


@router.get("/health")
def health():
    return {"ok": True}
