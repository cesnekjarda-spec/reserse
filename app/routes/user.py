from io import BytesIO

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from app.db import SessionLocal
from app.models.article import Article
from app.models.brief import Brief
from app.models.source import Source
from app.models.subscription import UserArticleRead, UserTopicSubscription
from app.models.topic import Topic
from app.models.user import User
from app.services.audio_service import (
    build_audio_research_text,
    build_listening_script_from_text,
    build_listening_script_preview,
    synthesize_elevenlabs_mp3_bytes,
    synthesize_mp3_bytes,
)
from app.services.external_provider_service import (
    build_article_prompt,
    build_brief_prompt,
    build_provider_url,
    build_topic_prompt,
    get_enabled_providers_for_user,
    get_user_provider_preferences,
    save_user_provider_preferences,
)
from app.services.provider_api_service import run_provider_research
from app.services.research_extension_service import (
    SUPPORTED_PROVIDER_CODES,
    build_external_research_prompt,
    build_provider_launcher_context,
)
from app.services.pricing_service import get_user_monthly_topic_pricing
from app.services.tts_connection_service import (
    DEFAULT_MODEL_ID,
    DEFAULT_PROVIDER_CODE,
    decrypt_api_key,
    describe_connection,
    get_or_create_user_tts_connection,
    save_user_tts_connection,
)
from app.utils.templates import template_context
from app.services.vip_pricing_sync_service import push_user_pricing_to_vip


router = APIRouter(tags=["user"])


def require_user(request: Request):
    return getattr(request.state, "current_user", None)


def _clean_export_text(value: str) -> str:
    return (value or "").replace("\r\n", "\n").strip()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    with SessionLocal() as db:
        topic_rows = db.scalars(
            select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order.asc(), Topic.name.asc())
        ).all()
        selected_ids = set(
            db.scalars(
                select(UserTopicSubscription.topic_id).where(UserTopicSubscription.user_id == current_user.id)
            ).all()
        )
        read_ids = set(
            db.scalars(select(UserArticleRead.article_id).where(UserArticleRead.user_id == current_user.id)).all()
        )
        provider_preferences = get_user_provider_preferences(db, current_user)
        enabled_providers = get_enabled_providers_for_user(db, current_user)
        tts_connection = get_or_create_user_tts_connection(db, current_user)

        pricing_summary = get_user_monthly_topic_pricing(db, user_id=current_user.id)

        if selected_ids:
            articles = db.scalars(
                select(Article)
                .options(joinedload(Article.source).joinedload(Source.topic))
                .join(Source, Source.id == Article.source_id)
                .where(Source.topic_id.in_(selected_ids))
                .order_by(desc(Article.published_at), desc(Article.created_at))
                .limit(60)
            ).unique().all()
            briefs = db.scalars(
                select(Brief)
                .options(joinedload(Brief.topic))
                .where(Brief.topic_id.in_(selected_ids), Brief.status == "published")
                .order_by(Brief.published_at.desc(), Brief.generated_at.desc())
            ).unique().all()
            selected_topics = [topic for topic in topic_rows if topic.id in selected_ids][:8]
        else:
            articles = []
            briefs = []
            selected_topics = []

        related_article_ids: list[str] = []
        for brief in briefs:
            related_article_ids.extend(brief.article_ids)
        related_articles = {}
        if related_article_ids:
            related_rows = db.scalars(
                select(Article)
                .options(joinedload(Article.source).joinedload(Source.topic))
                .where(Article.id.in_(related_article_ids))
            ).unique().all()
            related_articles = {article.id: article for article in related_rows}
        brief_related = {
            brief.id: [related_articles[article_id] for article_id in brief.article_ids if article_id in related_articles]
            for brief in briefs
        }
        brief_listen_preview = {
            brief.id: build_listening_script_preview(brief, brief_related.get(brief.id, []))
            for brief in briefs
        }
        brief_audio_payload = {
            brief.id: build_audio_research_payload(brief, brief_related.get(brief.id, []))
            for brief in briefs
        }

        def prompt_for_brief(provider, brief_obj):
            if provider.code in SUPPORTED_PROVIDER_CODES:
                return build_external_research_prompt(brief_obj, brief_related.get(brief_obj.id, []), provider.code)
            return build_brief_prompt(brief_obj)

        brief_external_links = {
            brief.id: [
                {
                    "name": provider.name,
                    "url": build_provider_url(provider, prompt_for_brief(provider, brief)),
                }
                for provider in enabled_providers
            ]
            for brief in briefs
        }
        topic_external_links = {
            topic.id: [
                {
                    "name": provider.name,
                    "url": build_provider_url(provider, build_topic_prompt(topic, mode="topic")),
                }
                for provider in enabled_providers
            ]
            for topic in selected_topics
        }
        article_external_links = {
            article.id: [
                {
                    "name": provider.name,
                    "url": build_provider_url(
                        provider,
                        build_article_prompt(
                            article.source.topic.name if article.source and article.source.topic else "obecné téma",
                            article.title,
                            article.summary,
                        ),
                    ),
                }
                for provider in enabled_providers
            ]
            for article in articles[:20]
        }

    return request.app.state.templates.TemplateResponse(
        "user_dashboard.html",
        template_context(
            request,
            topics=topic_rows,
            selected_ids=selected_ids,
            briefs=briefs,
            brief_related=brief_related,
            brief_external_links=brief_external_links,
            brief_listen_preview=brief_listen_preview,
            brief_audio_payload=brief_audio_payload,
            topic_external_links=topic_external_links,
            article_external_links=article_external_links,
            provider_preferences=provider_preferences,
            selected_topics=selected_topics,
            articles=articles,
            read_ids=read_ids,
            tts_connection=describe_connection(tts_connection),
            can_generate_tts=bool(tts_connection.is_enabled and tts_connection.api_key_encrypted and tts_connection.voice_id),
            pricing_summary=pricing_summary,
        ),
    )


