import json
import logging
from typing import override

from django.http import Http404, HttpRequest, HttpResponse
from ninja.errors import AuthenticationError, AuthorizationError, HttpError, ValidationError
from ninja.openapi.schema import OpenAPISchema
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController

from blog.api import router as blog_router
from core.exceptions import AppException
from orders.api import router as orders_router
from products.api import router as products_router

logger = logging.getLogger(__name__)

# Framework error schemas — defined as JSON schema dicts (not Pydantic models)
# because they are only needed for OpenAPI generation, not serialization.
_VALIDATION_ERROR_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "tag": {"type": "string", "const": "ValidationError"},
        "detail": {"type": "string"},
        "errors": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["tag", "detail", "errors"],
    "title": "ValidationError",
}

_AUTHENTICATION_ERROR_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "tag": {"type": "string", "const": "AuthenticationError"},
        "detail": {"type": "string"},
    },
    "required": ["tag", "detail"],
    "title": "AuthenticationError",
}

_AUTHORIZATION_ERROR_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "tag": {"type": "string", "const": "AuthorizationError"},
        "detail": {"type": "string"},
    },
    "required": ["tag", "detail"],
    "title": "AuthorizationError",
}

_INTERNAL_ERROR_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "tag": {"type": "string", "const": "InternalError"},
        "detail": {"type": "string"},
    },
    "required": ["tag", "detail"],
    "title": "InternalError",
}


class TaggedErrorAPI(NinjaExtraAPI):
    """NinjaExtraAPI subclass that injects framework error schemas into OpenAPI output."""

    @override
    def get_openapi_schema(self, **kwargs) -> OpenAPISchema:  # pyright: ignore[reportAny]
        schema = super().get_openapi_schema(**kwargs)
        for path_methods in schema.get("paths", {}).values():
            for method_detail in path_methods.values():
                if not isinstance(method_detail, dict) or "responses" not in method_detail:
                    continue
                responses = method_detail["responses"]
                has_auth = "security" in method_detail and method_detail["security"]

                # Always inject: 422 ValidationError, 500 InternalError
                if "422" not in responses:
                    responses["422"] = {
                        "description": "Unprocessable Entity",
                        "content": {"application/json": {"schema": _VALIDATION_ERROR_SCHEMA}},
                    }
                if "500" not in responses:
                    responses["500"] = {
                        "description": "Internal Server Error",
                        "content": {"application/json": {"schema": _INTERNAL_ERROR_SCHEMA}},
                    }

                # Conditional on auth: 401, 403
                if has_auth:
                    if "401" not in responses:
                        responses["401"] = {
                            "description": "Unauthorized",
                            "content": {
                                "application/json": {"schema": _AUTHENTICATION_ERROR_SCHEMA}
                            },
                        }
                    if "403" not in responses:
                        responses["403"] = {
                            "description": "Forbidden",
                            "content": {
                                "application/json": {"schema": _AUTHORIZATION_ERROR_SCHEMA}
                            },
                        }

        return schema


api = TaggedErrorAPI()
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
