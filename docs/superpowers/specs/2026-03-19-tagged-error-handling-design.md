# Tagged Error Handling Design

## Problem

Engineers must manually compose error union types per endpoint. On the frontend, there's no consistent way to discriminate between different error types — domain errors, validation errors, auth errors, etc. — using a single `tag` field.

## Goals

- Every error response (domain and framework) includes a `tag` field for frontend discrimination
- Domain errors are explicitly composed per endpoint using `RootModel` unions (same pattern as success types)
- Framework errors (validation, auth, etc.) are automatically injected into every endpoint's OpenAPI schema
- Frontend can match on `tag` exclusively using `ts-pattern`, regardless of error origin
- Simplify the backend: one generic `AppException`, no per-error exception wrappers

## Design

### 1. Simplified `AppException`

Remove per-error exception wrappers (`OrderNotFound`, `OrderNotAccessible`, etc.). `AppException` becomes a single generic exception that wraps any `AppError`:

```python
# core/exceptions.py
class AppException(Exception):
    def __init__(self, error: AppError):
        super().__init__()
        self.error = error
```

No `status_code` parameter — all domain errors return HTTP 400. This is a deliberate trade-off: we lose HTTP status code semantics for domain errors (e.g., 404 vs 403), but the frontend discriminates on `tag` exclusively, making status codes redundant for domain errors. Framework errors (auth, validation) retain their standard status codes.

### 2. Domain Error Definition

No changes to the existing pattern. Engineers define errors as `AppError` subclasses (auto-tagged via `TaggedSchema.__init_subclass__`):

```python
# orders/schemas.py
class OrderNotFoundError(AppError):
    id: int

class OrderNotAccessibleError(AppError):
    id: int
```

### 3. Domain Error Composition

Engineers compose domain errors into `RootModel` unions per endpoint, same as success types:

```python
# orders/schemas.py
class OrderErrors(RootModel[OrderNotFoundError | OrderNotAccessibleError]):
    pass
```

### 4. Endpoint Declaration

Domain errors go on status 400:

```python
# orders/api.py
@router.get(
    "/{order_id}/",
    response={200: OrderResponse, 400: OrderErrors},
)
def get_order(request, order_id: int) -> OrderResponse:
    return service.get_order(order_id)
```

### 5. Raising Domain Errors

```python
# orders/service.py
raise AppException(OrderNotFoundError(id=order_id, detail="Order not found"))
```

### 6. Centralized Exception Handler

One handler in `project/api.py` that normalizes all errors into tagged responses:

```python
from ninja.errors import (
    AuthenticationError as NinjaAuthenticationError,
    AuthorizationError as NinjaAuthorizationError,
    ValidationError as NinjaValidationError,
    HttpError as NinjaHttpError,
)
from django.http import Http404

@api.exception_handler(Exception)
def handle_exception(request, exc):
    if isinstance(exc, AppException):
        return api.create_response(request, exc.error.model_dump(), status=400)

    if isinstance(exc, NinjaValidationError):
        return api.create_response(request, {
            "tag": "ValidationError",
            "detail": "Validation error",
            "errors": exc.errors,
        }, status=422)

    if isinstance(exc, NinjaAuthenticationError):
        return api.create_response(request, {
            "tag": "AuthenticationError",
            "detail": str(exc),
        }, status=401)

    if isinstance(exc, NinjaAuthorizationError):
        return api.create_response(request, {
            "tag": "AuthorizationError",
            "detail": str(exc),
        }, status=403)

    if isinstance(exc, NinjaHttpError):
        return api.create_response(request, {
            "tag": "HttpError",
            "detail": exc.message,
            "status_code": exc.status_code,
        }, status=exc.status_code)

    if isinstance(exc, Http404):
        return api.create_response(request, {
            "tag": "NotFoundError",
            "detail": "Not found",
        }, status=404)

    # Catch-all for unhandled exceptions.
    # Log the exception so it's visible in error reporters (Sentry, etc.)
    # before returning a generic tagged response.
    import logging
    logger = logging.getLogger(__name__)
    logger.exception("Unhandled exception: %s", exc)
    return api.create_response(request, {
        "tag": "InternalError",
        "detail": "Internal server error",
    }, status=500)
```

### 7. OpenAPI Schema Injection

Subclass `NinjaExtraAPI` (which the project already uses) and override `get_openapi_schema()` to inject universal framework error responses into every endpoint's schema:

- **Always injected:** `ValidationError` (422), `HttpError` (variable), `InternalError` (500)
- **Conditional on auth config:** `AuthenticationError` (401), `AuthorizationError` (403)

The framework error schemas are defined as JSON schema dicts within the override (not as Pydantic models) since they are only needed for OpenAPI generation, not for serialization.

### 8. Frontend Usage

All errors — domain and framework — are discriminated by `tag` using `ts-pattern`:

```typescript
import { match } from "ts-pattern";

function handleError(error: OrderErrors | ValidationError | AuthenticationError | InternalError) {
    return match(error)
        .with({ tag: "OrderNotFoundError" }, (e) => `Order ${e.id} not found`)
        .with({ tag: "OrderNotAccessibleError" }, (e) => `Order ${e.id} not accessible`)
        .with({ tag: "ValidationError" }, (e) => `Validation failed: ${e.errors.length} errors`)
        .with({ tag: "AuthenticationError" }, () => `Please log in`)
        .with({ tag: "InternalError" }, () => `Something went wrong`)
        .exhaustive();
}
```

## What Changes

| Before | After |
|--------|-------|
| Per-error exception wrappers (`OrderNotFound(AppException)`) | Deleted — use `raise AppException(error)` directly |
| `AppException` takes `status_code` + `AppError` | `AppException` takes only `AppError` — always 400 |
| Individual exception handlers per type | One centralized handler for all exceptions |
| No framework errors in OpenAPI schema | Framework errors auto-injected via `get_openapi_schema()` |
| Frontend branches on status code + type | Frontend matches on `tag` exclusively |

## What Stays the Same

- `AppError` extends `TaggedSchema` — auto-tagged via `__init_subclass__`
- Domain errors defined as `AppError` subclasses with additional fields
- `RootModel` used to compose unions (now for errors too, not just success types)
- TypeScript types generated via `@hey-api/openapi-ts`
- `ts-pattern` for exhaustive matching on the frontend

## Files to Change

- `core/exceptions.py` — simplify `AppException` (remove `status_code`)
- `core/schemas.py` — no changes needed
- `project/api.py` — replace individual handlers with centralized handler, subclass `NinjaExtraAPI` with `get_openapi_schema()` override
- `orders/exceptions.py` — delete (per-error wrappers no longer needed)
- `orders/schemas.py` — add `OrderErrors` RootModel
- `orders/api.py` — update endpoint `response` dicts, update raise sites
- `products/schemas.py` — add `ProductErrors` RootModel
- `products/api.py` — update endpoint `response` dicts, migrate inline dict error returns to `raise AppException(...)` pattern
- `blog/api.py` — add `PostErrors` RootModel, update endpoint declarations (note: blog success types use `status` as discriminator via `Annotated[..., Field(discriminator="status")]`, not `TaggedSchema` — this is unrelated to error handling and stays as-is)
- `client/` — regenerate types, update ts-pattern examples
