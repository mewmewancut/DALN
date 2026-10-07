import re
import warnings
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.product_image import ProductDetailImage

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
IMAGE_NAME = re.compile(r"[0-9a-f]{32}\.webp")


def replace_detail_images(db: Session, product_id: int, urls: list[str]) -> None:
    db.execute(delete(ProductDetailImage).where(ProductDetailImage.product_id == product_id))
    db.add_all(
        [
            ProductDetailImage(product_id=product_id, position=position, image_url=url)
            for position, url in enumerate(urls, start=1)
        ]
    )


def image_path(shop_id: int, filename: str) -> Path:
    if shop_id <= 0 or not IMAGE_NAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="Ảnh không tồn tại")
    return Path(get_settings().product_image_directory) / str(shop_id) / filename


def validate_owned_images(shop_id: int, urls: list[str]) -> None:
    for url in urls:
        if not url.startswith("/media/product-images/"):
            continue  # Preserve the existing external URL contract.
        parts = url.split("/")
        if len(parts) != 5 or parts[3] != str(shop_id):
            raise HTTPException(status_code=403, detail="Ảnh không thuộc shop của bạn")
        if not image_path(shop_id, parts[4]).is_file():
            raise HTTPException(status_code=400, detail="Ảnh đã tải lên không tồn tại")


def upload_product_image(shop_id: int, file: UploadFile) -> dict[str, str]:
    try:
        content = file.file.read(MAX_IMAGE_BYTES + 1)
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Mỗi ảnh tối đa 5 MB")
        if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=415, detail="Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content), formats=["JPEG", "PNG", "WEBP"]) as image:
                    if image.width * image.height > MAX_IMAGE_PIXELS:
                        raise HTTPException(status_code=413, detail="Ảnh tối đa 20 triệu điểm ảnh")
                    image.load()
                    # Encode decoded pixels only: no original filename or metadata is published.
                    pixels = ImageOps.exif_transpose(image).convert("RGBA")
                    encoded = BytesIO()
                    pixels.save(encoded, format="WEBP", quality=90)
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(status_code=415, detail="File không phải ảnh hợp lệ") from None
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(status_code=413, detail="Kích thước ảnh quá lớn") from None
        filename = f"{uuid4().hex}.webp"
        path = image_path(shop_id, filename)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encoded.getvalue())
        except OSError:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass  # Preserve the retryable response even when storage is inaccessible.
            raise HTTPException(status_code=503, detail="Không lưu được ảnh, hãy thử lại") from None
        return {"image_url": f"/media/product-images/{shop_id}/{filename}"}
    finally:
        file.file.close()
