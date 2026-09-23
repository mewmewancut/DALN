from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User
from app.schemas.auth import RegisterRequest


def register_user(db: Session, request: RegisterRequest) -> User:
    if request.role not in ("BUYER", "SHOP_OWNER"):
        raise HTTPException(status_code=400, detail="Vai trò đăng ký không hợp lệ")
    normalized_email = request.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == normalized_email)) is not None:
        raise HTTPException(status_code=400, detail="Email đã được sử dụng")

    user = User(
        email=normalized_email,
        password_hash=bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode(),
        full_name=request.full_name,
        role=request.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email đã được sử dụng") from None
    db.refresh(user)
    return user


def login_user(db: Session, email: str, password: str) -> tuple[str, User]:
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")

    settings = get_settings()
    shop_id = user.shop.id if user.shop is not None else None
    token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "shop_id": shop_id,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return token, user
