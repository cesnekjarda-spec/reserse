from __future__ import annotations

from io import BytesIO

import httpx
from google import genai
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


def _article_source_excerpt(article: Article, max_chars: int = 1600) -> str:
    chunks: list[str] = []
    if article.title:
        chunks.append(f"Titulek: {normalize_whitespace(article.title)}")
    if article.summary:
        chunks.append(f"Shrnutí: {normalize_whitespace(shorten_text(article.summary, 500))}")
    if article.full_text:
        chunks.append(f"Text článku: {normalize_whitespace(shorten_text(article.full_text, max_chars))}")
    return "\n".join(part for part in chunks if part).strip()


def _collect_article_context_blocks(related_articles: list[Article], limit: int = 6) -> list[str]:
    blocks: list[str] = []
    for idx, article in enumerate(related_articles[:limit], start=1):
        excerpt = _article_source_excerpt(article)
        if not excerpt:
            continue
        prefix = f"Podklad {idx}"
        if article.url:
            prefix += f" · URL: {article.url.strip()}"
        blocks.append(f"{prefix}\n{excerpt}")
    return blocks


def _gemini_reason_label(reason: str) -> str:
    return {
        "no_api_key": "Gemini API key není nastavený.",
        "no_article_context": "Pro tento briefing nejsou dostupné použitelné textové podklady článků.",
        "gemini_empty": "Gemini bylo k dispozici, ale pro tento brief nevrátilo použitelný text.",
        "gemini_error": "Gemini volání selhalo a aplikace přešla na fallback.",
    }.get(reason, "Audio výstup vznikl přes fallback.")


def _extract_text_from_genai_response(response) -> str:
    direct = normalize_whitespace(getattr(response, "text", "") or "")
    if direct:
        return direct

    chunks: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = normalize_whitespace(getattr(part, "text", "") or "")
            if part_text:
                chunks.append(part_text)
    return normalize_whitespace(" ".join(chunks))


def _gemini_audio_script_from_article_text(brief: Brief, related_articles: list[Article]) -> dict:
    if not settings.gemini_api_key:
        return {"ok": False, "reason": "no_api_key"}

    blocks = _collect_article_context_blocks(related_articles)
    if not blocks:
        return {"ok": False, "reason": "no_article_context"}

    topic_name = brief.topic.name if brief.topic else "téma"
    context_blob = "\n\n".join(blocks)
    prompt = normalize_whitespace(
        f"Jsi zkušený český rešeršér a rozhlasový editor. "
        f"Na základě přiložených textových podkladů připrav souvislou operativní poslechovou rešerši v češtině. "
        f"Nepiš odrážky, seznamy ani titulky. Piš v plných větách a tak, aby výstup zněl přirozeně při předčítání. "
        f"Text rozděl přirozeně takto: krátké uvedení tématu, hlavní vývoj, proč je důležitý, co sledovat dál. "
        f"Buď věcný, střízlivý a shrň to do přibližně 170 až 260 slov. "
        f"Téma: {topic_name}. "
        f"Výchozí briefing: {brief.summary}. {brief.what_happened}. {brief.why_it_matters}. {brief.watchlist}. "
        f"Podklady z článků: {context_blob}"
    )

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        text = _extract_text_from_genai_response(response)
        if not text:
            return {"ok": False, "reason": "gemini_empty"}
        return {
            "ok": True,
            "text": text,
            "context_article_count": len(blocks),
        }
    except Exception as exc:  # pragma: no cover - network/runtime variability
        return {
            "ok": False,
            "reason": "gemini_error",
            "error": shorten_text(str(exc), 240),
        }


def build_audio_research_payload(brief: Brief, related_articles: list[Article]) -> dict:
    gemini_result = _gemini_audio_script_from_article_text(brief, related_articles)
    if gemini_result.get("ok"):
        return {
            "text": gemini_result["text"],
            "source": "gemini",
            "label": "Gemini",
            "reason": None,
            "reason_label": "Gemini použilo interní textové podklady článků.",
            "context_article_count": gemini_result.get("context_article_count", 0),
        }

    reason = gemini_result.get("reason") or "fallback"
    error = gemini_result.get("error")
    reason_label = _gemini_reason_label(reason)
    if error:
        reason_label = f"{reason_label} Detail: {error}"

    return {
        "text": _build_fallback_script(brief, related_articles),
        "source": "fallback",
        "label": "Fallback",
        "reason": reason,
        "reason_label": reason_label,
        "context_article_count": len(_collect_article_context_blocks(related_articles)),
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
