from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.address import UserAddress
from app.models.user import User
from app.schemas.profile import AddressCreate, AddressUpdate, ProfileUpdate
from app.services.location_service import resolve_location

MAX_ADDRESSES = 10


def update_profile(db: Session, user: User, request: ProfileUpdate) -> User:
    changes = request.model_dump(exclude_unset=True)
    if changes.get("full_name", "not-set") is None:
        raise HTTPException(status_code=400, detail="Họ tên không được để trống")
    if "avatar_url" in changes and changes["avatar_url"] is not None:
        changes["avatar_url"] = str(changes["avatar_url"])
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def list_addresses(db: Session, user_id: int) -> list[UserAddress]:
    return list(
        db.scalars(
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .order_by(UserAddress.is_default.desc(), UserAddress.created_at, UserAddress.id)
        )
    )


def _lock_user(db: Session, user_id: int) -> None:
    db.execute(select(User.id).where(User.id == user_id).with_for_update()).scalar_one()


def _owned_address(db: Session, user_id: int, address_id: int) -> UserAddress:
    address = db.scalar(
        select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == user_id,
        )
    )
    if address is None:
        raise HTTPException(status_code=404, detail="Địa chỉ không tồn tại")
    return address


def _clear_default(db: Session, user_id: int) -> None:
    db.execute(
        update(UserAddress)
        .where(UserAddress.user_id == user_id, UserAddress.is_default.is_(True))
        .values(is_default=False)
    )


def create_address(db: Session, user_id: int, request: AddressCreate) -> UserAddress:
    _lock_user(db, user_id)
    count = db.scalar(
        select(func.count()).select_from(UserAddress).where(UserAddress.user_id == user_id)
    )
    if count is not None and count >= MAX_ADDRESSES:
        raise HTTPException(status_code=400, detail="Mỗi tài khoản chỉ được lưu tối đa 10 địa chỉ")
    province_name, commune_name = resolve_location(request.province_code, request.commune_code)
    make_default = count == 0 or request.is_default
    if make_default:
        _clear_default(db, user_id)
    values = request.model_dump(exclude={"is_default"})
    address = UserAddress(
        user_id=user_id,
        **values,
        province_name=province_name,
        commune_name=commune_name,
        is_default=make_default,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


def update_address(
    db: Session, user_id: int, address_id: int, request: AddressUpdate
) -> UserAddress:
    _lock_user(db, user_id)
    address = _owned_address(db, user_id, address_id)
    changes = request.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=400, detail="Thông tin địa chỉ không được để trống")
    province_code = changes.get("province_code", address.province_code)
    commune_code = changes.get("commune_code", address.commune_code)
    province_name, commune_name = resolve_location(province_code, commune_code)
    for field, value in changes.items():
        setattr(address, field, value)
    address.province_name = province_name
    address.commune_name = commune_name
    db.commit()
    db.refresh(address)
    return address


def set_default_address(db: Session, user_id: int, address_id: int) -> UserAddress:
    _lock_user(db, user_id)
    address = _owned_address(db, user_id, address_id)
    if not address.is_default:
        _clear_default(db, user_id)
        address.is_default = True
        db.commit()
        db.refresh(address)
    return address


def delete_address(db: Session, user_id: int, address_id: int) -> None:
    _lock_user(db, user_id)
    address = _owned_address(db, user_id, address_id)
    was_default = address.is_default
    db.delete(address)
    db.flush()
    if was_default:
        replacement = db.scalar(
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .order_by(UserAddress.created_at, UserAddress.id)
            .limit(1)
        )
        if replacement is not None:
            replacement.is_default = True
    db.commit()
