from decimal import Decimal
from typing import Literal

from pydantic import Field

from core.schemas import AppError, TaggedSchema, tagged_union


class AvailableProductSchema(TaggedSchema):
    """Available product — has stock_count. tag maps from ORM's status field."""

    tag: Literal["available"] = Field(validation_alias="status", default="available")
    id: int
    name: str
    description: str
    price: Decimal
    stock_count: int


class OutOfStockProductSchema(TaggedSchema):
    """Out-of-stock product — no stock_count. tag maps from ORM's status field."""

    tag: Literal["out_of_stock"] = Field(validation_alias="status", default="out_of_stock")
    id: int
    name: str
    description: str
    price: Decimal


ProductResult = tagged_union(AvailableProductSchema, OutOfStockProductSchema)


class ProductNotFoundError(AppError):
    tag: Literal["product_not_found"] = "product_not_found"
    id: int


class ProductHiddenError(AppError):
    tag: Literal["product_hidden"] = "product_hidden"
    id: int
