import json
import logging
from collections import defaultdict
from typing import override

from django.http import Http404, HttpRequest, HttpResponse
from ninja.openapi.schema import OpenAPISchema
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController

from blog.api import router as blog_router
from core.decorators import RAISED_EXCEPTIONS_ATTR
from core.exceptions import AppException
from orders.api import router as orders_router
from products.api import router as products_router

logger = logging.getLogger(__name__)

# Framework error schemas — defined as JSON schema dicts (not Pydantic models)
# because they are only needed for OpenAPI generation, not serialization.

_NOT_FOUND_BODY: dict = {"tag": "NotFoundError", "detail": "Not found"}

_EXCEPTION_TAGS: dict[type[Exception], str] = {
    Http404: "NotFoundError",
}


def _tag_for(exc: Exception) -> str:
    """Derive a tag from an exception instance.

    Checks _EXCEPTION_TAGS first (for exceptions whose class name doesn't match
    the desired tag, e.g. Http404 → "NotFoundError"). Falls back to class name,
    which naturally gives "AuthenticationError", "AuthorizationError", etc.
    """
    for cls in type(exc).__mro__:
        if cls in _EXCEPTION_TAGS:
            return _EXCEPTION_TAGS[cls]
    return type(exc).__name__


def _error_schema(tag: str, extra_properties: dict | None = None) -> dict:
    """Build a JSON Schema object for a tagged error response."""
    properties: dict = {
        "tag": {"type": "string", "const": tag},
        "detail": {"type": "string"},
    }
    required = ["tag", "detail"]
    if extra_properties:
        properties.update(extra_properties)
        required = list(dict.fromkeys([*required, *extra_properties.keys()]))
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "title": tag,
    }


_VALIDATION_ERROR_ITEM_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "loc": {"type": "array", "items": {"type": "string"}},
        "msg": {"type": "string"},
        "ctx": {"type": "object"},
    },
    "required": ["type", "loc", "msg"],
}

_VALIDATION_ERROR_SCHEMA = _error_schema(
    "ValidationError",
    {"detail": {"type": "array", "items": _VALIDATION_ERROR_ITEM_SCHEMA}},
)
_AUTHENTICATION_ERROR_SCHEMA = _error_schema("AuthenticationError")
_AUTHORIZATION_ERROR_SCHEMA = _error_schema("AuthorizationError")
_INTERNAL_ERROR_SCHEMA = _error_schema("InternalError")


class TaggedErrorAPI(NinjaExtraAPI):
    """NinjaExtraAPI subclass that injects tagged error responses."""

    @override
    def set_default_exception_handlers(self) -> None:
        super().set_default_exception_handlers()
        self.add_exception_handler(AppException, self._handle_app_exception)
        self.add_exception_handler(Exception, self._handle_exception)

    @override
    def on_exception(self, request: HttpRequest, exc: Exception) -> HttpResponse:  # pyright: ignore[reportIncompatibleMethodOverride]
        response = super().on_exception(request, exc)
        try:
            body = json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return response
        if "tag" not in body:
            body["tag"] = _tag_for(exc)
            response.content = json.dumps(body).encode()
        return response

    def _handle_app_exception(self, request: HttpRequest, exc: AppException) -> HttpResponse:
        return self.create_response(request, exc.to_dict(), status=exc.status)

    def _handle_exception(self, request: HttpRequest, exc: Exception) -> HttpResponse:
        logger.exception("Unhandled exception: %s", exc)
        return self.create_response(
            request,
            {"tag": "InternalError", "detail": "Internal server error"},
            status=500,
        )

    def _collect_raised_exceptions(
        self,
    ) -> dict[str, tuple[type[AppException], ...]]:
        """Collect @raises() metadata from all operations, keyed by operationId."""
        result: dict[str, tuple[type[AppException], ...]] = {}
        for _prefix, router in self._routers:
            for _path, path_view in router.path_operations.items():
                for operation in path_view.operations:
                    raised = getattr(
                        operation.view_func, RAISED_EXCEPTIONS_ATTR, None
                    )
                    if raised is None:
                        continue
                    op_id = operation.operation_id or self.get_openapi_operation_id(
                        operation
                    )
                    result[op_id] = raised
        return result

    @override
    def get_openapi_schema(self, **kwargs) -> OpenAPISchema:  # pyright: ignore[reportAny]
        schema = super().get_openapi_schema(**kwargs)
        raised_by_op_id = self._collect_raised_exceptions()

        for path_methods in schema.get("paths", {}).values():
            for method_detail in path_methods.values():
                if not isinstance(method_detail, dict) or "responses" not in method_detail:
                    continue
                responses = method_detail["responses"]
                has_auth = method_detail.get("security")

                # Framework error injection
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

                # Domain error injection via @raises()
                op_id = method_detail.get("operationId")
                raised = raised_by_op_id.get(op_id) if op_id else None
                if raised is None:
                    continue

                by_status: dict[int, list[type[AppException]]] = defaultdict(list)
                for exc_cls in raised:
                    by_status[exc_cls.status].append(exc_cls)

                for status_code, exc_classes in by_status.items():
                    status_key = str(status_code)
                    # Manual response= declaration takes precedence (keys may be int or str)
                    if status_key in responses or status_code in responses:
                        continue

                    if len(exc_classes) == 1:
                        error_schema = exc_classes[0].Schema.model_json_schema()
                    else:
                        error_schema = {
                            "oneOf": [
                                exc_cls.Schema.model_json_schema()
                                for exc_cls in exc_classes
                            ],
                            "discriminator": {"propertyName": "tag"},
                        }

                    responses[status_key] = {
                        "description": "Domain Error",
                        "content": {"application/json": {"schema": error_schema}},
                    }

        return schema


api = TaggedErrorAPI()
api.register_controllers(NinjaJWTDefaultController)  # pyright: ignore[reportUnknownMemberType]


def django_404_handler(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Django-level 404 handler for URL routing misses (outside Ninja's exception system)."""
    return HttpResponse(
        json.dumps(_NOT_FOUND_BODY),
        content_type="application/json",
        status=404,
    )


api.add_router("/blog", blog_router)
api.add_router("/orders", orders_router)
api.add_router("/products", products_router)
