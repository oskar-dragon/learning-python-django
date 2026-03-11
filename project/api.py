from django.http import HttpRequest
from ninja import NinjaAPI

api = NinjaAPI()


@api.get("/health")
def health(request: HttpRequest) -> dict[str, str]:  # pyright: ignore[reportUnusedParameter]
    return {"status": "ok"}
