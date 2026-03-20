from datetime import datetime
from decimal import Decimal

from ninja.filter_schema import FilterSchema
from pydantic import Field, RootModel

from core.schemas import TaggedSchema
from orders.models import Order


class PendingOrder(TaggedSchema):
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    created_at: datetime


class ShippedOrder(TaggedSchema):
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    tracking_number: str
    shipped_at: datetime
    created_at: datetime


class CancelledOrder(TaggedSchema):
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    cancellation_reason: str
    cancelled_at: datetime
    created_at: datetime


class OrderResponse(RootModel[PendingOrder | ShippedOrder | CancelledOrder]):
    pass


class OrderFilters(FilterSchema):
    status: Order.Status | None = None
    q: str | None = Field(None, q=["customer_name__icontains"])  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
    min_total: Decimal | None = Field(None, q="total_price__gte")  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
    max_total: Decimal | None = Field(None, q="total_price__lte")  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
