import hashlib
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

from argon2 import PasswordHasher


password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except Exception:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_safe_redirect_url(url: str) -> bool:
    parsed = urlparse(url)
    return not parsed.netloc
