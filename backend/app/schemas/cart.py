from pydantic import BaseModel, ConfigDict, Field


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
    product_id: int
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
