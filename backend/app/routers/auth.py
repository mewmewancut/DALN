from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from app.services.auth_service import login_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> User:
    return register_user(db, request)


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> LoginResponse:
    token, user = login_user(db, request.email, request.password)
    return LoginResponse(
        access_token=token,
        role=user.role,
        shop_id=user.shop.id if user.shop is not None else None,
    )


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
