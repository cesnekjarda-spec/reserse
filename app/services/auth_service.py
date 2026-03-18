from __future__ import annotations

from io import BytesIO
from typing import Iterable

import httpx
from google import genai
from google.genai.types import GenerateContentConfig
from gtts import gTTS

from app.config import settings
from app.models.article import Article
from app.models.brief import Brief
from app.utils.text import normalize_whitespace, shorten_text


def _article_title_block(related_articles: list[Article], limit: int = 4) -> str:
    titles = [article.title for article in related_articles[:limit] if article.title]
    return " ".join(f"Důležitý zdroj: {shorten_text(title, 160)}." for title in titles)


def build_listening_script_preview(brief: Brief, related_articles: list[Article]) -> str:
    intro = f"Poslechový přehled k tématu {brief.topic.name if brief.topic else 'téma'}."
    return normalize_whitespace(
        f"{intro} {brief.title}. Hlavní shrnutí: {brief.summary}. "
        f"Teď stručně k tomu, co se skutečně děje: {brief.what_happened}. "
        f"Pro posluchače je důležité hlavně toto: {brief.why_it_matters}. "
        f"A dál se vyplatí sledovat: {brief.watchlist}. "
        f"{_article_title_block(related_articles, limit=3)}"
    )


def _build_fallback_script(brief: Brief, related_articles: list[Article]) -> str:
    topic_name = brief.topic.name if brief.topic else "téma"
    source_block = _article_title_block(related_articles)

    parts = [
        f"Operativní poslechová rešerše k tématu {topic_name}.",
        f"Hlavní linie dnešního vývoje je tato: {brief.summary}.",
        f"V praxi se právě děje toto: {brief.what_happened}.",
        f"Pro posluchače je důležité hlavně to, že {brief.why_it_matters}.",
        f"V dalších dnech stojí za sledování zejména toto: {brief.watchlist}.",
    ]

    if source_block:
        parts.append(f"Rešerše vychází mimo jiné z těchto podkladů: {source_block}")

    parts.append("Tímto základní poslechová rešerše končí.")
    return normalize_whitespace(" ".join(parts))


def build_listening_script_from_text(title: str, body_text: str, topic_name: str | None = None) -> str:
    topic_intro = f" k tématu {topic_name}" if topic_name else ""
    return normalize_whitespace(
        f"Poslechový přepis{topic_intro}. {title}. "
        f"{body_text} "
        f"Konec přehledu."
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


def build_audio_research_payload(brief: Brief, related_articles: list[Article]) -> dict:
    urls = _collect_public_urls(related_articles)
    has_api_key = bool(settings.gemini_api_key)

    if has_api_key and urls:
        text = _gemini_audio_script(brief, related_articles)
        if text:
            return {
                "text": text,
                "source": "gemini",
                "label": "Gemini",
                "reason": "Výstup vznikl přes Gemini nad veřejnými URL článků.",
            }
        return {
            "text": _build_fallback_script(brief, related_articles),
            "source": "fallback",
            "label": "Fallback",
            "reason": "Gemini bylo k dispozici, ale pro tento brief nevrátilo použitelný text.",
        }

    if not has_api_key:
        return {
            "text": _build_fallback_script(brief, related_articles),
            "source": "fallback",
            "label": "Fallback",
            "reason": "Gemini není aktivní, protože chybí GEMINI_API_KEY.",
        }

    return {
        "text": _build_fallback_script(brief, related_articles),
        "source": "fallback",
        "label": "Fallback",
        "reason": "Gemini se pro tento brief nepoužilo, protože chybí veřejné URL článků.",
    }


def build_audio_research_text(brief: Brief, related_articles: list[Article]) -> str:
    payload = build_audio_research_payload(brief, related_articles)
    return payload.get("text", "")


def synthesize_mp3_bytes(text: str) -> bytes:
    fp = BytesIO()
    tts = gTTS(text=text, lang=settings.audio_tts_lang)
    tts.write_to_fp(fp)
    return fp.getvalue()


def synthesize_elevenlabs_mp3_bytes(
    text: str,
    *,
    api_key: str,
    voice_id: str,
    model_id: str | None = None,
) -> bytes:
    clean_text = normalize_whitespace(text)
    if not clean_text:
        raise ValueError("Text pro ElevenLabs je prázdný")
    if not voice_id:
        raise ValueError("Chybí ElevenLabs voice_id")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    params = {"output_format": "mp3_44100_128"}
    payload = {
        "text": shorten_text(clean_text, 4500),
        "model_id": model_id or "eleven_multilingual_v2",
        "language_code": "cs",
    }
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    with httpx.Client(timeout=settings.provider_request_timeout_seconds) as client:
        response = client.post(url, params=params, json=payload, headers=headers)
        response.raise_for_status()
        return response.content
