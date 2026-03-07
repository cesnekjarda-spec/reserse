from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.source import Source
from app.models.subscription import UserTopicSubscription
from app.models.topic import Topic
from app.models.user import User
from app.seed_data import SEED_TOPICS
from app.services.auth_service import upsert_user
from app.utils.text import slugify


def ensure_system_accounts(db: Session) -> None:
    upsert_user(
        db,
        username=settings.bootstrap_admin_username,
        email=settings.bootstrap_admin_email,
        password=settings.bootstrap_admin_password,
        role="admin",
    )
    normal_user = upsert_user(
        db,
        username=settings.bootstrap_user_username,
        email=settings.bootstrap_user_email,
        password=settings.bootstrap_user_password,
        role="user",
    )
    ensure_seed_topics_and_sources(db)
    ensure_default_user_subscriptions(db, normal_user)


def ensure_seed_topics_and_sources(db: Session) -> None:
    for topic_item in SEED_TOPICS:
        slug = slugify(topic_item["name"])
        topic = db.scalar(select(Topic).where(Topic.slug == slug))
        if not topic:
            topic = Topic(
                name=topic_item["name"],
                slug=slug,
                description=topic_item.get("description"),
                price_czk=topic_item.get("price_czk", 0),
                sort_order=topic_item.get("sort_order", 0),
                is_active=True,
            )
            db.add(topic)
            db.commit()
            db.refresh(topic)
        else:
            topic.description = topic_item.get("description")
            topic.price_czk = topic_item.get("price_czk", 0)
            topic.sort_order = topic_item.get("sort_order", 0)
            topic.is_active = True
            db.add(topic)
            db.commit()

        for source_item in topic_item.get("sources", []):
            existing = db.scalar(
                select(Source).where(Source.topic_id == topic.id, Source.rss_url == source_item["rss_url"])
            )
            if existing:
                existing.name = source_item["name"]
                existing.website_url = source_item.get("website_url")
                existing.is_active = True
                db.add(existing)
                db.commit()
                continue
            db.add(
                Source(
                    topic_id=topic.id,
                    name=source_item["name"],
                    website_url=source_item.get("website_url"),
                    rss_url=source_item["rss_url"],
                    is_active=True,
                )
            )
            db.commit()


def ensure_default_user_subscriptions(db: Session, user: User) -> None:
    topic_ids = db.scalars(select(Topic.id).where(Topic.is_active.is_(True))).all()
    for topic_id in topic_ids:
        existing = db.scalar(
            select(UserTopicSubscription).where(
                UserTopicSubscription.user_id == user.id,
                UserTopicSubscription.topic_id == topic_id,
            )
        )
        if not existing:
            db.add(UserTopicSubscription(user_id=user.id, topic_id=topic_id))
    db.commit()
