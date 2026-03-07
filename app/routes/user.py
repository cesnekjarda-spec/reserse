import uuid

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import exists, select
from sqlalchemy.orm import joinedload

from app.db import SessionLocal
from app.models.article import Article
from app.models.source import Source
from app.models.subscription import UserArticleRead, UserTopicSubscription
from app.models.topic import Topic
from app.utils.templates import template_context

router = APIRouter()


def _redirect_login():
    return RedirectResponse(url="/login", status_code=303)


@router.get("/dashboard")
def dashboard(request: Request):
    current_user = getattr(request.state, "current_user", None)
    if not current_user:
        return _redirect_login()

    with SessionLocal() as db:
        user_id = current_user.id

        subscriptions = db.scalars(
            select(UserTopicSubscription)
            .where(UserTopicSubscription.user_id == user_id)
            .options(joinedload(UserTopicSubscription.topic))
        ).all()
        subscribed_topic_ids = [sub.topic_id for sub in subscriptions]

        all_topics = db.scalars(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order.asc(), Topic.name.asc())).all()

        articles = []
        if subscribed_topic_ids:
            stmt = (
                select(Article)
                .join(Source, Article.source_id == Source.id)
                .join(Topic, Source.topic_id == Topic.id)
                .where(Topic.id.in_(subscribed_topic_ids))
                .where(
                    ~exists(
                        select(UserArticleRead.id).where(
                            (UserArticleRead.user_id == user_id) & (UserArticleRead.article_id == Article.id)
                        )
                    )
                )
                .options(joinedload(Article.source).joinedload(Source.topic))
                .order_by(Article.published_at.desc().nullslast(), Article.created_at.desc())
                .limit(50)
            )
            articles = db.scalars(stmt).unique().all()

    return request.app.state.templates.TemplateResponse(
        "user_dashboard.html",
        template_context(
            request,
            subscriptions=subscriptions,
            all_topics=all_topics,
            articles=articles,
        ),
    )


@router.post("/subscriptions/add/{topic_id}")
def add_subscription(request: Request, topic_id: uuid.UUID):
    current_user = getattr(request.state, "current_user", None)
    if not current_user:
        return _redirect_login()

    with SessionLocal() as db:
        existing = db.scalar(
            select(UserTopicSubscription).where(
                UserTopicSubscription.user_id == current_user.id,
                UserTopicSubscription.topic_id == topic_id,
            )
        )
        if not existing:
            db.add(UserTopicSubscription(user_id=current_user.id, topic_id=topic_id))
            db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/subscriptions/remove/{topic_id}")
def remove_subscription(request: Request, topic_id: uuid.UUID):
    current_user = getattr(request.state, "current_user", None)
    if not current_user:
        return _redirect_login()

    with SessionLocal() as db:
        subscription = db.scalar(
            select(UserTopicSubscription).where(
                UserTopicSubscription.user_id == current_user.id,
                UserTopicSubscription.topic_id == topic_id,
            )
        )
        if subscription:
            db.delete(subscription)
            db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/articles/{article_id}/open")
def open_article(request: Request, article_id: uuid.UUID):
    current_user = getattr(request.state, "current_user", None)
    if not current_user:
        return _redirect_login()

    with SessionLocal() as db:
        article = db.scalar(
            select(Article)
            .where(Article.id == article_id)
            .options(joinedload(Article.source).joinedload(Source.topic))
        )
        if not article:
            return RedirectResponse(url="/dashboard", status_code=303)

        topic_id = article.source.topic_id
        subscribed = db.scalar(
            select(UserTopicSubscription).where(
                UserTopicSubscription.user_id == current_user.id,
                UserTopicSubscription.topic_id == topic_id,
            )
        )
        if not subscribed:
            return RedirectResponse(url="/dashboard", status_code=303)

        already_read = db.scalar(
            select(UserArticleRead).where(
                UserArticleRead.user_id == current_user.id,
                UserArticleRead.article_id == article.id,
            )
        )
        if not already_read:
            db.add(UserArticleRead(user_id=current_user.id, article_id=article.id))
            db.commit()

        return RedirectResponse(url=article.url, status_code=302)
