from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.models.user import User
from app.schemas.wishlist import WishlistItemResponse
from app.services import wishlist_service

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=list[WishlistItemResponse])
def wishlist(
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> list[WishlistItemResponse]:
    return wishlist_service.list_items(db, user.id)


@router.put("/items/{product_id}", response_model=WishlistItemResponse)
def add_wishlist_item(
    product_id: int,
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> WishlistItemResponse:
    return wishlist_service.add_item(db, user.id, product_id)


@router.delete("/items/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_wishlist_item(
    product_id: int,
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    wishlist_service.remove_item(db, user.id, product_id)
