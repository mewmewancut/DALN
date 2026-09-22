from pydantic import BaseModel, ConfigDict, Field


class ShopCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ShopUpdate(ShopCreate):
    pass


class ShopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    description: str | None
    is_active: bool
