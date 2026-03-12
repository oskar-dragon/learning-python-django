from ninja import Schema


class AppError(Schema):
    type: str
    detail: str
