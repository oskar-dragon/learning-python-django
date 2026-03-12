from core.exceptions import AppException
from orders.schemas import OrderNotAccessibleError, OrderNotFoundError


class OrderNotFound(AppException):
    def __init__(self, order_id: int) -> None:
        super().__init__(404, OrderNotFoundError(id=order_id, detail="Order not found"))


class OrderNotAccessible(AppException):
    def __init__(self, order_id: int) -> None:
        super().__init__(403, OrderNotAccessibleError(id=order_id, detail="Order not accessible"))
