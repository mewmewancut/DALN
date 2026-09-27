import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import bcrypt
import jwt
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.auth import AuthToken
from app.models.user import User
from app.schemas.auth import RegisterRequest

VERIFY_EMAIL = "VERIFY_EMAIL"
RESET_PASSWORD = "RESET_PASSWORD"
INVALID_TOKEN_DETAIL = "Liên kết không hợp lệ hoặc đã hết hạn"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def register_user(db: Session, request: RegisterRequest) -> tuple[User, str]:
    if request.role not in ("BUYER", "SHOP_OWNER"):
        raise HTTPException(status_code=400, detail="Vai trò đăng ký không hợp lệ")
    normalized_email = normalize_email(request.email)
    if db.scalar(select(User.id).where(func.lower(User.email) == normalized_email)) is not None:
        raise HTTPException(status_code=400, detail="Email đã được sử dụng")

    user = User(
        email=normalized_email,
        password_hash=hash_password(request.password),
        full_name=request.full_name.strip(),
        role=request.role,
    )
    db.add(user)
    try:
        db.flush()
        token = _issue_token(
            db,
            user.id,
            VERIFY_EMAIL,
            get_settings().verify_email_expire_minutes,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email đã được sử dụng") from None
    db.refresh(user)
    return user, token


def verify_email(db: Session, raw_token: str) -> None:
    user_id = _consume_token(db, raw_token, VERIFY_EMAIL)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        db.rollback()
        raise HTTPException(status_code=400, detail=INVALID_TOKEN_DETAIL)

    now = datetime.now(timezone.utc)
    if user.email_verified_at is None:
        user.email_verified_at = now
    _invalidate_tokens(db, user.id, VERIFY_EMAIL, now)
    db.commit()


def issue_verification_token(db: Session, email: str) -> tuple[str, str] | None:
    user = db.scalar(select(User).where(func.lower(User.email) == normalize_email(email)))
    if user is None or not user.is_active or user.email_verified_at is not None:
        return None
    token = _issue_token(
        db,
        user.id,
        VERIFY_EMAIL,
        get_settings().verify_email_expire_minutes,
    )
    db.commit()
    return user.email, token


def issue_password_reset_token(db: Session, email: str) -> tuple[str, str] | None:
    user = db.scalar(select(User).where(func.lower(User.email) == normalize_email(email)))
    if user is None or not user.is_active or user.email_verified_at is None:
        return None
    token = _issue_token(
        db,
        user.id,
        RESET_PASSWORD,
        get_settings().reset_password_expire_minutes,
    )
    db.commit()
    return user.email, token


def reset_password(db: Session, raw_token: str, new_password: str) -> str:
    user_id = _consume_token(db, raw_token, RESET_PASSWORD)
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.email_verified_at is None:
        db.rollback()
        raise HTTPException(status_code=400, detail=INVALID_TOKEN_DETAIL)

    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(new_password)
    user.auth_version += 1
    _invalidate_tokens(db, user.id, RESET_PASSWORD, now)
    db.commit()
    return user.email


def login_user(db: Session, email: str, password: str) -> tuple[str, User]:
    user = db.scalar(select(User).where(func.lower(User.email) == normalize_email(email)))
    if user is None or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Email chưa được xác nhận")

    settings = get_settings()
    shop_id = user.shop.id if user.shop is not None else None
    token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "shop_id": shop_id,
            "auth_version": user.auth_version,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return token, user


def _issue_token(db: Session, user_id: int, purpose: str, expire_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    _invalidate_tokens(db, user_id, purpose, now)
    raw_token = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=_token_hash(raw_token),
            expires_at=now + timedelta(minutes=expire_minutes),
        )
    )
    return raw_token


def _consume_token(db: Session, raw_token: str, purpose: str) -> int:
    now = datetime.now(timezone.utc)
    user_id = db.execute(
        update(AuthToken)
        .where(
            AuthToken.token_hash == _token_hash(raw_token),
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > func.now(),
        )
        .values(used_at=now)
        .returning(AuthToken.user_id)
    ).scalar_one_or_none()
    if user_id is None:
        db.rollback()
        raise HTTPException(status_code=400, detail=INVALID_TOKEN_DETAIL)
    return user_id


def _invalidate_tokens(db: Session, user_id: int, purpose: str, when: datetime) -> None:
    db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
        .values(used_at=when)
    )


def _token_hash(raw_token: str) -> str:
    return sha256(raw_token.encode()).hexdigest()
