from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.models.user import User
from app.schemas.catalog import ProductSummary
from app.services.recommendation_service import list_recommendations

router = APIRouter(prefix="/users/me/recommendations", tags=["recommendations"])


@router.get("", response_model=list[ProductSummary])
def recommendations(
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> list[ProductSummary]:
    return list_recommendations(db, user.id, limit=limit)
