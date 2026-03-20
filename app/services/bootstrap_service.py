from urllib.parse import quote_plus

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.source import Source
from app.models.subscription import UserTopicSubscription
from app.models.topic import Topic
from app.models.user import User
from app.seed_data import SEED_TOPICS
from app.services.auth_service import upsert_user
from app.services.external_provider_service import ensure_external_providers, ensure_user_provider_preferences
from app.utils.text import slugify


def ensure_system_accounts(db: Session) -> None:
    admin_user = upsert_user(
        db,
        username=settings.bootstrap_admin_username,
        email=settings.bootstrap_admin_email,
        password=settings.bootstrap_admin_password,
        role="admin",
    )
    normal_user = None
    if settings.bootstrap_user_enabled:
        normal_user = upsert_user(
            db,
            username=settings.bootstrap_user_username,
            email=settings.bootstrap_user_email,
            password=settings.bootstrap_user_password,
            role="user",
        )
    ensure_seed_topics_and_sources(db)
    if normal_user:
        ensure_default_user_subscriptions(db, normal_user)
    ensure_external_providers(db)
    ensure_user_provider_preferences(db, admin_user)
    if normal_user:
        ensure_user_provider_preferences(db, normal_user)


def _google_news_source(name: str, query: str) -> dict:
    encoded = quote_plus(query)
    return {
        "name": name,
        "website_url": f"https://news.google.com/search?q={encoded}&hl=cs&gl=CZ&ceid=CZ:cs",
        "rss_url": f"https://news.google.com/rss/search?q={encoded}&hl=cs&gl=CZ&ceid=CZ:cs",
    }


def _direct_sources_for_topic(topic_name: str) -> list[dict]:
    slug = slugify(topic_name)
    shared: list[dict] = [
        _google_news_source(f"Google News – Reuters focus – {topic_name}", f'{topic_name} site:reuters.com'),
        _google_news_source(f"Google News – AP focus – {topic_name}", f'{topic_name} site:apnews.com'),
    ]

    mapping = {
        "ai-a-automatizace": [
            {
                "name": "The Register – AI + ML",
                "website_url": "https://www.theregister.com/Design/page/feeds.html",
                "rss_url": "https://www.theregister.com/software/ai_ml/headlines.atom",
            },
        ],
        "kyberbezpecnost": [
            {
                "name": "The Register – Security",
                "website_url": "https://www.theregister.com/Design/page/feeds.html",
                "rss_url": "https://www.theregister.com/security/headlines.atom",
            },
        ],
        "vyvoj-software": [
            {
                "name": "The Register – DevOps",
                "website_url": "https://www.theregister.com/Design/page/feeds.html",
                "rss_url": "https://www.theregister.com/software/devops/headlines.atom",
            },
            {
                "name": "The Register – AI + ML",
                "website_url": "https://www.theregister.com/Design/page/feeds.html",
                "rss_url": "https://www.theregister.com/software/ai_ml/headlines.atom",
            },
        ],
        "ekonomika-a-makro": [
            {
                "name": "ECB – Press releases",
                "website_url": "https://www.ecb.europa.eu/home/html/rss.en.html",
                "rss_url": "https://www.ecb.europa.eu/rss/press.html",
            },
            {
                "name": "ECB – Statistical press releases",
                "website_url": "https://www.ecb.europa.eu/home/html/rss.en.html",
                "rss_url": "https://www.ecb.europa.eu/rss/statpress.html",
            },
        ],
        "finance-a-bankovnictvi": [
            {
                "name": "ECB – Press releases",
                "website_url": "https://www.ecb.europa.eu/home/html/rss.en.html",
                "rss_url": "https://www.ecb.europa.eu/rss/press.html",
            },
        ],
        "investice-a-trhy": [
            {
                "name": "ECB – Research bulletin",
                "website_url": "https://www.ecb.europa.eu/home/html/rss.en.html",
                "rss_url": "https://www.ecb.europa.eu/rss/rbu.html",
            },
            {
                "name": "ECB – Press releases",
                "website_url": "https://www.ecb.europa.eu/home/html/rss.en.html",
                "rss_url": "https://www.ecb.europa.eu/rss/press.html",
            },
        ],
        "geopolitika-a-verejna-politika": [
            {
                "name": "ECB – Press releases",
                "website_url": "https://www.ecb.europa.eu/home/html/rss.en.html",
                "rss_url": "https://www.ecb.europa.eu/rss/press.html",
            },
        ],
        "pravo-a-regulace": [
            {
                "name": "ECB – Press releases",
                "website_url": "https://www.ecb.europa.eu/home/html/rss.en.html",
                "rss_url": "https://www.ecb.europa.eu/rss/press.html",
            },
        ],
    }
    shared.extend(mapping.get(slug, []))
    return shared


def _default_topic_queries(topic_name: str, description: str | None = None) -> list[str]:
    base = topic_name.strip()
    generic = [
        base,
        f"{base} Česko",
        f"{base} Evropa",
        f"{base} trendy",
        f"{base} vývoj",
        f"{base} analýza",
        f"{base} firmy",
        f"{base} trh",
        f"{base} inovace",
        f"{base} regulace",
    ]
    if description:
        desc = description.strip().rstrip('.')
        generic.append(f"{base} {desc}")
    ordered: list[str] = []
    seen: set[str] = set()
    for query in generic:
        q = query.strip()
        if not q or q.lower() in seen:
            continue
        seen.add(q.lower())
        ordered.append(q)
    return ordered


def _top_up_google_news_sources(topic_name: str, description: str | None, existing_source_items: list[dict], minimum_sources: int = 10) -> list[dict]:
    used_names = {str(item.get('name') or '').strip().lower() for item in existing_source_items}
    used_rss = {str(item.get('rss_url') or '').strip().lower() for item in existing_source_items}
    additions: list[dict] = []
    for idx, query in enumerate(_default_topic_queries(topic_name, description), start=1):
        source = _google_news_source(f"Google News – {topic_name} · doplněk {idx}", query)
        key_name = source['name'].strip().lower()
        key_rss = source['rss_url'].strip().lower()
        if key_name in used_names or key_rss in used_rss:
            continue
        additions.append(source)
        used_names.add(key_name)
        used_rss.add(key_rss)
        if len(existing_source_items) + len(additions) >= minimum_sources:
            break
    return additions

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

        source_items = list(topic_item.get("sources", [])) + _direct_sources_for_topic(topic_item["name"])
        source_items.extend(
            _top_up_google_news_sources(
                topic_item["name"],
                topic_item.get("description"),
                source_items,
                minimum_sources=10,
            )
        )
        for source_item in source_items:
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
