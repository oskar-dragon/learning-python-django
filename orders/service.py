from orders.exceptions import OrderNotAccessible, OrderNotFound
from orders.models import Order
from orders.schemas import (
    CancelledOrder,
    OrderFilters,
    PendingOrder,
    ShippedOrder,
)

OrderQueryResult = PendingOrder | ShippedOrder | CancelledOrder


def _to_schema(order: Order) -> OrderQueryResult:
    match order.status:
        case Order.Status.PENDING:
            return PendingOrder(
                id=order.pk,
                customer_name=order.customer_name,
                items_count=order.items_count,
                total_price=order.total_price,
                created_at=order.created_at,
            )
        case Order.Status.SHIPPED:
            return ShippedOrder(
                id=order.pk,
                customer_name=order.customer_name,
                items_count=order.items_count,
                total_price=order.total_price,
                tracking_number=order.tracking_number or "",
                shipped_at=order.shipped_at,  # pyright: ignore[reportArgumentType]
                created_at=order.created_at,
            )
        case Order.Status.CANCELLED:
            return CancelledOrder(
                id=order.pk,
                customer_name=order.customer_name,
                items_count=order.items_count,
                total_price=order.total_price,
                cancellation_reason=order.cancellation_reason or "",
                cancelled_at=order.cancelled_at,  # pyright: ignore[reportArgumentType]
                created_at=order.created_at,
            )
        case Order.Status.DRAFT | _:
            # DRAFT is excluded before _to_schema is called; this branch should never be reached
            raise ValueError(f"Unexpected order status in _to_schema: {order.status}")


def list_orders(filters: OrderFilters) -> list[OrderQueryResult]:
    # Draft orders are always excluded — they are an internal status not exposed to consumers.
    # list_orders never raises OrderNotFound/OrderNotAccessible: filters simply narrow results.
    qs = Order.objects.exclude(status=Order.Status.DRAFT)
    qs = filters.filter(qs)
    return [_to_schema(order) for order in qs]


def get_order(order_id: int) -> OrderQueryResult:
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        raise OrderNotFound(order_id)

    if order.status == Order.Status.DRAFT:
        raise OrderNotAccessible(order_id)

    return _to_schema(order)
