from core.exceptions import AppException


class OrderNotFoundError(AppException):
    id: int
    detail: str = "Order not found"


class OrderNotAccessibleError(AppException):
    id: int
    detail: str = "Order not accessible"
