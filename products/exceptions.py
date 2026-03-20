from core.exceptions import AppException


class ProductNotFoundError(AppException):
    id: int
    detail: str = "Product not found"


class ProductHiddenError(AppException):
    id: int
    detail: str = "Product is not available"
