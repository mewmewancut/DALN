from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.models.user import User
from app.schemas.preference import PreferenceOptionsResponse, PreferenceResponse, PreferenceUpdate
from app.services import preference_service

router = APIRouter(prefix="/users/me/preferences", tags=["preferences"])


@router.get("/options", response_model=PreferenceOptionsResponse)
def preference_options(
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> PreferenceOptionsResponse:
    return preference_service.list_options(db, user.id)


@router.get("", response_model=PreferenceResponse)
def preferences(
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> PreferenceResponse:
    return preference_service.get_preferences(db, user.id)


@router.put("", response_model=PreferenceResponse)
def update_preferences(
    request: PreferenceUpdate,
    user: Annotated[User, Depends(require_role("BUYER"))],
    db: Annotated[Session, Depends(get_db)],
) -> PreferenceResponse:
    return preference_service.update_preferences(db, user.id, request)
