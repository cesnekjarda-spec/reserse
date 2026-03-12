from __future__ import annotations

from io import BytesIO
from typing import Iterable

from google import genai
from google.genai.types import GenerateContentConfig
from gtts import gTTS

from app.config import settings
from app.models.article import Article
from app.models.brief import Brief
from app.utils.text import normalize_whitespace, shorten_text


def _build_fallback_script(brief: Brief, related_articles: list[Article]) -> str:
    titles = [article.title for article in related_articles[:4] if article.title]
    title_block = " ".join(f"Důležitý zdroj: {shorten_text(title, 160)}." for title in titles)
    return normalize_whitespace(
        f"Audio briefing k tématu {brief.topic.name if brief.topic else 'téma'}. "
        f"{brief.title}. Shrnutí: {brief.summary}. Co se děje: {brief.what_happened}. "
        f"Proč je to důležité: {brief.why_it_matters}. Co dál sledovat: {brief.watchlist}. "
        f"{title_block}"
    )


def _collect_public_urls(related_articles: Iterable[Article]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for article in related_articles:
        if not article.url:
            continue
        url = article.url.strip()
        if not url.startswith("http"):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if len(urls) >= settings.audio_url_limit:
            break
    return urls


def _gemini_audio_script(brief: Brief, related_articles: list[Article]) -> str | None:
    if not settings.gemini_api_key:
        return None

    urls = _collect_public_urls(related_articles)
    if not urls:
        return None

    prompt = (
        "Pracuj jako zkušený rešeršér a rozhlasový editor. "
        "Na základě následujících veřejných URL vytvoř v češtině krátkou, věcnou a poslouchatelnou operativní rešerši. "
        "Nepoužívej odrážky. Piš v plných větách, přirozeně pro audio. "
        "Nejdřív jednou větou uveď hlavní téma, pak popiš 3 až 5 nejdůležitějších zjištění, proč jsou důležitá a co dál sledovat. "
        f"Zaměření tématu: {brief.topic.name if brief.topic else 'téma'}. "
        f"Výchozí briefing: {brief.summary}. {brief.what_happened}. {brief.why_it_matters}. {brief.watchlist}. "
        "Pracuj s těmito URL: " + " ".join(urls)
    )

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=GenerateContentConfig(tools=[{"url_context": {}}]),
        )
        text = normalize_whitespace(getattr(response, "text", "") or "")
        return text or None
    except Exception:
        return None


def build_audio_research_text(brief: Brief, related_articles: list[Article]) -> str:
    text = _gemini_audio_script(brief, related_articles)
    if text:
        return text
    return _build_fallback_script(brief, related_articles)


def synthesize_mp3_bytes(text: str) -> bytes:
    fp = BytesIO()
    tts = gTTS(text=text, lang=settings.audio_tts_lang)
    tts.write_to_fp(fp)
    return fp.getvalue()
