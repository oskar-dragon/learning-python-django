from core.exceptions import AppException


class PostNotFoundError(AppException):
    id: int
    detail: str = "Post not found"
