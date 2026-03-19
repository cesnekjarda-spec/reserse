from __future__ import annotations

from urllib.parse import quote_plus

from app.models.article import Article
from app.models.brief import Brief
from app.utils.text import normalize_whitespace, shorten_text


SUPPORTED_PROVIDER_CODES = {"exa-research", "tavily-research"}


def _related_url_block(related_articles: list[Article]) -> str:
    urls: list[str] = []
    for article in related_articles[:6]:
        if article.url and article.url.startswith("http"):
            urls.append(article.url.strip())
    if not urls:
        return ""
    return "\n\nPoužij jako výchozí veřejné zdroje i tyto URL:\n" + "\n".join(urls)


def build_external_research_prompt(brief: Brief, related_articles: list[Article], provider_code: str) -> str:
    topic_name = brief.topic.name if brief.topic else "dané téma"
    related_context = _related_url_block(related_articles)
    base = normalize_whitespace(
        f"Zpracuj poctivou rešerši k tématu {topic_name}. "
        f"Vyjdi z tohoto briefu: {brief.title}. Shrnutí: {brief.summary}. "
        f"Co se děje: {brief.what_happened}. Proč je to důležité: {brief.why_it_matters}. "
        f"Co dál sledovat: {brief.watchlist}."
    )
    key_points = "; ".join(brief.key_points[:6])
    if provider_code == "exa-research":
        return (
            base
            + f" Doplň nezávislou webovou rešerši, odděl jistá fakta od nejistot, ukaž rozpory mezi zdroji a přidej krátký závěr. "
            + f" Zaměř se na posledních 7 až 14 dní. Klíčové body: {key_points}."
            + related_context
        )
    return (
        base
        + f" Proveď poctivou webovou rešerši, vyber nejdůležitější nové informace, zvaž i protichůdné interpretace a napiš výsledný report v češtině. "
        + f" V závěru uveď 3 až 5 bodů co sledovat dál. Klíčové body: {key_points}."
        + related_context
    )


def build_provider_launcher_context(provider_code: str, prompt: str) -> dict:
    provider_name = "Exa Research" if provider_code == "exa-research" else "Tavily Research"
    external_url = None
    helper_text = ""
    if provider_code == "exa-research":
        helper_text = (
            "Tato větev umí po doplnění EXA_API_KEY zavolat živou webovou rešerši přes Exa API, "
            "zobrazit výsledek a připravit zvlášť i text upravený pro poslech."
        )
    elif provider_code == "tavily-research":
        helper_text = (
            "Tato větev umí po doplnění TAVILY_API_KEY zavolat živou webovou rešerši přes Tavily API, "
            "zobrazit výsledek a připravit zvlášť i text upravený pro poslech."
        )
    return {
        "provider_name": provider_name,
        "prompt": prompt,
        "external_url": external_url,
        "helper_text": helper_text,
    }


def build_launch_query(prompt: str, provider_code: str) -> str:
    label = "Exa Research" if provider_code == "exa-research" else "Tavily Research"
    return shorten_text(f"{label}: {prompt}", 1200)
