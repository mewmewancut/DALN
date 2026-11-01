from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_shop, get_db, require_role
from app.models.shop import Shop
from app.models.user import User
from app.schemas.review import (
    ReviewCreate,
    ReviewPage,
    ReviewResponse,
    ShopReviewPage,
    ShopReviewReply,
    ShopReviewResponse,
)
from app.services import review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])
product_router = APIRouter(prefix="/products", tags=["reviews"])
Buyer = Annotated[User, Depends(require_role("BUYER"))]
Database = Annotated[Session, Depends(get_db)]
CurrentShop = Annotated[Shop, Depends(get_current_shop)]


@router.post("", response_model=ReviewResponse)
def create_review(request: ReviewCreate, buyer: Buyer, db: Database) -> ReviewResponse:
    return review_service.create_review(db, buyer, request)


@product_router.get("/{product_id}/reviews", response_model=ReviewPage)
def product_reviews(
    product_id: int,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReviewPage:
    return review_service.list_product_reviews(db, product_id, page=page, page_size=page_size)


@router.get("/shop", response_model=ShopReviewPage)
def shop_reviews(
    shop: CurrentShop,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ShopReviewPage:
    return review_service.list_shop_reviews(db, shop, page=page, page_size=page_size)


@router.post("/shop/{review_id}/reply", response_model=ShopReviewResponse)
def reply_to_review(
    review_id: int,
    request: ShopReviewReply,
    shop: CurrentShop,
    db: Database,
) -> ShopReviewResponse:
    return review_service.reply_to_shop_review(db, shop, review_id, request)


@router.patch("/shop/{review_id}/read", response_model=ShopReviewResponse)
def mark_review_read(
    review_id: int,
    shop: CurrentShop,
    db: Database,
) -> ShopReviewResponse:
    return review_service.mark_shop_review_read(db, shop, review_id)
