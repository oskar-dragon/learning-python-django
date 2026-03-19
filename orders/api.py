from django.http import HttpRequest
from ninja import Query, Router
from ninja_jwt.authentication import JWTAuth

from orders import service
from orders.schemas import OrderErrors, OrderFilters, OrderResponse

router = Router(auth=JWTAuth())


@router.get("/", response=list[OrderResponse])
def list_orders(request: HttpRequest, filters: Query[OrderFilters]) -> list[OrderResponse]:
    return service.list_orders(filters)  # pyright: ignore[reportReturnType]


@router.get(
    "/{order_id}/",
    response={200: OrderResponse, 400: OrderErrors},
)
def get_order(request: HttpRequest, order_id: int) -> OrderResponse:
    # Errors are raised as AppException — caught by the global handler in project/api.py
    return service.get_order(order_id)  # pyright: ignore[reportReturnType]
