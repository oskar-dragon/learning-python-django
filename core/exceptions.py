from core.schemas import AppError


class AppException(Exception):
    def __init__(self, status_code: int, error: AppError) -> None:
        super().__init__()
        self.status_code = status_code
        self.error = error
