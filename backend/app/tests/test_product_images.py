from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.models import Category, Inventory, Product, ProductDetailImage, ProductVariant, Shop
from app.schemas.catalog import ProductUpdate
from app.services.catalog_service import update_product
from app.services.product_image_service import MAX_IMAGE_BYTES
from app.tests.test_catalog import client as client
from app.tests.test_catalog import product_payload, user_with_token


@pytest.fixture
def context(db_session, client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "product_image_directory", str(tmp_path))
    _, headers = user_with_token(db_session, "image-owner@example.com", "SHOP_OWNER")
    _, other = user_with_token(db_session, "image-other@example.com", "SHOP_OWNER")
    _, buyer = user_with_token(db_session, "image-buyer@example.com", "BUYER")
    shop = client.post("/shops", json={"name": "Ảnh A"}, headers=headers).json()
    client.post("/shops", json={"name": "Ảnh B"}, headers=other)
    category = Category(name="Ảnh")
    db_session.add(category)
    db_session.commit()
    return headers, other, buyer, shop["id"], category.id, tmp_path


def image_bytes(format="PNG", size=(30, 40)):
    output = BytesIO()
    Image.new("RGB", size, "blue").save(output, format=format)
    return output.getvalue()


def upload(client, headers, content=None, mime="image/png", filename="../../fake.png"):
    return client.post(
        "/shop/product-images",
        headers=headers,
        files={"file": (filename, image_bytes() if content is None else content, mime)},
    )


@pytest.mark.parametrize(
    "format,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")]
)
def test_upload_real_images_and_read_publicly(client, context, format, mime):
    headers, _, _, shop_id, _, directory = context
    response = upload(client, headers, image_bytes(format), mime)
    assert response.status_code == 201
    url = response.json()["image_url"]
    assert url.startswith(f"/media/product-images/{shop_id}/")
    assert "fake" not in url
    public = client.get(url)
    assert public.status_code == 200
    assert public.headers["content-type"] == "image/webp"
    assert public.headers["x-content-type-options"] == "nosniff"
    with Image.open(BytesIO(public.content)) as result:
        assert result.size == (30, 40)
        assert result.format == "WEBP"
    assert len(list(directory.rglob("*.webp"))) == 1


def test_upload_permissions_invalid_files_limits_and_paths(client, context, db_session):
    headers, _, buyer, _, _, directory = context
    assert upload(client, {}).status_code == 401
    assert upload(client, buyer).status_code == 403
    _, no_shop = user_with_token(db_session, "image-no-shop@example.com", "SHOP_OWNER")
    assert upload(client, no_shop).status_code == 403
    for content, mime, status in [
        (b"not an image", "image/png", 415),
        (b"<svg></svg>", "image/svg+xml", 415),
        (b"", "image/png", 415),
        (b"x" * (MAX_IMAGE_BYTES + 1), "image/png", 413),
        (image_bytes(size=(5000, 4001)), "image/png", 413),
    ]:
        assert upload(client, headers, content, mime).status_code == status
    assert list(directory.rglob("*.webp")) == []
    assert client.get("/media/product-images/1/secrets.txt").status_code == 404
    assert client.get("/media/product-images/1/" + "0" * 32 + ".webp").status_code == 404


@pytest.mark.parametrize(
    "main", [None, "", "   ", "javascript:alert(1)", "data:image/png;base64,test"]
)
def test_create_requires_main_image(client, context, db_session, main):
    headers, _, _, _, category_id, _ = context
    payload = product_payload(category_id)
    payload["image_url"] = main
    assert client.post("/products", headers=headers, json=payload).status_code == 422
    payload.pop("image_url")
    assert client.post("/products", headers=headers, json=payload).status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Product)) == 0


