from __future__ import annotations

from datetime import datetime, timezone
import re
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.models.user_tts import UserTtsConnection


DEFAULT_PROVIDER_CODE = "elevenlabs"
DEFAULT_DISPLAY_NAME = "ElevenLabs"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"


class TtsSecretUnavailableError(RuntimeError):
    pass


def _build_fernet_key(secret: str) -> bytes:
    clean = secret.strip().encode("utf-8")
    try:
        Fernet(clean)
        return clean
    except Exception:
        digest = hashlib.sha256(clean).digest()
        return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    secret = settings.user_secret_encryption_key
    if not secret:
        raise TtsSecretUnavailableError("USER_SECRET_ENCRYPTION_KEY is not configured")
    return Fernet(_build_fernet_key(secret))


def _compact_secretish(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "")


def mask_api_key(value: str | None) -> str | None:
    clean = _compact_secretish(value)
    if not clean:
        return None
    return clean[-4:] if len(clean) >= 4 else clean


def encrypt_api_key(value: str | None) -> str | None:
    clean = _compact_secretish(value)
    if not clean:
        return None
    fernet = _get_fernet()
    return fernet.encrypt(clean.encode("utf-8")).decode("utf-8")


def decrypt_api_key(value: str | None) -> str | None:
    if not value:
        return None
    try:
        fernet = _get_fernet()
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except (TtsSecretUnavailableError, InvalidToken):
        return None


def clear_api_key(connection: UserTtsConnection) -> None:
    connection.api_key_encrypted = None
    connection.api_key_last4 = None


def get_user_tts_connection(db: Session, user: User, provider_code: str = DEFAULT_PROVIDER_CODE) -> UserTtsConnection | None:
    return db.scalar(
        select(UserTtsConnection).where(
            UserTtsConnection.user_id == user.id,
            UserTtsConnection.provider_code == provider_code,
        )
    )


def get_or_create_user_tts_connection(db: Session, user: User, provider_code: str = DEFAULT_PROVIDER_CODE) -> UserTtsConnection:
    connection = get_user_tts_connection(db, user, provider_code=provider_code)
    if connection:
        return connection
    connection = UserTtsConnection(
        user_id=user.id,
        provider_code=provider_code,
        display_name=DEFAULT_DISPLAY_NAME,
        model_id=DEFAULT_MODEL_ID,
        is_enabled=False,
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def describe_connection(connection: UserTtsConnection | None) -> dict:
    if not connection:
        return {
            "provider_code": DEFAULT_PROVIDER_CODE,
            "display_name": DEFAULT_DISPLAY_NAME,
            "voice_id": "",
            "model_id": DEFAULT_MODEL_ID,
            "has_api_key": False,
            "api_key_last4": None,
            "is_enabled": False,
            "note": "",
            "status": "Rozhraní je připravené. Pro free ElevenLabs účty může přímé serverové volání na sdílené IP selhávat, proto je nejspolehlivější export scriptu.",
        }

    has_api_key = bool(connection.api_key_encrypted)
    status = "Rozhraní je bez API klíče."
    if has_api_key and connection.is_enabled:
        status = "Přímé ElevenLabs TTS je zapnuté. U free účtů na sdíleném serveru může selhat; spolehlivější je export scriptu nebo placený účet."
    elif has_api_key:
        status = "Klíč je uložený. Přímé TTS volání je vypnuté a můžeš používat jen export scriptu pro ruční vložení do ElevenLabs."

    return {
        "provider_code": connection.provider_code,
        "display_name": connection.display_name or DEFAULT_DISPLAY_NAME,
        "voice_id": connection.voice_id or "",
        "model_id": connection.model_id or DEFAULT_MODEL_ID,
        "has_api_key": has_api_key,
        "api_key_last4": connection.api_key_last4,
        "is_enabled": bool(connection.is_enabled),
        "note": connection.note or "",
        "status": status,
    }


def save_user_tts_connection(
    db: Session,
    user: User,
    *,
    provider_code: str = DEFAULT_PROVIDER_CODE,
    display_name: str | None = None,
    voice_id: str | None = None,
    model_id: str | None = None,
    api_key: str | None = None,
    note: str | None = None,
    is_enabled: bool = False,
) -> tuple[UserTtsConnection, str | None]:
    connection = get_or_create_user_tts_connection(db, user, provider_code=provider_code)
    connection.display_name = (display_name or DEFAULT_DISPLAY_NAME).strip() or DEFAULT_DISPLAY_NAME
    connection.voice_id = _compact_secretish(voice_id) or None
    connection.model_id = (model_id or DEFAULT_MODEL_ID).strip() or DEFAULT_MODEL_ID
    connection.note = (note or "").strip() or None
    connection.is_enabled = bool(is_enabled)
    connection.updated_at = datetime.now(timezone.utc)

    warning = None
    clean_key = _compact_secretish(api_key)
    if clean_key:
        try:
            connection.api_key_encrypted = encrypt_api_key(clean_key)
            connection.api_key_last4 = mask_api_key(clean_key)
        except TtsSecretUnavailableError:
            warning = "API klíč nebyl uložen, protože chybí USER_SECRET_ENCRYPTION_KEY v prostředí. Metadata rozhraní byla uložena."
            connection.api_key_encrypted = None
            connection.api_key_last4 = None

    db.add(connection)
    try:
        db.commit()
        db.refresh(connection)
    except Exception:
        db.rollback()
        raise

    return connection, warning
