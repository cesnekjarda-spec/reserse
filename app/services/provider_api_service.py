from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import httpx

from app.config import settings
from app.utils.text import normalize_whitespace, shorten_text


@dataclass
class ProviderResearchResult:
    provider_code: str
    provider_name: str
    prompt: str
    helper_text: str
    status: str
    status_label: str
    result_text: str | None = None
    listen_text: str | None = None
    citations: list[dict[str, str]] | None = None
    error_message: str | None = None


class ProviderAPIError(RuntimeError):
    pass


PROVIDER_NAMES = {
    "exa-research": "Exa Research",
    "tavily-research": "Tavily Research",
}


PROVIDER_HELPERS = {
    "exa-research": "Živá webová rešerše přes Exa API s citacemi.",
    "tavily-research": "Živá webová rešerše přes Tavily API s odpovědí a zdroji.",
}


def _provider_name(provider_code: str) -> str:
    return PROVIDER_NAMES.get(provider_code, provider_code)


def _provider_helper(provider_code: str) -> str:
    return PROVIDER_HELPERS.get(provider_code, "Živá webová rešerše.")


def _citations_from_exa(items: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    for item in items or []:
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        title = normalize_whitespace(str(item.get("title") or url))
        snippet = normalize_whitespace(str(item.get("text") or item.get("highlight") or ""))
        citations.append({
            "title": shorten_text(title, 180),
            "url": url,
            "snippet": shorten_text(snippet, 320) if snippet else "",
        })
    return citations


def _citations_from_tavily(items: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    for item in items or []:
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        title = normalize_whitespace(str(item.get("title") or url))
        snippet = normalize_whitespace(str(item.get("content") or item.get("raw_content") or ""))
        citations.append({
            "title": shorten_text(title, 180),
            "url": url,
            "snippet": shorten_text(snippet, 320) if snippet else "",
        })
    return citations


def _extract_tavily_query(prompt: str) -> str:
    clean = normalize_whitespace(prompt)
    if len(clean) <= 380:
        return clean

    topic_match = re.search(r"tématu\s+([^\.]+)", clean, flags=re.IGNORECASE)
    topic = topic_match.group(1).strip() if topic_match else "dané téma"

    key_points_match = re.search(r"Klíčové body:\s*(.+)$", clean, flags=re.IGNORECASE)
    key_points_raw = key_points_match.group(1).strip() if key_points_match else ""
    key_points = []
    if key_points_raw:
        for part in re.split(r"[;,.]", key_points_raw):
            item = normalize_whitespace(part)
            if item and len(item) > 2:
                key_points.append(item)
            if len(key_points) >= 4:
                break

    urls = re.findall(r"https?://\S+", clean)
    domain_hints = []
    for url in urls[:3]:
        domain = re.sub(r"^https?://", "", url).split("/")[0].strip()
        domain = domain.replace("www.", "")
        if domain:
            domain_hints.append(domain)

    parts = [
        f"Poctivá webová rešerše: {topic}",
        "Zaměř se na nové informace za posledních 7 až 14 dní",
        "odděl jistá fakta od nejistot",
        "přidej zdroje a co sledovat dál",
    ]
    if key_points:
        parts.append("Klíčové okruhy: " + ", ".join(key_points))
    if domain_hints:
        parts.append("Vezmi v úvahu i tyto zdrojové okruhy: " + ", ".join(domain_hints))

    query = ". ".join(parts)
    return shorten_text(normalize_whitespace(query), 380)


def _tavily_answer_from_citations(citations: list[dict[str, str]]) -> str:
    if not citations:
        return ""

    lines: list[str] = []
    for idx, item in enumerate(citations[:5]):
        title = normalize_whitespace(item.get("title") or f"Zdroj {idx + 1}")
        snippet = normalize_whitespace(item.get("snippet") or "")
        if snippet:
            lines.append(f"{idx + 1}. {title}: {shorten_text(snippet, 220)}")
        else:
            lines.append(f"{idx + 1}. {title}.")

    summary = " ".join(lines)
    return normalize_whitespace(shorten_text(summary, 1200))


def _listen_text(provider_name: str, result_text: str, citations: list[dict[str, str]]) -> str:
    source_titles = "; ".join(c["title"] for c in citations[:4] if c.get("title"))
    body = normalize_whitespace(result_text)
    if source_titles:
        body += f" Zdroje, ze kterých rešerše vychází: {source_titles}."
    return normalize_whitespace(
        f"Poslechový přehled od poskytovatele {provider_name}. {shorten_text(body, 4500)} Konec přehledu."
    )


def _build_manual_result(provider_code: str, prompt: str, error_message: str) -> ProviderResearchResult:
    provider_name = _provider_name(provider_code)
    helper_text = _provider_helper(provider_code)
    fallback_text = (
        f"Nepodařilo se automaticky získat živou rešerši přes {provider_name}. "
        f"Můžeš zatím použít připravený prompt a po opravě klíče nebo nastavení dotaz zopakovat."
    )
    return ProviderResearchResult(
        provider_code=provider_code,
        provider_name=provider_name,
        prompt=prompt,
        helper_text=helper_text,
        status="fallback",
        status_label="Použit záložní režim",
        result_text=fallback_text,
        listen_text=_listen_text(provider_name, fallback_text, []),
        citations=[],
        error_message=error_message,
    )


def _run_exa(prompt: str) -> ProviderResearchResult:
    if not settings.exa_api_key:
        return _build_manual_result("exa-research", prompt, "Chybí EXA_API_KEY v prostředí Renderu.")

    url = "https://api.exa.ai/answer"
    headers = {
        "x-api-key": settings.exa_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "query": prompt,
        "text": True,
    }
    try:
        with httpx.Client(timeout=settings.provider_request_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        return _build_manual_result("exa-research", prompt, f"Exa API chyba: {exc}")

    answer = normalize_whitespace(str(data.get("answer") or ""))
    citations = _citations_from_exa(data.get("citations"))
    if not answer:
        answer = "Exa nevrátila hotový text odpovědi, ale můžeš zkontrolovat citované zdroje níže."

    provider_name = _provider_name("exa-research")
    return ProviderResearchResult(
        provider_code="exa-research",
        provider_name=provider_name,
        prompt=prompt,
        helper_text=_provider_helper("exa-research"),
        status="ok",
        status_label="Živá rešerše načtena",
        result_text=answer,
        listen_text=_listen_text(provider_name, answer, citations),
        citations=citations,
    )


def _run_tavily(prompt: str) -> ProviderResearchResult:
    if not settings.tavily_api_key:
        return _build_manual_result("tavily-research", prompt, "Chybí TAVILY_API_KEY v prostředí Renderu.")

    url = "https://api.tavily.com/search"
    headers = {
        "Authorization": f"Bearer {settings.tavily_api_key}",
        "Content-Type": "application/json",
    }

    # Tavily má limit délky query 400 znaků. Proto prompt převádíme na kratší
    # vyhledávací dotaz, který zachová téma, klíčové body a případné zdrojové okruhy.
    search_query = _extract_tavily_query(prompt)
    payload_primary = {
        "query": search_query,
        "auto_parameters": True,
        "max_results": 6,
        "include_answer": "advanced",
        "include_favicon": True,
        "include_raw_content": False,
        "include_usage": True,
    }
    payload_fallback = {
        "query": search_query,
        "max_results": 5,
        "include_answer": True,
        "include_raw_content": False,
        "include_usage": True,
    }

    last_error = None
    data = None
    try:
        with httpx.Client(timeout=settings.provider_request_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload_primary)
            if response.status_code == 400:
                last_error = f"HTTP 400: {response.text}"
                response = client.post(url, headers=headers, json=payload_fallback)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        detail = last_error or str(exc)
        return _build_manual_result("tavily-research", prompt, f"Tavily API chyba: {detail}")

    answer = normalize_whitespace(str((data or {}).get("answer") or ""))
    citations = _citations_from_tavily(data.get("results"))
    if not answer and citations:
        answer = _tavily_answer_from_citations(citations)
    if not answer:
        answer = "Tavily nevrátila hotovou textovou odpověď, ale níže jsou nalezené zdroje."

    provider_name = _provider_name("tavily-research")
    return ProviderResearchResult(
        provider_code="tavily-research",
        provider_name=provider_name,
        prompt=prompt,
        helper_text=_provider_helper("tavily-research"),
        status="ok",
        status_label="Živá rešerše načtena",
        result_text=answer,
        listen_text=_listen_text(provider_name, answer, citations),
        citations=citations,
    )


def run_provider_research(provider_code: str, prompt: str) -> ProviderResearchResult:
    clean_prompt = normalize_whitespace(prompt)
    if provider_code == "exa-research":
        return _run_exa(clean_prompt)
    if provider_code == "tavily-research":
        return _run_tavily(clean_prompt)
    raise ProviderAPIError(f"Unsupported provider: {provider_code}")
