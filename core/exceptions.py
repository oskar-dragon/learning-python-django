from core.schemas import AppError


class AppException(Exception):
    def __init__(self, error: AppError) -> None:
        super().__init__()
        self.error = error
