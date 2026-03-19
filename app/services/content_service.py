from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import settings
from app.models.article import Article
from app.utils.security import utcnow


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ReserseBot/1.0; +https://example.local)",
    "Accept-Language": "cs,en;q=0.9",
}


def fetch_article_html(url: str) -> str | None:
    try:
        with httpx.Client(timeout=settings.article_fetch_timeout_seconds, follow_redirects=True, headers=DEFAULT_HEADERS) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except Exception:
        return None


def extract_main_text(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "form", "header", "footer", "nav"]):
        tag.decompose()

    paragraphs: list[str] = []
    for paragraph in soup.find_all("p"):
        text = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True)).strip()
        if len(text) >= 80:
            paragraphs.append(text)

    if not paragraphs:
        body_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
        return body_text[:12000] if len(body_text) > 120 else None

    unique_paragraphs: list[str] = []
    seen: set[str] = set()
    for item in paragraphs:
        if item in seen:
            continue
        seen.add(item)
        unique_paragraphs.append(item)
    return "\n\n".join(unique_paragraphs[:18])[:12000]


def enrich_article_content(db: Session, article: Article) -> Article:
    if article.full_text and article.extraction_status == "ok":
        return article

    html = fetch_article_html(article.url)
    article.extracted_at = utcnow()
    if not html:
        article.extraction_status = "failed"
        db.add(article)
        db.commit()
        db.refresh(article)
        return article

    full_text = extract_main_text(html)
    if full_text:
        article.full_text = full_text
        article.extraction_status = "ok"
    else:
        article.extraction_status = "empty"
    db.add(article)
    db.commit()
    db.refresh(article)
    return article
