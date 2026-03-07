from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.session import UserSession
from app.models.user import User
from app.utils.security import generate_session_token, hash_password, hash_token, utcnow, verify_password


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email.lower().strip())
    return db.scalar(stmt)


def create_user(db: Session, email: str, password: str, role: str = "user") -> User:
    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_session(db: Session, user: User, ip_address: str | None = None, user_agent: str | None = None) -> str:
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
    if session.expires_at < utcnow():
        session.revoked_at = utcnow()
        db.add(session)
        db.commit()
        return None
    return db.get(User, session.user_id)


def ensure_admin_exists(db: Session, email: str | None, password: str | None) -> None:
    if not email or not password:
        return
    existing = get_user_by_email(db, email)
    if existing:
        if existing.role != "admin":
            existing.role = "admin"
            db.add(existing)
            db.commit()
        return
    create_user(db, email=email, password=password, role="admin")
