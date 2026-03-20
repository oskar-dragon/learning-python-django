# `@raises()` Decorator Design

Supersedes the endpoint declaration pattern from `2026-03-20-simplified-tagged-errors-design.md` (section 4 only — everything else in that spec remains valid).

## Problem

Every endpoint that can raise domain errors needs two pieces of boilerplate:

1. A `response={400: OrderErrors}` dict in the decorator
2. A `*Errors` RootModel wrapper class in `schemas.py`

```python
# schemas.py — boilerplate wrapper
class OrderErrors(RootModel[OrderNotFoundError.Schema | OrderNotAccessibleError.Schema]):
    pass

# api.py — verbose response dict
@router.get("/{order_id}/", response={200: OrderResponse, 400: OrderErrors})
def get_order(request: HttpRequest, order_id: int) -> OrderResponse:
    return service.get_order(order_id)
```

The runtime error handling doesn't need any of this — `TaggedErrorAPI` catches all `AppException` raises globally. The `response=` dict and `*Errors` classes exist only to populate OpenAPI docs.

## Goal

- Endpoints declare which domain errors they can raise via a `@raises()` decorator
- No manual `response={400: ...}` dicts for error schemas
- No manual `*Errors` RootModel wrapper classes
- OpenAPI docs still document all domain error types per endpoint
- Zero runtime behavior change — decorator is metadata-only

## Design

### 1. `raises()` decorator — metadata-only

```python
# core/decorators.py
from core.exceptions import AppException

RAISED_EXCEPTIONS_ATTR = "_raised_exceptions"

def raises(*exceptions: type[AppException]):
    """Mark an endpoint with the domain errors it can raise.

    Pure metadata — has no runtime effect. TaggedErrorAPI reads this
    during OpenAPI schema generation to inject error response schemas.
    """
    def decorator(func):
        func._raised_exceptions = exceptions
        return func
    return decorator
```

### 2. OpenAPI injection in `TaggedErrorAPI.get_openapi_schema()`

The existing `get_openapi_schema()` override already iterates all endpoints to inject framework errors (422, 500, 401, 403). We extend it to also read `_raised_exceptions` metadata and inject domain error schemas.

The key challenge is mapping from Django Ninja's OpenAPI path/method entries back to the view functions that have `_raised_exceptions`. Django Ninja's router stores operation references that link paths to view functions.

**Schema generation from `_raised_exceptions`:**

1. For each endpoint with `_raised_exceptions`, group exception classes by their `status` class variable (most will be 400)
2. For each status code group, generate a JSON schema:
   - Single exception → inline its `.Schema`'s JSON schema directly (no `oneOf` wrapper)
   - Multiple exceptions → wrap in `oneOf` with `tag` as discriminator
3. Inject into the endpoint's OpenAPI responses under that status code

**Example output for `@raises(OrderNotFoundError, OrderNotAccessibleError)`:**

```json
{
  "400": {
    "description": "Domain Error",
    "content": {
      "application/json": {
        "schema": {
          "oneOf": [
            { "$ref": "#/components/schemas/OrderNotFoundError" },
            { "$ref": "#/components/schemas/OrderNotAccessibleError" }
          ],
          "discriminator": {
            "propertyName": "tag"
          }
        }
      }
    }
  }
}
```

**Accessing view functions from OpenAPI iteration:**

Django Ninja's `NinjaAPI` has `_routers` which contain `PathView` objects with operations. Each operation has a `view_func`. During `get_openapi_schema()`, we need to build a mapping from OpenAPI path+method to view function. We'll do this by iterating `self._routers` before the schema injection loop.

### 3. Endpoint declarations — before and after

**Before:**
```python
# orders/schemas.py
class OrderErrors(RootModel[OrderNotFoundError.Schema | OrderNotAccessibleError.Schema]):
    pass

# orders/api.py
@router.get("/{order_id}/", response={200: OrderResponse, 400: OrderErrors})
def get_order(request: HttpRequest, order_id: int) -> OrderResponse:
    return service.get_order(order_id)
```

**After:**
```python
# orders/api.py
from core.decorators import raises
from orders.exceptions import OrderNotFoundError, OrderNotAccessibleError

@router.get("/{order_id}/")
@raises(OrderNotFoundError, OrderNotAccessibleError)
def get_order(request: HttpRequest, order_id: int) -> OrderResponse:
    return service.get_order(order_id)
```

