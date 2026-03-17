from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import UserTopicSubscription
from app.models.topic import Topic
from app.models.user import User


def _serialize_topic(topic: Topic) -> dict:
    price_czk = int(topic.price_czk or 0)
    return {
        "id": topic.id,
        "name": topic.name,
        "slug": topic.slug,
        "price_czk": price_czk,
        "price_label": f"{price_czk} Kč / měsíc",
        "billing_period": "month",
    }


def get_user_monthly_topic_pricing(db: Session, *, email: str | None = None, username: str | None = None, user_id: str | None = None) -> dict:
    stmt = select(User)
    if user_id:
        stmt = stmt.where(User.id == str(user_id).strip())
    elif email:
        stmt = stmt.where(User.email == str(email).strip().lower())
    elif username:
        stmt = stmt.where(User.username == str(username).strip())
    else:
        return {
            "found_user": False,
            "monthly_amount_czk": 0,
            "active_topic_count": 0,
            "topics": [],
            "currency": "CZK",
            "billing_period": "month",
            "pricing_source": "reserse_topics",
        }

    user = db.scalar(stmt.limit(1))
    if not user:
        return {
            "found_user": False,
            "monthly_amount_czk": 0,
            "active_topic_count": 0,
            "topics": [],
            "currency": "CZK",
            "billing_period": "month",
            "pricing_source": "reserse_topics",
            "email": (email or "").strip().lower() or None,
            "username": (username or "").strip() or None,
        }

    topics = db.scalars(
        select(Topic)
        .join(UserTopicSubscription, UserTopicSubscription.topic_id == Topic.id)
        .where(UserTopicSubscription.user_id == user.id, Topic.is_active.is_(True))
        .order_by(Topic.sort_order.asc(), Topic.name.asc())
    ).all()

    monthly_amount_czk = sum(int(topic.price_czk or 0) for topic in topics)
    serialized_topics = [_serialize_topic(topic) for topic in topics]
    return {
        "found_user": True,
        "user_id": user.id,
        "email": user.email,
        "username": user.username,
        "monthly_amount_czk": monthly_amount_czk,
        "active_topic_count": len(serialized_topics),
        "topics": serialized_topics,
        "currency": "CZK",
        "billing_period": "month",
        "pricing_source": "reserse_topics",
        "monthly_label": f"{monthly_amount_czk} Kč / měsíc",
    }
