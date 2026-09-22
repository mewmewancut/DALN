from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.shop import Shop
from app.models.user import User
from app.schemas.shop import ShopCreate, ShopUpdate


def create_shop(db: Session, owner: User, request: ShopCreate) -> Shop:
    if owner.shop is not None:
        raise HTTPException(status_code=400, detail="Tài khoản đã có shop")
    shop = Shop(owner_id=owner.id, **request.model_dump())
    db.add(shop)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Tài khoản đã có shop") from None
    db.refresh(shop)
    return shop


def update_shop(db: Session, shop: Shop, request: ShopUpdate) -> Shop:
    for field, value in request.model_dump().items():
        setattr(shop, field, value)
    db.commit()
    db.refresh(shop)
    return shop
