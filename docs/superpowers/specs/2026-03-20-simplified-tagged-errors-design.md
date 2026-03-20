# Simplified Tagged Error Handling Design

Supersedes: `2026-03-19-tagged-error-handling-design.md`

## Problem

The current error handling has two pain points:

1. **Too many override points** — six `@api.exception_handler` decorators, each manually constructing tagged response dicts
2. **Verbose error raising** — `raise AppException(OrderNotFoundError(id=order_id, detail="Order not found"))` requires wrapping an `AppError` Pydantic model inside an `AppException`

## Goals

- Every error response includes a `tag` field for frontend discrimination
- Override as little as possible — lean on Ninja's default error handlers
- Domain errors are defined as simple exception subclasses with annotations — zero boilerplate
- Raising is direct: `raise OrderNotFoundError(id=order_id)`
- Call sites are type-safe (pyright validates argument types, required fields, unknown fields)
- OpenAPI schema still documents all error types with `const` tags for TypeScript generation

## Design

### 1. `AppException` — raisable, type-safe, auto-generates Schema

`AppException` uses `@dataclass_transform()` (PEP 681) so pyright treats subclass annotations as typed `__init__` params. `__init_subclass__` auto-generates a companion `TaggedSchema` for OpenAPI.

```python
# core/exceptions.py
from typing import Any, ClassVar, dataclass_transform

from core.schemas import TaggedSchema


@dataclass_transform()
class AppException(Exception):
    """Base for all domain errors. Subclass to define typed, raisable errors."""

    tag: ClassVar[str] = ""
    status: ClassVar[int] = 400
    Schema: ClassVar[type[TaggedSchema]]

    detail: str = ""

    def __init_subclass__(cls, status: int = 400, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.tag = cls.__name__
        cls.status = status

        # Collect own annotations (not inherited from AppException)
        own_annotations: dict[str, type] = {}
        for name, ann in cls.__annotations__.items():
            if name in ("tag", "detail", "status", "Schema"):
                continue
            own_annotations[name] = ann

        # Build companion TaggedSchema for OpenAPI generation.
        # TaggedSchema.__init_subclass__ handles the Literal[tag] annotation.
        schema_namespace: dict[str, Any] = {
            "__annotations__": {"detail": str, **own_annotations},
        }
        for name in own_annotations:
            if hasattr(cls, name):
                schema_namespace[name] = getattr(cls, name)

        cls.Schema = type(cls.__name__, (TaggedSchema,), schema_namespace)

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)
        Exception.__init__(self, getattr(self, "detail", ""))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"tag": self.tag, "detail": self.detail}
        own_annotations = {
            k
            for k in type(self).__annotations__
            if k not in ("tag", "detail", "status", "Schema")
        }
        for field in own_annotations:
            if hasattr(self, field):
                result[field] = getattr(self, field)
        return result
```

### 2. Defining domain errors — zero boilerplate

```python
# orders/exceptions.py
from core.exceptions import AppException

class OrderNotFoundError(AppException):
    id: int
    detail: str = "Order not found"

class OrderNotAccessibleError(AppException):
    id: int
    detail: str = "Order not accessible"
```

Each subclass auto-gets:
- `tag = "OrderNotFoundError"` (class attribute)
- `status = 400` (inherited, overridable via `class MyError(AppException, status=404)`)
- `OrderNotFoundError.Schema` — a `TaggedSchema` with `tag: Literal["OrderNotFoundError"]`, `detail: str`, `id: int`

### 3. Raising — direct, type-safe

```python
# orders/service.py
raise OrderNotFoundError(id=order_id)
```

Pyright validates call sites via `@dataclass_transform()`:
- `OrderNotFoundError(id="wrong")` → pyright error (wrong type)
- `OrderNotFoundError()` → pyright error (missing required `id`)
- `OrderNotFoundError(id=1, bogus=True)` → pyright error (unknown field)

### 4. Endpoint declarations — use `.Schema`

```python
# orders/api.py
from pydantic import RootModel
from orders.exceptions import OrderNotFoundError, OrderNotAccessibleError

class OrderErrors(RootModel[OrderNotFoundError.Schema | OrderNotAccessibleError.Schema]):
    pass

@router.get("/{order_id}/", response={200: OrderResponse, 400: OrderErrors})
def get_order(request, order_id: int) -> OrderResponse:
    return service.get_order(order_id)
```

