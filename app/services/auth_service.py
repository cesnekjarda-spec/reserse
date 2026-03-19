from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.session import UserSession
from app.models.user import User
from app.utils.security import (
    generate_session_token,
    hash_password,
    hash_token,
    utcnow,
    verify_password,
)


def normalize_identity(value: str) -> str:
    return value.strip()


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email.strip().lower())
    return db.scalar(stmt)


def get_user_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username.strip())
    return db.scalar(stmt)


def get_user_by_identity(db: Session, identity: str) -> User | None:
    clean = normalize_identity(identity)
    stmt = select(User).where(
        or_(
            User.email == clean.lower(),
            User.username == clean,
            User.username == clean.lower(),
            User.username == clean.capitalize(),
        )
    )
    return db.scalar(stmt)


def create_user(db: Session, username: str, email: str, password: str, role: str = "user") -> User:
    user = User(
        username=username.strip(),
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def upsert_user(db: Session, username: str, email: str, password: str, role: str = "user") -> User:
    existing = get_user_by_email(db, email) or get_user_by_username(db, username)
    if existing:
        existing.username = username.strip()
        existing.email = email.strip().lower()
        existing.password_hash = hash_password(password)
        existing.role = role
        existing.is_active = True
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    return create_user(db, username=username, email=email, password=password, role=role)


def authenticate_user(db: Session, identity: str, password: str) -> User | None:
    user = get_user_by_identity(db, identity)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_session(
    db: Session,
    user: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    raw_token = generate_session_token()
    session = UserSession(
        user_id=user.id,
        session_token_hash=hash_token(raw_token),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session)
    db.commit()
    return raw_token


def revoke_session(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    stmt = select(UserSession).where(UserSession.session_token_hash == hash_token(raw_token))
    session = db.scalar(stmt)
    if session and session.revoked_at is None:
        session.revoked_at = utcnow()
        db.add(session)
        db.commit()


def get_user_from_session_token(db: Session, raw_token: str | None) -> User | None:
    if not raw_token:
        return None
    stmt = (
        select(UserSession)
        .where(UserSession.session_token_hash == hash_token(raw_token))
        .where(UserSession.revoked_at.is_(None))
    )
    session = db.scalar(stmt)
    if not session:
        return None

    expires_at = session.expires_at
    now = utcnow()
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=now.tzinfo)

    if expires_at < now:
        session.revoked_at = now
        db.add(session)
        db.commit()
        return None
    return db.get(User, session.user_id)



def upsert_vip_user(db: Session, username: str, email: str, role: str = "user", is_active: bool = True) -> User:
    existing = get_user_by_email(db, email) or get_user_by_username(db, username)
    if existing:
        existing.username = username.strip()
        existing.email = email.strip().lower()
        existing.role = "admin" if role == "admin" else "user"
        existing.is_active = bool(is_active)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    user = User(
        username=username.strip(),
        email=email.strip().lower(),
        password_hash=hash_password(generate_session_token()),
        role="admin" if role == "admin" else "user",
        is_active=bool(is_active),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
