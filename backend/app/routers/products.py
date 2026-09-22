from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.deps import get_current_shop, get_db
from app.models.shop import Shop
from app.schemas.catalog import (
    CategoryResponse,
    ProductCreate,
    ProductDetail,
    ProductPage,
    ProductUpdate,
    VariantCreate,
    VariantResponse,
    VariantUpdate,
)
from app.services.catalog_service import (
    add_variant,
    create_product,
    get_product_detail,
    list_categories,
    list_products,
    remove_product,
    update_product,
    update_variant,
)


category_router = APIRouter(prefix="/categories", tags=["catalog"])
product_router = APIRouter(prefix="/products", tags=["catalog"])
variant_router = APIRouter(prefix="/variants", tags=["catalog"])


@category_router.get("", response_model=list[CategoryResponse])
def categories(db: Annotated[Session, Depends(get_db)]):
    return list_categories(db)


@product_router.get("", response_model=ProductPage)
def products(
    db: Annotated[Session, Depends(get_db)],
    keyword: str | None = None,
    category_id: int | None = None,
    shop_id: int | None = None,
    min_price: Annotated[int | None, Query(ge=0)] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    sort: Literal["newest", "price_asc", "price_desc"] = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductPage:
    return list_products(
        db,
        keyword=keyword,
        category_id=category_id,
        shop_id=shop_id,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@product_router.get("/{product_id}", response_model=ProductDetail)
def product_detail(
    product_id: int, db: Annotated[Session, Depends(get_db)]
) -> ProductDetail:
    return get_product_detail(db, product_id)


@product_router.post("", response_model=ProductDetail, status_code=status.HTTP_201_CREATED)
def create(
    request: ProductCreate,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> ProductDetail:
    return create_product(db, shop, request)


@product_router.put("/{product_id}", response_model=ProductDetail)
def update(
    product_id: int,
    request: ProductUpdate,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> ProductDetail:
    return update_product(db, shop, product_id, request)


@product_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(
    product_id: int,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    remove_product(db, shop, product_id)


@product_router.post(
    "/{product_id}/variants",
    response_model=VariantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_variant(
    product_id: int,
    request: VariantCreate,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> VariantResponse:
    return add_variant(db, shop, product_id, request)


@variant_router.put("/{variant_id}", response_model=VariantResponse)
def edit_variant(
    variant_id: int,
    request: VariantUpdate,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> VariantResponse:
    return update_variant(db, shop, variant_id, request)
