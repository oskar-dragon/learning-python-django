from django.http import HttpRequest
from ninja import Query, Router
from ninja_jwt.authentication import JWTAuth

from core.decorators import raises
from orders import service
from orders.exceptions import OrderNotAccessibleError, OrderNotFoundError
from orders.schemas import OrderFilters, OrderResponse

router = Router(auth=JWTAuth())


@router.get("/", response=list[OrderResponse])
def list_orders(request: HttpRequest, filters: Query[OrderFilters]):
    return service.list_orders(filters)


@router.get("/{order_id}/", response=OrderResponse)
@raises(OrderNotFoundError, OrderNotAccessibleError)
def get_order(
    request: HttpRequest,
    order_id: int,
):
    return service.get_order(order_id)