### 5. `TaggedErrorAPI` — two new method overrides + unchanged `get_openapi_schema`

```python
# project/api.py

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


class TaggedErrorAPI(NinjaExtraAPI):
    """NinjaExtraAPI subclass that adds tagged error responses."""

    @override
    def set_default_exception_handlers(self) -> None:
        super().set_default_exception_handlers()  # keep Ninja's defaults
        self.add_exception_handler(AppException, self._handle_app_exception)
        # Ninja's default Exception handler re-raises in production.
        # We replace it to return a tagged JSON 500 response.
        self.add_exception_handler(Exception, self._handle_exception)

    @override
    def on_exception(self, request: HttpRequest, exc: Exc) -> HttpResponse:
        response = super().on_exception(request, exc)
        try:
            body = json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return response  # Can't inject tag into non-JSON responses
        changed = False
        if "tag" not in body:
            body["tag"] = _tag_for(exc)
            changed = True
        if isinstance(exc, HttpError) and "status_code" not in body:
            body["status_code"] = exc.status_code
            changed = True
        if changed:
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

    @override
    def get_openapi_schema(self, **kwargs) -> OpenAPISchema:
        # Unchanged in structure — injects framework error schemas.
        # See "OpenAPI Schema Injection" section below.
        ...
```

### 6. How errors flow

| Exception | Who handles it | Response body | Tag source |
|---|---|---|---|
| `AppException` | `_handle_app_exception` | `exc.to_dict()` | Already in body (from `cls.tag`) |
| `ValidationError` | Ninja's default | `{"detail": [...errors]}` | Injected by `on_exception` → `"ValidationError"` |
| `AuthenticationError` | Ninja's default (via `HttpError` MRO) | `{"detail": "Unauthorized", "status_code": 401}` | Injected → `"AuthenticationError"` (class name) |
| `AuthorizationError` | Ninja's default (via `HttpError` MRO) | `{"detail": "Forbidden", "status_code": 403}` | Injected → `"AuthorizationError"` (class name) |
| `HttpError` | Ninja's default | `{"detail": "...message", "status_code": N}` | Injected → `"HttpError"` (class name) |
| `Http404` | Ninja's default | `{"detail": "Not Found"}` | Injected → `"NotFoundError"` (via `_EXCEPTION_TAGS`) |
| `Exception` | `_handle_exception` | `{"tag": "InternalError", ...}` | Already in body |

MRO note: `AuthenticationError` and `AuthorizationError` are subclasses of `HttpError`. Ninja's `_lookup_exception_handler` walks the MRO, so the registered `HttpError` handler catches all three. `type(exc).__name__` produces the correct tag for each.

`status_code` injection: `on_exception` injects `status_code` into the body for all `HttpError` instances (including `AuthenticationError` and `AuthorizationError`).

### 7. Validation error shape change

Ninja's default validation handler returns `{"detail": exc.errors}` — the errors array lives inside `detail`. The current implementation restructures this to `{"detail": "Validation error", "errors": [...]}`.

After this change, the response becomes:

```json
{
  "tag": "ValidationError",
  "detail": [
    {"type": "enum", "loc": ["query", "status"], "msg": "..."}
  ]
}
```

### 8. `django_404_handler` — unchanged

This handler lives outside Ninja's exception system (handles Django-level URL routing misses). It stays as-is:

```python
_NOT_FOUND_BODY: dict = {"tag": "NotFoundError", "detail": "Not found"}

def django_404_handler(request: HttpRequest, exception: Exception) -> HttpResponse:
    return HttpResponse(
        json.dumps(_NOT_FOUND_BODY),
        content_type="application/json",
        status=404,
    )
```

Note: Ninja's default 404 handler uses `"Not Found"` (capital F), while `_NOT_FOUND_BODY` uses `"Not found"`. Both carry `tag: "NotFoundError"` which is what the frontend discriminates on.

### 9. OpenAPI Schema Injection

`get_openapi_schema` is unchanged in structure — it still injects framework error schemas into every endpoint. The only schema change is for validation errors, where `detail` becomes an array:

```python
_VALIDATION_ERROR_SCHEMA = _error_schema(
    "ValidationError",
    {"detail": {"type": "array", "items": _VALIDATION_ERROR_ITEM_SCHEMA}},
)
```

