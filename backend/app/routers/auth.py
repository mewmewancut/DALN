import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
    EmailRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenRequest,
    UserResponse,
)
from app.services.auth_rate_limiter import (
    AuthRateLimiter,
    RateLimitExceeded,
    get_auth_rate_limiter,
)
from app.services.auth_service import (
    issue_password_reset_token,
    issue_verification_token,
    login_user,
    normalize_email,
    register_user,
    reset_password,
    verify_email,
)
from app.services.email_service import EmailDeliveryError, EmailSender, get_email_sender

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

GENERIC_VERIFY_MESSAGE = "Nếu email hợp lệ và chưa được xác nhận, hệ thống đã gửi một liên kết mới."
GENERIC_RESET_MESSAGE = (
    "Nếu email thuộc tài khoản hợp lệ, hệ thống đã gửi hướng dẫn đặt lại mật khẩu."
)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    sender: Annotated[EmailSender, Depends(get_email_sender)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
) -> User:
    _check_limit(limiter, "register", _client_ip(request), limit=10, window_seconds=3600)
    user, token = register_user(db, payload)
    try:
        sender.send_verification(user.email, token)
    except EmailDeliveryError:
        logger.exception("Không gửi được email xác minh khi đăng ký")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể gửi email. Vui lòng thử gửi lại sau",
        ) from None
    return user


@router.post("/verify-email", response_model=MessageResponse)
def confirm_email(
    payload: TokenRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
) -> MessageResponse:
    _check_limit(limiter, "verify", _client_ip(request), limit=10, window_seconds=3600)
    verify_email(db, payload.token)
    return MessageResponse(message="Email đã được xác nhận. Bạn có thể đăng nhập.")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    payload: EmailRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    sender: Annotated[EmailSender, Depends(get_email_sender)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
) -> MessageResponse:
    _check_email_limit(limiter, "resend", request, payload.email)
    issued = issue_verification_token(db, payload.email)
    if issued is not None:
        recipient, token = issued
        background_tasks.add_task(_send_verification_safely, sender, recipient, token)
    return MessageResponse(message=GENERIC_VERIFY_MESSAGE)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: EmailRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    sender: Annotated[EmailSender, Depends(get_email_sender)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
) -> MessageResponse:
    _check_email_limit(limiter, "forgot", request, payload.email)
    issued = issue_password_reset_token(db, payload.email)
    if issued is not None:
        recipient, token = issued
        background_tasks.add_task(_send_password_reset_safely, sender, recipient, token)
    return MessageResponse(message=GENERIC_RESET_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def change_password(
    payload: ResetPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    sender: Annotated[EmailSender, Depends(get_email_sender)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
) -> MessageResponse:
    _check_limit(limiter, "reset", _client_ip(request), limit=10, window_seconds=3600)
    recipient = reset_password(db, payload.token, payload.new_password)
    background_tasks.add_task(_send_password_changed_safely, sender, recipient)
    return MessageResponse(message="Mật khẩu đã được thay đổi. Hãy đăng nhập lại.")


def _send_verification_safely(sender: EmailSender, recipient: str, token: str) -> None:
    try:
        sender.send_verification(recipient, token)
    except EmailDeliveryError:
        logger.exception("Không gửi được email xác minh được yêu cầu lại")


def _send_password_reset_safely(sender: EmailSender, recipient: str, token: str) -> None:
    try:
        sender.send_password_reset(recipient, token)
    except EmailDeliveryError:
        logger.exception("Không gửi được email đặt lại mật khẩu")


def _send_password_changed_safely(sender: EmailSender, recipient: str) -> None:
    try:
        sender.send_password_changed(recipient)
    except EmailDeliveryError:
        logger.exception("Không gửi được thông báo đổi mật khẩu")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> LoginResponse:
    token, user = login_user(db, payload.email, payload.password)
    return LoginResponse(
        access_token=token,
        role=user.role,
        shop_id=user.shop.id if user.shop is not None else None,
    )


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _check_email_limit(
    limiter: AuthRateLimiter,
    scope: str,
    request: Request,
    email: str,
) -> None:
    identity = f"{_client_ip(request)}:{normalize_email(email)}"
    _check_limit(
        limiter,
        scope,
        identity,
        limit=5,
        window_seconds=3600,
        cooldown_seconds=60,
    )


def _check_limit(
    limiter: AuthRateLimiter,
    scope: str,
    identity: str,
    *,
    limit: int,
    window_seconds: int,
    cooldown_seconds: int = 0,
) -> None:
    try:
        limiter.check(
            scope,
            identity,
            limit=limit,
            window_seconds=window_seconds,
            cooldown_seconds=cooldown_seconds,
        )
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn đã yêu cầu quá nhiều lần. Vui lòng thử lại sau",
        ) from None
