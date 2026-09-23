from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.models.user import User
from app.schemas.orders import CheckoutRequest, OrderResponse
from app.services import checkout_service

router = APIRouter(prefix="/orders", tags=["orders"])
Buyer = Annotated[User, Depends(require_role("BUYER"))]
Database = Annotated[Session, Depends(get_db)]


@router.post("/checkout", response_model=OrderResponse)
def checkout(request: CheckoutRequest, buyer: Buyer, db: Database):
    return checkout_service.checkout(db, buyer, request)
