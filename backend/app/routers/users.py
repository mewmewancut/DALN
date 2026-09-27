from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require_role
from app.models.address import UserAddress
from app.models.user import User
from app.schemas.profile import (
    AddressCreate,
    AddressResponse,
    AddressUpdate,
    DeleteAddressResponse,
    ProfileResponse,
    ProfileUpdate,
)
from app.services import profile_service

router = APIRouter(prefix="/users/me", tags=["users"])


@router.get("/profile", response_model=ProfileResponse)
def profile(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.patch("/profile", response_model=ProfileResponse)
def update_profile(
    request: ProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    return profile_service.update_profile(db, user, request)


@router.get("/addresses", response_model=list[AddressResponse])
def addresses(
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserAddress]:
    return profile_service.list_addresses(db, user.id)


@router.post(
    "/addresses",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_address(
    request: AddressCreate,
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserAddress:
    return profile_service.create_address(db, user.id, request)


@router.patch("/addresses/{address_id}", response_model=AddressResponse)
def update_address(
    address_id: int,
    request: AddressUpdate,
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserAddress:
    return profile_service.update_address(db, user.id, address_id, request)


@router.put("/addresses/{address_id}/default", response_model=AddressResponse)
def set_default_address(
    address_id: int,
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserAddress:
    return profile_service.set_default_address(db, user.id, address_id)


@router.delete("/addresses/{address_id}", response_model=DeleteAddressResponse)
def delete_address(
    address_id: int,
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> DeleteAddressResponse:
    profile_service.delete_address(db, user.id, address_id)
    return DeleteAddressResponse(message="Đã xóa địa chỉ")
