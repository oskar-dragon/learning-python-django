from django.http import HttpRequest
from ninja import Query, Router
from ninja_jwt.authentication import JWTAuth

from core.decorators import raises
from orders import service
from orders.exceptions import OrderNotAccessibleError, OrderNotFoundError
from orders.schemas import OrderFilters, OrderResponse

router = Router(auth=JWTAuth())


@router.get("/", response=list[OrderResponse])
def list_orders(request: HttpRequest, filters: Query[OrderFilters]) -> list[OrderResponse]:
    return service.list_orders(filters)  # pyright: ignore[reportReturnType]


@router.get("/{order_id}/")
@raises(OrderNotFoundError, OrderNotAccessibleError)
def get_order(request: HttpRequest, order_id: int) -> OrderResponse:
    return service.get_order(order_id)  # pyright: ignore[reportReturnType]
