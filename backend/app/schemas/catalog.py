from pydantic import BaseModel, ConfigDict, Field


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class VariantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    size: str = Field(min_length=1, max_length=10)
    color: str = Field(min_length=1, max_length=30)
    price: int = Field(ge=0, le=999_999_999_999)
    initial_quantity: int = Field(ge=0, le=2_147_483_647)


class VariantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price: int | None = Field(default=None, ge=0, le=999_999_999_999)
    is_active: bool | None = None


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    image_url: str | None = None
    base_price: int = Field(ge=0, le=999_999_999_999)
    variants: list[VariantCreate] = Field(min_length=1)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    image_url: str | None = None
    base_price: int | None = Field(default=None, ge=0, le=999_999_999_999)
    is_active: bool | None = None


class VariantResponse(BaseModel):
    id: int
    size: str
    color: str
    price: int
    sku: str
    is_active: bool
    quantity: int


class ProductSummary(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    category_id: int
    name: str
    image_url: str | None
    base_price: int
    price_from: int | None
    rating_average: float | None


class ProductDetail(ProductSummary):
    description: str | None
    is_active: bool
    variants: list[VariantResponse]


class ProductPage(BaseModel):
    items: list[ProductSummary]
    total: int
    page: int
    page_size: int
