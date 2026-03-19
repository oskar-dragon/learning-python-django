import json
import logging

from django.http import Http404, HttpRequest, HttpResponse
from ninja.errors import AuthenticationError, AuthorizationError, HttpError, ValidationError
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController

from blog.api import router as blog_router
from core.exceptions import AppException
from orders.api import router as orders_router
from products.api import router as products_router

logger = logging.getLogger(__name__)

api = NinjaExtraAPI()
api.register_controllers(NinjaJWTDefaultController)  # pyright: ignore[reportUnknownMemberType]


@api.exception_handler(AppException)
def handle_app_exception(request: HttpRequest, exc: AppException) -> HttpResponse:
    return api.create_response(request, exc.error.model_dump(), status=400)


@api.exception_handler(ValidationError)
def handle_validation_error(request: HttpRequest, exc: ValidationError) -> HttpResponse:
    return api.create_response(
        request,
        {"tag": "ValidationError", "detail": "Validation error", "errors": exc.errors},
        status=422,
    )


@api.exception_handler(AuthenticationError)
def handle_authentication_error(request: HttpRequest, exc: AuthenticationError) -> HttpResponse:
    return api.create_response(
        request,
        {"tag": "AuthenticationError", "detail": str(exc)},
        status=401,
    )


@api.exception_handler(AuthorizationError)
def handle_authorization_error(request: HttpRequest, exc: AuthorizationError) -> HttpResponse:
    return api.create_response(
        request,
        {"tag": "AuthorizationError", "detail": str(exc)},
        status=403,
    )


@api.exception_handler(HttpError)
def handle_http_error(request: HttpRequest, exc: HttpError) -> HttpResponse:
    return api.create_response(
        request,
        {"tag": "HttpError", "detail": exc.message, "status_code": exc.status_code},
        status=exc.status_code,
    )


@api.exception_handler(Http404)
def handle_404(request: HttpRequest, exc: Http404) -> HttpResponse:
    return api.create_response(
        request,
        {"tag": "NotFoundError", "detail": "Not found"},
        status=404,
    )


def django_404_handler(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Django-level 404 handler for URL routing misses (outside Ninja's exception system)."""
    return HttpResponse(
        json.dumps({"tag": "NotFoundError", "detail": "Not found"}),
        content_type="application/json",
        status=404,
    )


@api.exception_handler(Exception)
def handle_exception(request: HttpRequest, exc: Exception) -> HttpResponse:
    logger.exception("Unhandled exception: %s", exc)
    return api.create_response(
        request,
        {"tag": "InternalError", "detail": "Internal server error"},
        status=500,
    )


api.add_router("/blog", blog_router)
api.add_router("/orders", orders_router)
api.add_router("/products", products_router)
