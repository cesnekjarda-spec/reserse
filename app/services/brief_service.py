from collections import Counter

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.article import Article
from app.models.brief import Brief
from app.models.source import Source
from app.models.topic import Topic
from app.services.content_service import enrich_article_content
from app.utils.security import utcnow
from app.utils.text import domain_from_url, extract_keywords, normalize_whitespace, shorten_text


def _recent_topic_articles(db: Session, topic_id: str, limit: int | None = None) -> list[Article]:
    return db.scalars(
        select(Article)
        .options(joinedload(Article.source).joinedload(Source.topic))
        .join(Source, Source.id == Article.source_id)
        .where(Source.topic_id == topic_id)
        .order_by(desc(Article.published_at), desc(Article.created_at))
        .limit(limit or settings.brief_article_limit)
    ).unique().all()


def _ensure_content(db: Session, articles: list[Article]) -> list[Article]:
    fetched = 0
    enriched: list[Article] = []
    for article in articles:
        if fetched < settings.brief_fetch_limit and not article.full_text:
            try:
                enrich_article_content(db, article)
                fetched += 1
            except Exception:
                pass
        enriched.append(article)
    return enriched


def _build_structured_sections(topic: Topic, articles: list[Article]) -> dict:
    article_count = len(articles)
    source_domains: list[str] = []
    all_keywords: list[str] = []
    title_points: list[str] = []

    for article in articles:
        domain = ""
        if article.source:
            domain = domain_from_url(article.source.website_url or article.source.rss_url)
        if domain:
            source_domains.append(domain)

        basis = article.full_text or article.summary or article.title
        all_keywords.extend(extract_keywords(basis, limit=8))

        point = shorten_text(article.title, 120)
        if point not in title_points:
            title_points.append(point)

    keyword_counter = Counter(all_keywords)
    keywords = [word for word, _count in keyword_counter.most_common(8)]
    source_count = len(set(source_domains))

    intro_titles = '; '.join(title_points[:3])
    summary = normalize_whitespace(
        f"Téma {topic.name} nyní pokrývá {article_count} relevantních článků z {source_count or 1} zdrojů. "
        f"Nejčastěji se objevují okruhy {', '.join(keywords[:5]) if keywords else topic.name.lower()}. "
        f"Aktuálně se mezi klíčové zprávy řadí: {intro_titles}."
    )

    what_happened = normalize_whitespace(
        f"V posledních dnech se v tématu {topic.name} opakují zejména tyto linie: {intro_titles}. "
        f"Zdroje se soustředí na {', '.join(keywords[:4]) if keywords else topic.name.lower()} a potvrzují zvýšenou aktivitu v tomto okruhu."
    )

    why_it_matters = normalize_whitespace(
        f"Téma je důležité proto, že se promítá do rozhodování firem, investorů i veřejné správy. "
        f"Při porovnání více zdrojů je patrné, že nejde o izolované zmínky, ale o sérii navazujících úhlů pohledu. "
        f"Za prioritu lze považovat zejména {', '.join(keywords[:3]) if keywords else topic.name.lower()}, "
        f"což ukazuje na pokračující vývoj a potřebu průběžného sledování."
    )

    watch_words = keywords[3:8] if len(keywords) > 3 else keywords
    watchlist = normalize_whitespace(
        f"Dál sledovat: {', '.join(watch_words) if watch_words else topic.name.lower()}. "
        f"Silnější váhu mají zdroje {', '.join(source_domains[:4]) if source_domains else 'bez jasné dominance jednoho zdroje'}."
    )

    return {
        'summary': summary,
        'what_happened': what_happened,
        'why_it_matters': why_it_matters,
        'watchlist': watchlist,
        'key_points': title_points[:5],
        'article_ids': [article.id for article in articles[:6]],
        'source_count': source_count,
        'article_count': article_count,
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
    brief.summary = structured['summary']
    brief.what_happened = structured['what_happened']
    brief.why_it_matters = structured['why_it_matters']
    brief.watchlist = structured['watchlist']
    brief.source_count = structured['source_count']
    brief.article_count = structured['article_count']
    brief.status = 'draft'
    brief.generated_at = utcnow()
    brief.updated_at = utcnow()
    brief.published_at = None
    brief.set_key_points(structured['key_points'])
    brief.set_article_ids(structured['article_ids'])
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
    brief.status = 'published' if publish else 'draft'
    brief.published_at = utcnow() if publish else None
    brief.updated_at = utcnow()
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief


def publish_all_briefs(db: Session) -> int:
    briefs = db.scalars(select(Brief).where(Brief.status != 'published')).all()
    changed = 0
    now = utcnow()
    for brief in briefs:
        brief.status = 'published'
        brief.published_at = now
        brief.updated_at = now
        db.add(brief)
        changed += 1
    db.commit()
    return changed


def render_and_publish_all_briefs(db: Session) -> dict:
    generated = generate_all_briefs(db)
    published = publish_all_briefs(db)
    return {'generated': generated, 'published': published}