All other schemas remain unchanged:

- `_AUTHENTICATION_ERROR_SCHEMA` = `_error_schema("AuthenticationError")`
- `_AUTHORIZATION_ERROR_SCHEMA` = `_error_schema("AuthorizationError")`
- `_INTERNAL_ERROR_SCHEMA` = `_error_schema("InternalError")`

Injection rules (unchanged):
- **Always injected:** 422 `ValidationError`, 500 `InternalError`
- **Conditional on `security` config:** 401 `AuthenticationError`, 403 `AuthorizationError`

### 10. Frontend usage — unchanged

All errors are discriminated by `tag` using `ts-pattern`:

```typescript
match(error)
    .with({ tag: "OrderNotFoundError" }, (e) => `Order ${e.id} not found`)
    .with({ tag: "ValidationError" }, (e) => `${e.detail.length} validation errors`)
    .with({ tag: "AuthenticationError" }, () => `Please log in`)
    .exhaustive();
```

## What changes from current implementation

| Before | After |
|---|---|
| `AppError` (Pydantic model) + `AppException` (wrapper) | `AppException` with `@dataclass_transform()` — one class per error |
| `raise AppException(OrderNotFoundError(...))` | `raise OrderNotFoundError(id=order_id)` |
| `response={400: RootModel[OrderNotFoundError \| ...]}` | `response={400: RootModel[OrderNotFoundError.Schema \| ...]}` |
| 6 `@api.exception_handler` decorators | Zero — `set_default_exception_handlers` + `on_exception` |
| Each handler manually builds `{"tag": ...}` dicts | `on_exception` injects tags into Ninja's default responses |
| `exc.error.model_dump()` | `exc.to_dict()` |
| Validation response: `{"detail" (string), "errors"}` | Ninja's default: `{"detail" (array of errors)}` |

## What stays the same

- `TaggedSchema` still used for response schemas (`PendingOrder`, `ShippedOrder`, etc.)
- Domain error Schemas extend `TaggedSchema` — auto-tagged via `__init_subclass__`
- `RootModel` used to compose error unions per endpoint
- `get_openapi_schema` override injects framework error schemas
- `django_404_handler` for Django-level 404s
- TypeScript types generated via `@hey-api/openapi-ts`
- `ts-pattern` for exhaustive matching on the frontend

## What gets deleted

- `core/schemas.py` — `AppError` class (replaced by `AppException`)
- `core/exceptions.py` — current `AppException` (replaced by new `AppException` with `@dataclass_transform()`)
- `project/api.py` — all 6 `@api.exception_handler` decorators

## Files to change

- `core/exceptions.py` — rewrite: new `AppException` with `@dataclass_transform()`, `__init_subclass__`, `to_dict()`
- `core/schemas.py` — delete `AppError` class
- `orders/schemas.py` — move `OrderNotFoundError`, `OrderNotAccessibleError` to `orders/exceptions.py`; update `OrderErrors` to use `.Schema`
- `orders/exceptions.py` — create: define error classes as `AppException` subclasses
- `orders/api.py` — update imports, update `raise` sites from `raise AppException(Error(...))` to `raise Error(...)`
- `project/api.py` — replace `@api.exception_handler` decorators with `TaggedErrorAPI` overrides (`set_default_exception_handlers`, `on_exception`), update validation error OpenAPI schema, change `_handle_app_exception` to use `exc.to_dict()`
- `project/tests.py` — specific test changes:
  - `test_validation_error_has_tag`: replace `assertIn("errors", data)` with `assertIsInstance(data["detail"], list)` — errors now live in `detail`
  - `test_validation_error_item_schema_includes_ctx`: change `content["properties"]["errors"]["items"]` to `content["properties"]["detail"]["items"]` — schema key changed
  - `test_endpoint_has_validation_error_schema`: no change needed (still checks `tag` const)
  - `test_domain_error_has_tag`: no change needed (still checks `tag` value)
- `client/` — regenerate types (validation error shape change), then update call sites:
  - `client/src/ts-pattern/errors.ts`: update doc comment example from `e.errors` to `e.detail`
  - `client/src/ts-pattern/orders.ts`: change `flattenValidationErrors<...>(e.errors)` to `flattenValidationErrors<...>(e.detail)`
  - `flattenValidationErrors` function itself is unchanged — it takes `ValidationErrorItem[]`
