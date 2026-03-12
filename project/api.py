from django.http import HttpRequest, HttpResponse
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController

from blog.api import router as blog_router
from core.exceptions import AppException
from orders.api import router as orders_router
from products.api import router as products_router

api = NinjaExtraAPI()
api.register_controllers(NinjaJWTDefaultController)  # pyright: ignore[reportUnknownMemberType]


@api.exception_handler(AppException)
def handle_app_exception(request: HttpRequest, exc: AppException) -> HttpResponse:
    return api.create_response(request, exc.error.model_dump(), status=exc.status_code)


api.add_router("/blog", blog_router)
api.add_router("/orders", orders_router)
api.add_router("/products", products_router)
