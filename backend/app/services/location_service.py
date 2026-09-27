import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "vn_admin_units_2025.json"


@lru_cache(maxsize=1)
def _dataset() -> dict[str, Any]:
    with DATA_FILE.open(encoding="utf-8") as handle:
        return json.load(handle)


def list_provinces() -> list[dict[str, str]]:
    return [{"code": item["code"], "name": item["name"]} for item in _dataset()["provinces"]]


def _province(province_code: str) -> dict[str, Any]:
    for province in _dataset()["provinces"]:
        if province["code"] == province_code:
            return province
    raise HTTPException(status_code=400, detail="Mã Tỉnh/Thành phố không hợp lệ")


def list_communes(province_code: str) -> list[dict[str, str]]:
    province = _province(province_code)
    return list(province["communes"])


def resolve_location(province_code: str, commune_code: str) -> tuple[str, str]:
    province = _province(province_code)
    for commune in province["communes"]:
        if commune["code"] == commune_code:
            return province["name"], commune["name"]
    raise HTTPException(
        status_code=400,
        detail="Mã Xã/Phường/Đặc khu không thuộc Tỉnh/Thành phố đã chọn",
    )