### 4. What gets deleted

- `OrderErrors` class from `orders/schemas.py`
- `ProductErrors` class from `products/schemas.py`
- `PostErrors` class from `blog/schemas.py`
- All `response={400: ...}` dicts from endpoint decorators
- `response={200: ProductResponse, 400: ProductErrors}` becomes just `response=ProductResponse` (or return type annotation)
- Related imports of `*Errors` classes

### 5. What stays the same

- `AppException` subclasses and their auto-generated `.Schema` — unchanged
- `TaggedErrorAPI` runtime exception handling (`_handle_app_exception`, `_handle_exception`, `on_exception`) — unchanged
- Framework error injection (422, 500, 401, 403) — unchanged
- `TaggedSchema`, `TaggedModelSchema` — unchanged
- Frontend `ts-pattern` matching — unchanged

### 6. Edge case: mixed status codes

`AppException` subclasses can declare custom status codes:

```python
class OrderNotFoundError(AppException, status=404):
    id: int
```

The decorator groups by status code automatically. An endpoint decorated with `@raises(OrderNotFoundError, OrderNotAccessibleError)` where `OrderNotFoundError` has `status=404` and `OrderNotAccessibleError` has `status=400` would produce both a 400 and 404 entry in OpenAPI.

### 7. Resolving view functions during OpenAPI generation

The decorator stashes `_raised_exceptions` directly on the view function. During `get_openapi_schema()`, we need to access view functions to read this metadata. Django Ninja's router stores `PathView` objects with operations, each having a `.view_func`.

**Primary approach:** Build a `{(path, method): view_func}` lookup by iterating `self._routers` → `path_operations` → `PathView` → operations before the schema injection loop. Use this lookup during the existing path iteration to check for `_raised_exceptions`.

**If router introspection proves fragile** (it depends on Django Ninja's internal path-building logic which could change between versions), fall back to stashing metadata on the function and matching by function identity during the operation iteration — the function reference is stable regardless of path formatting.

### 8. `@raises` and `response=` coexistence

If an endpoint declares both `@raises(...)` and `response={400: SomeErrors}`, the manually declared `response` takes precedence for that status code. `@raises` only injects into status codes not already present in the endpoint's declared responses. This prevents conflicts during incremental adoption.

### 9. Single-exception behavior

When `@raises` contains a single exception for a given status code, the schema is inlined directly — no `oneOf` wrapper. For example, `@raises(PostNotFoundError)` produces:

```json
{
  "400": {
    "description": "Domain Error",
    "content": {
      "application/json": {
        "schema": { "$ref": "#/components/schemas/PostNotFoundError" }
      }
    }
  }
}
```

## Files to change

- `core/decorators.py` — **new**: `raises()` decorator
- `project/api.py` — extend `get_openapi_schema()` to read `_raised_exceptions` and inject domain error schemas
- `orders/api.py` — replace `response={200: OrderResponse, 400: OrderErrors}` with `@raises(...)`, remove `OrderErrors` import
- `orders/schemas.py` — delete `OrderErrors` class
- `products/api.py` — replace `response={200: ProductResponse, 400: ProductErrors}` with `response=ProductResponse` + `@raises(...)`, remove `ProductErrors` import
- `products/schemas.py` — delete `ProductErrors` class
- `blog/api.py` — replace `response={200: PostResponse, 400: PostErrors}` with `response=PostResponse` + `@raises(...)`, remove `PostErrors` import
- `blog/schemas.py` — delete `PostErrors` class
- Tests — update OpenAPI schema assertions to expect `oneOf` structure instead of `$ref` to `*Errors` models

## Testing strategy

- **Unit test `raises()` decorator**: verify it stashes exception classes on the function
- **OpenAPI schema tests (new coverage)**: no existing tests assert on domain error schemas in OpenAPI — these are entirely new tests, not updates. Verify domain error schemas appear in the correct endpoints with correct status codes, `oneOf` structure (multiple errors) and inline schema (single error), and discriminator
- **Integration tests**: existing tests should continue passing since runtime behavior is unchanged
- **Mixed status code test**: verify an endpoint with errors of different status codes produces multiple response entries. Will need a test-only exception class since no current domain errors use non-default status codes
- **Coexistence test**: verify that `@raises` does not overwrite a manually declared `response={400: ...}` on the same endpoint
