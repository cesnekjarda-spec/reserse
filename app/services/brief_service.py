from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.article import Article
from app.models.brief import Brief
from app.models.source import Source
from app.models.topic import Topic
from app.services.content_service import enrich_article_content
from app.utils.security import utcnow
from app.utils.text import domain_from_url, extract_keywords, shorten_text, top_sentences


def _recent_topic_articles(db: Session, topic_id: str, limit: int | None = None) -> list[Article]:
    stmt = (
        select(Article)
        .options(joinedload(Article.source).joinedload(Source.topic))
        .join(Source, Source.id == Article.source_id)
        .where(Source.topic_id == topic_id)
        .order_by(Article.published_at.desc(), Article.created_at.desc())
        .limit(limit or settings.brief_article_limit)
    )
    return db.scalars(stmt).unique().all()


def _ensure_content(db: Session, articles: list[Article]) -> list[Article]:
    fetched = 0
    refreshed: list[Article] = []
    for article in articles:
        if fetched < settings.brief_fetch_limit and not article.full_text:
            article = enrich_article_content(db, article)
            fetched += 1
        refreshed.append(article)
    return refreshed


def _build_structured_sections(topic: Topic, articles: list[Article]) -> dict:
    source_domains = sorted({domain_from_url(article.url) for article in articles if article.url})
    source_domains = [item for item in source_domains if item]
    source_count = len(source_domains)
    article_count = len(articles)

    weighted_texts: list[str] = []
    for article in articles:
        weighted_texts.append(article.title)
        if article.summary:
            weighted_texts.append(article.summary)
        if article.full_text:
            weighted_texts.append(article.full_text[:1600])

    keywords = extract_keywords(weighted_texts, limit=8)
    title_points: list[str] = []
    for article in articles[:5]:
        point = shorten_text(article.title, width=120)
        if point not in title_points:
            title_points.append(point)

    salient_sentences = top_sentences([article.summary or article.full_text or "" for article in articles], limit=4)
    sentence_counter: Counter[str] = Counter(keywords[:5])
    recurring_focus = ", ".join(keywords[:4]) if keywords else "hlavní vývoj v tématu"
    summary = (
        f"Monitoring tématu {topic.name} zachytil {article_count} relevantních položek z {source_count} zdrojů. "
        f"Napříč zdroji se nejčastěji opakují okruhy {recurring_focus}."
    )

    happened_bits = title_points + [shorten_text(sentence, 120) for sentence in salient_sentences[:2]]
    what_happened = "\n".join(f"• {item}" for item in happened_bits[:5])

    why_it_matters = (
        f"Téma je důležité, protože se objevuje napříč {source_count} zdroji a má více navazujících úhlů pohledu. "
        f"Za prioritu lze považovat zejména {', '.join(keywords[:3]) if keywords else topic.name.lower()}, "
        f"což ukazuje na pokračující vývoj a potřebu průběžného sledování."
    )

    watch_words = keywords[3:8] if len(keywords) > 3 else keywords
    watchlist = (
        f"Dál sledovat: {', '.join(watch_words) if watch_words else topic.name.lower()}. "
        f"Silnější váhu mají zdroje {', '.join(source_domains[:4]) if source_domains else 'bez jasné dominance jednoho zdroje'}."
    )

    return {
        "summary": summary,
        "what_happened": what_happened,
        "why_it_matters": why_it_matters,
        "watchlist": watchlist,
        "key_points": title_points[:5],
        "article_ids": [article.id for article in articles[:6]],
        "source_count": source_count,
        "article_count": article_count,
    }


def generate_topic_brief(db: Session, topic: Topic) -> Brief | None:
    articles = _recent_topic_articles(db, topic.id)
    if not articles:
        return None
    articles = _ensure_content(db, articles)
    structured = _build_structured_sections(topic, articles)

    brief = db.scalar(select(Brief).where(Brief.topic_id == topic.id))
    if not brief:
        brief = Brief(topic_id=topic.id, title=f"{topic.name} — operativní briefing")

    brief.title = f"{topic.name} — operativní briefing"
    brief.summary = structured["summary"]
    brief.what_happened = structured["what_happened"]
    brief.why_it_matters = structured["why_it_matters"]
    brief.watchlist = structured["watchlist"]
    brief.source_count = structured["source_count"]
    brief.article_count = structured["article_count"]
    brief.status = "draft"
    brief.generated_at = utcnow()
    brief.updated_at = utcnow()
    brief.published_at = None
    brief.set_key_points(structured["key_points"])
    brief.set_article_ids(structured["article_ids"])
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief


def generate_all_briefs(db: Session) -> int:
    topics = db.scalars(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order.asc(), Topic.name.asc())).all()
    generated = 0
    for topic in topics:
        brief = generate_topic_brief(db, topic)
        if brief:
            generated += 1
    return generated


def publish_brief(db: Session, brief_id: str, publish: bool = True) -> Brief | None:
    brief = db.get(Brief, brief_id)
    if not brief:
        return None
    brief.status = "published" if publish else "draft"
    brief.published_at = utcnow() if publish else None
    brief.updated_at = utcnow()
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief
