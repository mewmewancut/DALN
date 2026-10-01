from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_ids: list[int] = Field(default_factory=list, max_length=100)
    colors: list[str] = Field(default_factory=list, max_length=20)
    min_price: int | None = Field(default=None, ge=0, le=999_999_999_999)
    max_price: int | None = Field(default=None, ge=0, le=999_999_999_999)

    @field_validator("category_ids")
    @classmethod
    def normalize_categories(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("Mã danh mục phải là số nguyên dương")
        return list(dict.fromkeys(values))

    @field_validator("colors")
    @classmethod
    def normalize_colors(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 30 for value in normalized):
            raise ValueError("Màu sắc phải có từ 1 đến 30 ký tự")
        return list(dict.fromkeys(normalized))

    @model_validator(mode="after")
    def validate_price_range(self) -> Self:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("Giá tối thiểu không được lớn hơn giá tối đa")
        return self


class PreferenceResponse(BaseModel):
    category_ids: list[int]
    colors: list[str]
    min_price: int | None
    max_price: int | None


class PreferenceCategoryOption(BaseModel):
    id: int
    name: str


class PreferenceOptionsResponse(BaseModel):
    categories: list[PreferenceCategoryOption]
    colors: list[str]
