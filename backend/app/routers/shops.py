from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.deps import get_current_shop, get_db, require_role
from app.models.shop import Shop
from app.models.user import User
from app.schemas.shop import PublicShopResponse, ShopCreate, ShopResponse, ShopUpdate
from app.services.shop_service import create_shop, get_public_shop, update_shop

router = APIRouter(prefix="/shops", tags=["shops"])


@router.post("", response_model=ShopResponse, status_code=status.HTTP_201_CREATED)
def create(
    request: ShopCreate,
    owner: Annotated[User, Depends(require_role("SHOP_OWNER"))],
    db: Annotated[Session, Depends(get_db)],
) -> Shop:
    return create_shop(db, owner, request)


@router.put("/me", response_model=ShopResponse)
def update(
    request: ShopUpdate,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> Shop:
    return update_shop(db, shop, request)


@router.get("/{shop_id}", response_model=PublicShopResponse)
def public_shop(
    shop_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
) -> Shop:
    return get_public_shop(db, shop_id)
