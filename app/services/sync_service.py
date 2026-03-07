from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.source import Source
from app.models.sync import SyncRun, SyncRunItem
from app.services.rss_service import build_guid_hash, clean_summary, parse_feed, parse_published


def run_sync(db: Session, triggered_by: str = "local") -> dict:
    sync_run = SyncRun(status="running", triggered_by=triggered_by)
    db.add(sync_run)
    db.commit()
    db.refresh(sync_run)

    sources = db.scalars(select(Source).where(Source.is_active.is_(True)).order_by(Source.name.asc())).all()
    sync_run.sources_total = len(sources)
    db.add(sync_run)
    db.commit()

    articles_created = 0
    sources_ok = 0
    sources_failed = 0

    try:
        for source in sources:
            item = SyncRunItem(sync_run_id=sync_run.id, source_id=source.id, status="success")
            db.add(item)

            try:
                feed = parse_feed(source.rss_url)
                entries = getattr(feed, "entries", []) or []
                item.items_seen = len(entries)
                inserted_here = 0

                for entry in entries:
                    title = getattr(entry, "title", None) or "(bez názvu)"
                    url = getattr(entry, "link", None)
                    if not url:
                        continue

                    published_at = parse_published(entry)
                    external_guid = getattr(entry, "id", None) or getattr(entry, "guid", None)
                    guid_hash = build_guid_hash(url, title, published_at, external_guid)

                    existing = db.scalar(select(Article).where(Article.guid_hash == guid_hash))
                    if existing:
                        continue

                    article = Article(
                        source_id=source.id,
                        external_guid=external_guid,
                        guid_hash=guid_hash,
                        title=title[:500],
                        url=url[:1000],
                        published_at=published_at,
                        summary=clean_summary(getattr(entry, "summary", None) or getattr(entry, "description", None)),
                        author=(getattr(entry, "author", None) or None),
                    )
                    db.add(article)
                    inserted_here += 1

                item.items_inserted = inserted_here
                articles_created += inserted_here
                sources_ok += 1
                db.add(item)
                db.commit()

            except Exception as exc:
                item.status = "failed"
                item.error_message = str(exc)[:2000]
                sources_failed += 1
                db.add(item)
                db.commit()

        sync_run.status = "partial" if sources_failed else "success"
        sync_run.sources_ok = sources_ok
        sync_run.sources_failed = sources_failed
        sync_run.articles_created = articles_created
        sync_run.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        db.add(sync_run)
        db.commit()

        return {
            "ok": True,
            "status": sync_run.status,
            "sources_total": sync_run.sources_total,
            "sources_ok": sources_ok,
            "sources_failed": sources_failed,
            "articles_created": articles_created,
        }

    except Exception as exc:
        sync_run.status = "failed"
        sync_run.error_message = str(exc)[:2000]
        sync_run.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        db.add(sync_run)
        db.commit()
        return {"ok": False, "status": "failed", "error": str(exc)}
