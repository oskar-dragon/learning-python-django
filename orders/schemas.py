from datetime import datetime
from decimal import Decimal
from typing import Literal

from ninja.filter_schema import FilterSchema
from pydantic import Field, RootModel

from core.schemas import AppError, TaggedSchema
from orders.models import Order


class PendingOrderSchema(TaggedSchema):
    tag: Literal["pending"]
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    created_at: datetime


class ShippedOrderSchema(TaggedSchema):
    tag: Literal["shipped"]
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    tracking_number: str
    shipped_at: datetime
    created_at: datetime


class CancelledOrderSchema(TaggedSchema):
    tag: Literal["cancelled"]
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    cancellation_reason: str
    cancelled_at: datetime
    created_at: datetime


class OrderResult(RootModel[PendingOrderSchema | ShippedOrderSchema | CancelledOrderSchema]):
    pass


class OrderNotFoundError(AppError):
    tag: Literal["order_not_found"]
    id: int


class OrderNotAccessibleError(AppError):
    tag: Literal["order_not_accessible"]
    id: int


class OrderFilters(FilterSchema):
    status: Order.Status | None = None
    q: str | None = Field(None, q=["customer_name__icontains"])  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
    min_total: Decimal | None = Field(None, q="total_price__gte")  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
    max_total: Decimal | None = Field(None, q="total_price__lte")  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
