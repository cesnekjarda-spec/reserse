from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.article import Article
from app.models.source import Source
from app.models.sync import SyncRun, SyncRunItem
from app.services.rss_service import build_guid_hash, clean_summary, parse_feed, parse_published
from app.utils.security import utcnow


def run_sync(db: Session, triggered_by: str = "manual") -> dict:
    sync_run = SyncRun(triggered_by=triggered_by, status="running")
    db.add(sync_run)
    db.commit()
    db.refresh(sync_run)

    created_total = 0
    error_total = 0
    skipped_duplicates = 0

    sources = db.scalars(
        select(Source).options(joinedload(Source.topic)).where(Source.is_active.is_(True)).order_by(Source.name.asc())
    ).all()

    sync_run.total_sources = len(sources)
    db.add(sync_run)
    db.commit()

    for source in sources:
        item = SyncRunItem(
            sync_run_id=sync_run.id,
            source_name=source.name,
            source_rss_url=source.rss_url,
            status="ok",
            articles_created=0,
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        try:
            feed = parse_feed(source.rss_url)
            entries = getattr(feed, "entries", []) or []

            for entry in entries[:30]:
                title = getattr(entry, "title", "").strip()
                url = getattr(entry, "link", "").strip()

                if not title or not url:
                    continue

                published_at = parse_published(entry)
                external_guid = getattr(entry, "id", None) or getattr(entry, "guid", None)
                guid_hash = build_guid_hash(url, title, published_at, external_guid)

                existing = db.scalar(select(Article.id).where(Article.guid_hash == guid_hash))
                if existing:
                    skipped_duplicates += 1
                    continue

                article = Article(
                    source_id=source.id,
                    title=title,
                    url=url,
                    guid_hash=guid_hash,
                    external_guid=external_guid,
                    summary=clean_summary(
                        getattr(entry, "summary", None) or getattr(entry, "description", None)
                    ),
                    published_at=published_at,
                )

                db.add(article)

                try:
                    db.flush()
                    item.articles_created += 1
                    created_total += 1
                except IntegrityError:
                    db.rollback()
                    skipped_duplicates += 1

                    item = db.get(SyncRunItem, item.id)
                    sync_run = db.get(SyncRun, sync_run.id)
                    continue

            db.add(item)
            db.commit()

        except Exception as exc:
            db.rollback()

            item = db.get(SyncRunItem, item.id) or item
            item.status = "error"
            item.message = str(exc)

            db.add(item)
            db.commit()
            error_total += 1

    sync_run = db.get(SyncRun, sync_run.id)
    sync_run.status = "finished"
    sync_run.finished_at = utcnow()
    sync_run.total_articles_created = created_total
    sync_run.total_errors = error_total

    db.add(sync_run)
    db.commit()

    return {
        "sources": len(sources),
        "articles_created": created_total,
        "errors": error_total,
        "skipped_duplicates": skipped_duplicates,
        "sync_run_id": sync_run.id,
    }
