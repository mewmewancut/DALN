from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewPage, ReviewResponse
from app.services import review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])
product_router = APIRouter(prefix="/products", tags=["reviews"])
Buyer = Annotated[User, Depends(require_role("BUYER"))]
Database = Annotated[Session, Depends(get_db)]


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
