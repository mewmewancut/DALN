from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas.profile import LocationResponse
from app.services import location_service

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/provinces", response_model=list[LocationResponse])
def provinces() -> list[dict[str, str]]:
    return location_service.list_provinces()


@router.get("/communes", response_model=list[LocationResponse])
def communes(
    province_code: Annotated[str, Query(pattern=r"^\d{2}$")],
) -> list[dict[str, str]]:
    return location_service.list_communes(province_code)
