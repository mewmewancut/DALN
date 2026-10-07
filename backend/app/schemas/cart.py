from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CartItemAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: int = Field(gt=0, strict=True)
    quantity: int = Field(gt=0, le=2_147_483_647, strict=True)


class CartItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: int = Field(gt=0, le=2_147_483_647, strict=True)


class CartItemResponse(BaseModel):
    id: int
    variant_id: int
    product_id: int | None
    shop_id: int | None
    shop_name: str
    is_available: bool
    product_name: str
    image_url: str | None
    size: str
    color: str
    quantity: int
    unit_price: int
    stock_quantity: int


class CartResponse(BaseModel):
    shop_id: int | None
    shop_name: str | None
    items: list[CartItemResponse]
    total_amount: int


class CartPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CartItemAdd] = Field(max_length=200)

    @model_validator(mode="after")
    def unique_variants(self):
        if len({item.variant_id for item in self.items}) != len(self.items):
            raise ValueError("Mỗi biến thể chỉ được xuất hiện một lần")
        return self


class CartMergeRequest(CartPreviewRequest):
    merge_id: UUID
