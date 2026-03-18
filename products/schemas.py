from typing import Literal

from ninja import ModelSchema
from pydantic import ConfigDict, Field, RootModel

from core.schemas import AppError
from products.models import Product


class AvailableProductSchema(ModelSchema):
    """Available product — has stock_count. tag maps from ORM's status field."""

    model_config = ConfigDict(populate_by_name=True)
    tag: Literal["available"] = Field(validation_alias="status")

    class Meta:
        model = Product
        exclude = ["status", "created", "updated"]


class OutOfStockProductSchema(ModelSchema):
    """Out-of-stock product — no stock_count. tag maps from ORM's status field."""

    model_config = ConfigDict(populate_by_name=True)
    tag: Literal["out_of_stock"] = Field(validation_alias="status")

    class Meta:
        model = Product
        exclude = ["status", "stock_count", "created", "updated"]


class ProductResponse(RootModel[AvailableProductSchema | OutOfStockProductSchema]):
    """Named discriminated union for product success responses."""

    pass


class ProductNotFoundError(AppError):
    id: int


class ProductHiddenError(AppError):
    id: int
