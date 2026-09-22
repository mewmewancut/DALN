from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.models.user import User
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartResponse
from app.services import cart_service

router = APIRouter(prefix="/cart", tags=["cart"])
Buyer = Annotated[User, Depends(require_role("BUYER"))]
Database = Annotated[Session, Depends(get_db)]


@router.get("", response_model=CartResponse)
def get_cart(buyer: Buyer, db: Database):
    return cart_service.get_cart(db, buyer.id)


@router.post("/items", response_model=CartResponse)
def add_item(request: CartItemAdd, buyer: Buyer, db: Database):
    try:
        return cart_service.add_item(db, buyer.id, request.variant_id, request.quantity)
    except cart_service.DifferentShopError as error:
        return JSONResponse(
            status_code=409, content={"detail": error.detail, "current_shop": error.current_shop}
        )


@router.put("/items/{item_id}", response_model=CartResponse)
def update_item(item_id: int, request: CartItemUpdate, buyer: Buyer, db: Database):
    return cart_service.update_item(db, buyer.id, item_id, request.quantity)


@router.delete("/items/{item_id}", response_model=CartResponse)
def remove_item(item_id: int, buyer: Buyer, db: Database):
    return cart_service.remove_item(db, buyer.id, item_id)


@router.delete("", response_model=CartResponse)
def clear_cart(buyer: Buyer, db: Database):
    return cart_service.clear_cart(db, buyer.id)