@router.get("/briefs/{brief_id}/audio.mp3")
def brief_audio(request: Request, brief_id: str):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    with SessionLocal() as db:
        brief = db.scalar(select(Brief).options(joinedload(Brief.topic)).where(Brief.id == brief_id))
        if not brief:
            return RedirectResponse(url="/dashboard", status_code=303)
        if getattr(request.state, "current_role", current_user.role) != "admin" and brief.status != "published":
            return RedirectResponse(url="/dashboard", status_code=303)

        related_rows: list[Article] = []
        if brief.article_ids:
            related_rows = db.scalars(
                select(Article)
                .options(joinedload(Article.source).joinedload(Source.topic))
                .where(Article.id.in_(brief.article_ids))
            ).unique().all()

        audio_text = build_audio_research_text(brief, related_rows)
        mp3_bytes = synthesize_mp3_bytes(audio_text)
        filename = f"briefing-{brief.id}.mp3"
        return StreamingResponse(
            BytesIO(mp3_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )


@router.get("/briefs/{brief_id}/listen", response_class=HTMLResponse)
def brief_listen_script(request: Request, brief_id: str):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    with SessionLocal() as db:
        brief = db.scalar(select(Brief).options(joinedload(Brief.topic)).where(Brief.id == brief_id))
        if not brief:
            return RedirectResponse(url="/dashboard", status_code=303)
        if getattr(request.state, "current_role", current_user.role) != "admin" and brief.status != "published":
            return RedirectResponse(url="/dashboard", status_code=303)

        related_rows: list[Article] = []
        if brief.article_ids:
            related_rows = db.scalars(
                select(Article)
                .options(joinedload(Article.source).joinedload(Source.topic))
                .where(Article.id.in_(brief.article_ids))
            ).unique().all()
        audio_payload = build_audio_research_payload(brief, related_rows)
        listen_text = audio_payload.get("text", "")
        tts_connection = get_or_create_user_tts_connection(db, current_user)

    return request.app.state.templates.TemplateResponse(
        "brief_listen_script.html",
        template_context(
            request,
            brief=brief,
            listen_text=listen_text,
            audio_payload=audio_payload,
            related_articles=related_rows,
            tts_connection=describe_connection(tts_connection),
            can_generate_tts=bool(tts_connection.is_enabled and tts_connection.api_key_encrypted and tts_connection.voice_id),
        ),
    )


@router.get("/briefs/{brief_id}/listen.txt")
def brief_listen_script_txt(request: Request, brief_id: str):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    with SessionLocal() as db:
        brief = db.scalar(select(Brief).options(joinedload(Brief.topic)).where(Brief.id == brief_id))
        if not brief:
            return RedirectResponse(url="/dashboard", status_code=303)
        if getattr(request.state, "current_role", current_user.role) != "admin" and brief.status != "published":
            return RedirectResponse(url="/dashboard", status_code=303)
        related_rows: list[Article] = []
        if brief.article_ids:
            related_rows = db.scalars(
                select(Article).where(Article.id.in_(brief.article_ids))
            ).all()
        audio_payload = build_audio_research_payload(brief, related_rows)
        listen_text = audio_payload.get("text", "")

    return PlainTextResponse(
        listen_text,
        headers={"Content-Disposition": f'attachment; filename="brief-listen-{brief_id}.txt"'},
    )


@router.get("/research/launch/{provider_code}", response_class=HTMLResponse)
def research_launcher(
    request: Request,
    provider_code: str,
    q: str = Query(default=""),
    topic: str = Query(default=""),
):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    if provider_code not in SUPPORTED_PROVIDER_CODES:
        return RedirectResponse(url="/dashboard", status_code=303)

    prompt = (q or "").strip()
    if not prompt:
        prompt = f"Zpracuj poctivou rešerši k tématu {topic or 'dané téma'} a uveď zdroje, nejistoty a co sledovat dál."

    fallback_context = build_provider_launcher_context(provider_code, prompt)
    result = run_provider_research(provider_code, prompt)

    with SessionLocal() as db:
        tts_connection = get_or_create_user_tts_connection(db, current_user)
    tts_description = describe_connection(tts_connection)
    can_generate_tts = bool(tts_description.get("is_enabled") and tts_description.get("has_api_key") and tts_description.get("voice_id"))

    return request.app.state.templates.TemplateResponse(
        "research_launcher.html",
        template_context(
            request,
            provider_code=provider_code,
            provider_name=result.provider_name,
            prompt=prompt,
            external_url=fallback_context["external_url"],
            helper_text=result.helper_text,
            listen_text=result.listen_text,
            research_result=result,
            tts_connection=tts_description,
            can_generate_tts=can_generate_tts,
        ),
    )


@router.post("/tts/export.txt")
def export_tts_text(
    request: Request,
    title: str = Form(default="reserse"),
    text: str = Form(default=""),
):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    clean_text = _clean_export_text(text)
    if not clean_text:
        return PlainTextResponse("Chybí text pro export.", status_code=400)

    safe_title = "".join(ch for ch in (title or "reserse") if ch.isalnum() or ch in ("-", "_", " " )).strip().replace(" ", "-") or "reserse"
    filename = f"{safe_title}.txt"
    return PlainTextResponse(
        clean_text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/tts/elevenlabs.mp3")
def elevenlabs_text_to_speech(
    request: Request,
    title: str = Form(default="reserse"),
    text: str = Form(default=""),
):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    clean_text = (text or "").strip()
    if not clean_text:
        return PlainTextResponse("Chybí text pro ElevenLabs.", status_code=400)

    with SessionLocal() as db:
        connection = get_or_create_user_tts_connection(db, current_user)
        secret = decrypt_api_key(connection.api_key_encrypted)
        if not connection.is_enabled:
            return PlainTextResponse("ElevenLabs je u tohoto účtu vypnuté.", status_code=400)
        if not secret:
            return PlainTextResponse("Chybí nebo nejde dešifrovat uložený ElevenLabs API klíč.", status_code=400)
        if not connection.voice_id:
            return PlainTextResponse("Chybí ElevenLabs Voice ID.", status_code=400)
        try:
            mp3_bytes = synthesize_elevenlabs_mp3_bytes(
                clean_text,
                api_key=secret,
                voice_id=connection.voice_id,
                model_id=connection.model_id or DEFAULT_MODEL_ID,
            )
        except Exception as exc:
            detail = str(exc)
            if "401 Unauthorized" in detail:
                detail = (
                    "401 Unauthorized. ElevenLabs free účet může na sdílené serverové IP selhat, i když lokální test funguje. "
                    "Pro spolehlivé použití využij export scriptu nebo placený účet. Původní detail: " + detail
                )
            return PlainTextResponse(f"ElevenLabs API chyba: {detail}", status_code=502)

    safe_title = "".join(ch for ch in (title or "reserse") if ch.isalnum() or ch in ("-", "_", " ")).strip().replace(" ", "-") or "reserse"
    filename = f"{safe_title}.mp3"
    return StreamingResponse(
        BytesIO(mp3_bytes),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/dashboard/subscriptions")
def update_subscriptions(request: Request, topic_ids: list[str] = Form(default=[])):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        existing = db.scalars(select(UserTopicSubscription).where(UserTopicSubscription.user_id == current_user.id)).all()
        for row in existing:
            db.delete(row)
        db.commit()
        for topic_id in topic_ids:
            db.add(UserTopicSubscription(user_id=current_user.id, topic_id=topic_id))
        db.commit()
        fresh_user = db.get(User, current_user.id)
        push_user_pricing_to_vip(db, fresh_user, sync_trigger="subscriptions_update")
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/dashboard/providers")
def update_provider_preferences(request: Request, provider_ids: list[str] = Form(default=[])):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        fresh_user = db.get(User, current_user.id)
        if fresh_user:
            save_user_provider_preferences(db, fresh_user, provider_ids)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/dashboard/tts")
def update_tts_interface(
    request: Request,
    display_name: str = Form(default="ElevenLabs"),
    voice_id: str = Form(default=""),
    model_id: str = Form(default=DEFAULT_MODEL_ID),
    api_key: str = Form(default=""),
    note: str = Form(default=""),
    is_enabled: str | None = Form(default=None),
    clear_stored_key: str | None = Form(default=None),
):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    with SessionLocal() as db:
        fresh_user = db.get(User, current_user.id)
        if fresh_user:
            if clear_stored_key:
                connection = get_or_create_user_tts_connection(db, fresh_user)
                clear_api_key(connection)
                db.add(connection)
                db.commit()
            _, warning = save_user_tts_connection(
                db,
                fresh_user,
                provider_code=DEFAULT_PROVIDER_CODE,
                display_name=display_name,
                voice_id=voice_id,
                model_id=model_id,
                api_key=api_key,
                note=note,
                is_enabled=bool(is_enabled),
            )
            redirect_url = "/dashboard?tts_saved=1"
            if warning:
                redirect_url += "&tts_warning=1"
            return RedirectResponse(url=redirect_url, status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)




@router.post("/dashboard/tts/test")
def test_tts_interface(request: Request):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    with SessionLocal() as db:
        connection = get_or_create_user_tts_connection(db, current_user)
        secret = decrypt_api_key(connection.api_key_encrypted)
        if not connection.is_enabled:
            return PlainTextResponse("ElevenLabs je u tohoto účtu vypnuté.", status_code=400)
        if not secret:
            return PlainTextResponse("Chybí nebo nejde dešifrovat uložený ElevenLabs API klíč.", status_code=400)
        if not connection.voice_id:
            return PlainTextResponse("Chybí ElevenLabs Voice ID.", status_code=400)
        try:
            _ = synthesize_elevenlabs_mp3_bytes(
                "Dobry den, toto je kratky test.",
                api_key=secret,
                voice_id=connection.voice_id,
                model_id=connection.model_id or DEFAULT_MODEL_ID,
            )
            return PlainTextResponse(
                f"ElevenLabs test OK. Voice ID {connection.voice_id}, ulozeny klic konci na …{connection.api_key_last4 or '????' }.",
                status_code=200,
            )
        except Exception as exc:
            detail = str(exc)
            if "401 Unauthorized" in detail:
                detail = (
                    "401 Unauthorized. U free ElevenLabs účtů může přímé serverové volání ze sdílené IP selhávat, i když lokální test vrací MP3. "
                    "Pro běžné použití využij export scriptu nebo placený účet. Původní detail: " + detail
                )
            return PlainTextResponse(
                f"ElevenLabs test chyba. Voice ID {connection.voice_id}, ulozeny klic konci na …{connection.api_key_last4 or '????' }. Detail: {detail}",
                status_code=502,
            )

@router.post("/articles/{article_id}/read")
def mark_read(request: Request, article_id: str):
    current_user = require_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    with SessionLocal() as db:
        existing = db.scalar(
            select(UserArticleRead).where(
                UserArticleRead.user_id == current_user.id,
                UserArticleRead.article_id == article_id,
            )
        )
        if not existing:
            db.add(UserArticleRead(user_id=current_user.id, article_id=article_id))
            db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)