def test_create_edit_gallery_limits_ownership_and_visibility(client, context, db_session):
    headers, other, buyer, _, category_id, _ = context
    main = upload(client, headers).json()["image_url"]
    details = [upload(client, headers).json()["image_url"] for _ in range(10)]
    payload = {**product_payload(category_id), "image_url": main, "detail_image_urls": details}
    created = client.post("/products", json=payload, headers=headers)
    assert created.status_code == 201
    product_id = created.json()["id"]
    path = f"/products/{product_id}"
    assert client.get(path).json()["detail_image_urls"] == details
    assert (
        client.get("/shop/products", headers=headers).json()["items"][0]["detail_image_urls"]
        == details
    )
    summary = client.get("/products").json()["items"][0]
    assert summary["image_url"] == main
    assert "detail_image_urls" not in summary
    assert (
        client.post(
            "/products", headers=headers, json={**payload, "detail_image_urls": details + [main]}
        ).status_code
        == 422
    )
    for changes in (
        {"image_url": None},
        {"detail_image_urls": None},
        {"detail_image_urls": [""]},
        {"detail_image_urls": details + [main]},
    ):
        assert client.put(path, headers=headers, json=changes).status_code in {400, 422}
        assert client.get(path).json()["detail_image_urls"] == details
    other_image = upload(client, other).json()["image_url"]
    assert client.put(path, headers=headers, json={"image_url": other_image}).status_code == 403
    assert client.put(path, headers=other, json={"detail_image_urls": []}).status_code == 403
    assert client.put(path, headers=buyer, json={"detail_image_urls": []}).status_code == 403
    assert client.post("/products", headers=other, json=payload).status_code == 403
    missing = main.rsplit("/", 1)[0] + "/" + "0" * 32 + ".webp"
    assert client.put(path, headers=headers, json={"image_url": missing}).status_code == 400
    assert (
        client.put(path, headers=headers, json={"name": "Đổi tên"}).json()["detail_image_urls"]
        == details
    )
    reversed_details = details[::-1]
    assert (
        client.put(path, headers=headers, json={"detail_image_urls": reversed_details}).json()[
            "detail_image_urls"
        ]
        == reversed_details
    )
    assert (
        client.put(
            path, headers=headers, json={"image_url": details[0], "detail_image_urls": []}
        ).json()["detail_image_urls"]
        == []
    )
    assert client.get(path).json()["image_url"] == details[0]
    client.delete(path, headers=headers)
    assert client.get(path).status_code == 404
    assert (
        client.get("/shop/products", headers=headers).json()["items"][0]["image_url"] == details[0]
    )
    assert db_session.get(Product, product_id).detail_image_urls == []


def test_create_and_update_rollback_images_with_product(client, context, db_session, monkeypatch):
    headers, _, _, shop_id, category_id, _ = context
    payload = {
        **product_payload(category_id),
        "detail_image_urls": ["https://example.com/detail.png"],
    }
    payload["variants"][1]["size"] = "M"
    assert client.post("/products", headers=headers, json=payload).status_code == 409
    for model in (Product, ProductVariant, Inventory, ProductDetailImage):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0
    payload["variants"][1]["size"] = "L"
    created = client.post("/products", headers=headers, json=payload).json()
    shop = db_session.get(Shop, shop_id)

    def fail_commit():
        db_session.flush()
        raise RuntimeError("forced write failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError):
        update_product(
            db_session,
            shop,
            created["id"],
            ProductUpdate(image_url="https://example.com/new.png", detail_image_urls=[]),
        )
    db_session.expire_all()
    product = db_session.get(Product, created["id"])
    assert product.image_url == payload["image_url"]
    assert product.detail_image_urls == payload["detail_image_urls"]


def test_database_blocks_more_than_ten_details(client, context, db_session):
    headers, _, _, _, category_id, _ = context
    created = client.post("/products", headers=headers, json=product_payload(category_id)).json()
    db_session.add_all(
        [
            ProductDetailImage(
                product_id=created["id"],
                position=position,
                image_url="https://example.com/image.png",
            )
            for position in range(1, 12)
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_upload_storage_failure_returns_retryable_error(client, context, monkeypatch):
    headers, _, _, _, _, directory = context

    def fail_write(self, data):
        raise OSError("forced storage failure")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    assert upload(client, headers).status_code == 503
    assert list(directory.rglob("*.webp")) == []


def test_upload_storage_cleanup_failure_still_returns_retryable_error(client, context, monkeypatch):
    headers, _, _, _, _, _ = context

    def fail_write(self, data):
        raise OSError("forced storage failure")

    def fail_cleanup(self, missing_ok=False):
        raise PermissionError("forced cleanup failure")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    monkeypatch.setattr(Path, "unlink", fail_cleanup)
    assert upload(client, headers).status_code == 503
