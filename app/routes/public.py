from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.article import Article
from app.models.source import Source
from app.models.topic import Topic
from app.utils.templates import template_context

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    with SessionLocal() as db:
        topic_count = db.scalar(select(func.count()).select_from(Topic)) or 0
        source_count = db.scalar(select(func.count()).select_from(Source)) or 0
        article_count = db.scalar(select(func.count()).select_from(Article)) or 0

    return request.app.state.templates.TemplateResponse(
        "index.html",
        template_context(
            request,
            topic_count=topic_count,
            source_count=source_count,
            article_count=article_count,
        ),
    )


@router.get("/health")
def health():
    return {"ok": True}
