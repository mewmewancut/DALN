from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.deps import get_current_shop
from app.models.shop import Shop
from app.services.product_image_service import image_path, upload_product_image

router = APIRouter(tags=["product images"])


@router.post("/shop/product-images", status_code=status.HTTP_201_CREATED)
def upload_image(
    file: UploadFile,
    shop: Annotated[Shop, Depends(get_current_shop)],
) -> dict[str, str]:
    return upload_product_image(shop.id, file)


@router.get("/media/product-images/{shop_id}/{filename}")
def read_image(shop_id: int, filename: str) -> FileResponse:
    path = image_path(shop_id, filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Ảnh không tồn tại")
    return FileResponse(
        path,
        media_type="image/webp",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )
