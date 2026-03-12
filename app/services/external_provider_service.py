from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.brief import Brief
from app.models.provider import ExternalProvider, UserProviderPreference
from app.models.topic import Topic
from app.models.user import User
from app.utils.text import shorten_text


DEFAULT_EXTERNAL_PROVIDERS = [
    {
        "code": "google-search",
        "name": "Google AI",
        "description": "Širší webový dotaz v Google AI Mode.",
        "url_template": "https://www.google.com/search?udm=50&q={query}",
        "sort_order": 1,
    },
    {
        "code": "perplexity-search",
        "name": "Perplexity Search",
        "description": "Rešeršní dotaz v Perplexity.",
        "url_template": "https://www.perplexity.ai/search/?q={query}",
        "sort_order": 2,
    },
    {
        "code": "kagi-assistant",
        "name": "Kagi Assistant",
        "description": "AI rešeršní dotaz v Kagi Assistantu s webovým kontextem.",
        "url_template": "https://kagi.com/assistant?internet=true&q={query}",
        "sort_order": 3,
    },
    {
        "code": "kagi-search",
        "name": "Kagi Search",
        "description": "Klasické vyhledávání v Kagi pro rychlé ověření a dohledání zdrojů.",
        "url_template": "https://kagi.com/search?q={query}",
        "sort_order": 4,
    },
]


def ensure_external_providers(db: Session) -> None:
    for item in DEFAULT_EXTERNAL_PROVIDERS:
        provider = db.scalar(select(ExternalProvider).where(ExternalProvider.code == item["code"]))
        if not provider:
            provider = ExternalProvider(code=item["code"])
        provider.name = item["name"]
        provider.description = item["description"]
        provider.url_template = item["url_template"]
        provider.sort_order = item["sort_order"]
        provider.is_active = True
        db.add(provider)

    for stale_code in {"google-news", "bing-news", "microsoft-copilot"}:
        stale = db.scalar(select(ExternalProvider).where(ExternalProvider.code == stale_code))
        if stale:
            db.delete(stale)

    db.commit()


def ensure_user_provider_preferences(db: Session, user: User) -> None:
    providers = db.scalars(
        select(ExternalProvider)
        .where(ExternalProvider.is_active.is_(True))
        .order_by(ExternalProvider.sort_order.asc())
    ).all()

    for provider in providers:
        preference = db.scalar(
            select(UserProviderPreference).where(
                UserProviderPreference.user_id == user.id,
                UserProviderPreference.provider_id == provider.id,
            )
        )
        if not preference:
            db.add(
                UserProviderPreference(
                    user_id=user.id,
                    provider_id=provider.id,
                    is_enabled=True,
                    sort_order=provider.sort_order,
                )
            )
    db.commit()


def get_user_provider_preferences(db: Session, user: User) -> list[UserProviderPreference]:
    ensure_user_provider_preferences(db, user)
    return db.scalars(
        select(UserProviderPreference)
        .options(joinedload(UserProviderPreference.provider))
        .where(UserProviderPreference.user_id == user.id)
        .order_by(UserProviderPreference.sort_order.asc(), UserProviderPreference.created_at.asc())
    ).unique().all()


def save_user_provider_preferences(db: Session, user: User, enabled_provider_ids: list[str]) -> None:
    preferences = get_user_provider_preferences(db, user)
    enabled_set = set(enabled_provider_ids)
    for preference in preferences:
        preference.is_enabled = preference.provider_id in enabled_set
        db.add(preference)
    db.commit()


def get_enabled_providers_for_user(db: Session, user: User) -> list[ExternalProvider]:
    preferences = get_user_provider_preferences(db, user)
    return [
        pref.provider
        for pref in preferences
        if pref.is_enabled and pref.provider and pref.provider.is_active
    ]


def build_topic_prompt(topic: Topic | str, mode: str = "topic") -> str:
    topic_name = topic.name if hasattr(topic, "name") else str(topic)

    if mode == "topic":
        return (
            f"Vytvoř operativní rešerši k tématu {topic_name}. "
            f"Zaměř se na 5 nejnovějších a nejdůležitějších zpráv, "
            f"u každé napiš co se stalo, proč je to důležité a co sledovat dál. "
            f"Preferuj důvěryhodné zdroje a posledních 7 dní."
        )

    return f"Shrň hlavní vývoj v tématu {topic_name} za posledních 7 dní."


def build_brief_prompt(brief: Brief) -> str:
    points = "; ".join(brief.key_points[:4])
    topic_name = brief.topic.name if brief.topic else "dané téma"
    return (
        f"Navaz na briefing k tématu {topic_name}. "
        f"Pracuj s okruhy {points}. "
        f"Rozšiř rešerši o kontext, dopady a protichůdné interpretace, "
        f"ale drž se posledních 7 dní a důvěryhodných zdrojů."
    )


def build_article_prompt(topic_name: str, article_title: str, article_summary: str | None = None) -> str:
    base = f"Zpracuj rešerši k článku {article_title}. Téma: {topic_name}."
    if article_summary:
        base += f" Výchozí anotace: {shorten_text(article_summary, 220)}."
    base += " Doplň související zdroje, kontext a nejdůležitější návaznosti z posledních dní."
    return base


def build_provider_url(provider: ExternalProvider, prompt: str) -> str:
    return provider.url_template.replace("{query}", quote_plus(prompt))
