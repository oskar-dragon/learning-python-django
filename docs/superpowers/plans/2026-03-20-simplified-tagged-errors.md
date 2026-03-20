# Simplified Tagged Error Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace verbose `AppException(AppError(...))` pattern with direct `raise OrderNotFoundError(...)`, and consolidate 6 exception handler decorators into 2 method overrides on `TaggedErrorAPI`.

**Architecture:** `AppException` gains `@dataclass_transform()` so subclasses are zero-boilerplate, type-safe, directly raisable. `__init_subclass__` auto-generates companion `TaggedSchema` classes for OpenAPI. Framework errors use Ninja's defaults with tag injection via `on_exception` override.

**Tech Stack:** Django Ninja, Pydantic v2, ninja-extra, `@dataclass_transform()` (PEP 681), TypeScript (`@hey-api/openapi-ts`, `ts-pattern`)

**Spec:** `docs/superpowers/specs/2026-03-20-simplified-tagged-errors-design.md`

**Important:** Tasks 1-3 are atomic — the system is broken between them. `project/api.py` references `exc.error.model_dump()` which no longer exists after Task 1's rewrite of `AppException`. Don't run the full test suite until Task 3 is complete. Run only the scoped test commands listed in each task.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `core/exceptions.py` | Rewrite | New `AppException` with `@dataclass_transform()`, `__init_subclass__`, `to_dict()` |
| `core/schemas.py` | Modify | Delete `AppError` class (keep `TaggedSchema`, `TaggedModelSchema`) |
| `core/tests.py` | Modify | Rewrite `AppExceptionTest`, update `AppError` tests |
| `orders/exceptions.py` | Create | `OrderNotFoundError`, `OrderNotAccessibleError` as `AppException` subclasses |
| `orders/schemas.py` | Modify | Remove error classes, update `OrderErrors` to use `.Schema` |
| `orders/service.py` | Modify | Change `raise AppException(Error(...))` to `raise Error(...)` |
| `orders/api.py` | Modify | Update imports |
| `products/exceptions.py` | Create | `ProductNotFoundError`, `ProductHiddenError` as `AppException` subclasses |
| `products/schemas.py` | Modify | Remove error classes, update `ProductErrors` to use `.Schema` |
| `products/api.py` | Modify | Change raise sites, update imports |
| `blog/exceptions.py` | Create | `PostNotFoundError` as `AppException` subclass |
| `blog/schemas.py` | Modify | Remove error class, update `PostErrors` to use `.Schema` |
| `blog/api.py` | Modify | Change raise site, update imports |
| `project/api.py` | Modify | Replace 6 decorators with `TaggedErrorAPI` overrides, update OpenAPI schema |
| `project/tests.py` | Modify | Update validation error assertions |
| `client/src/ts-pattern/errors.ts` | Modify | Update doc comment `e.errors` → `e.detail` |
| `client/src/ts-pattern/orders.ts` | Modify | Change `e.errors` → `e.detail` in `flattenValidationErrors` call |

---

### Task 1: Rewrite `AppException` with `@dataclass_transform()`

**Files:**
- Rewrite: `core/exceptions.py`
- Test: `core/tests.py`

- [ ] **Step 1: Write failing tests for new `AppException`**

Replace the existing `AppExceptionTest` class in `core/tests.py` with tests for the new behavior. Also remove the `AppError`-specific tests (`test_intermediate_class_gets_own_tag`, `test_intermediate_class_does_not_break_subclass_tags`) and the `AppError` import.

```python
# In core/tests.py — replace AppExceptionTest class (lines 185-201) with:

class AppExceptionTest(TestCase):
    def test_subclass_gets_class_name_as_tag(self) -> None:
        class TestError(AppException):
            code: int

        self.assertEqual(TestError.tag, "TestError")

    def test_stores_fields_from_kwargs(self) -> None:
        class TestError(AppException):
            code: int

        exc = TestError(code=42, detail="something went wrong")
        self.assertEqual(exc.detail, "something went wrong")
        self.assertEqual(exc.code, 42)

    def test_to_dict_includes_tag_detail_and_fields(self) -> None:
        class TestError(AppException):
            code: int

        exc = TestError(code=42, detail="something went wrong")
        self.assertEqual(
            exc.to_dict(),
            {"tag": "TestError", "detail": "something went wrong", "code": 42},
        )

    def test_is_exception_subclass(self) -> None:
        class TestError(AppException):
            code: int

        exc = TestError(code=42, detail="test")
        self.assertIsInstance(exc, Exception)

    def test_raise_and_catch(self) -> None:
        class TestError(AppException):
            code: int

        with self.assertRaises(AppException) as ctx:
            raise TestError(code=42, detail="test")
        self.assertEqual(ctx.exception.tag, "TestError")

    def test_default_status_is_400(self) -> None:
        class TestError(AppException):
            code: int

        self.assertEqual(TestError.status, 400)

    def test_custom_status(self) -> None:
        class TestError(AppException, status=404):
            code: int

        self.assertEqual(TestError.status, 404)

    def test_auto_generates_schema(self) -> None:
        class TestError(AppException):
            code: int

        schema = TestError.Schema
        instance = schema(code=42, detail="test")
        dump = instance.model_dump()
        self.assertEqual(dump["tag"], "TestError")
        self.assertEqual(dump["code"], 42)
        self.assertEqual(dump["detail"], "test")

    def test_schema_json_schema_has_const_tag(self) -> None:
        class TestError(AppException):
            code: int

        json_schema = TestError.Schema.model_json_schema()
        self.assertEqual(json_schema["properties"]["tag"]["const"], "TestError")

    def test_detail_defaults_to_empty_string(self) -> None:
        class TestError(AppException):
            pass

        exc = TestError()
        self.assertEqual(exc.detail, "")

    def test_detail_uses_subclass_default(self) -> None:
        class TestError(AppException):
            detail: str = "Custom default"

        exc = TestError()
        self.assertEqual(exc.detail, "Custom default")
```

Also update the imports at the top of `core/tests.py`: remove `AppError` from the `core.schemas` import, add `AppException` import from `core.exceptions` (already exists).

Remove the two `AppError`-specific tests (lines 72-83):
- `test_intermediate_class_gets_own_tag`
- `test_intermediate_class_does_not_break_subclass_tags`

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test core.tests.AppExceptionTest -v2`
Expected: FAIL — `AppException` doesn't have `@dataclass_transform()`, `to_dict()`, `Schema`, etc.

- [ ] **Step 3: Implement new `AppException`**

Rewrite `core/exceptions.py`:

```python
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test core.tests.AppExceptionTest -v2`
Expected: All 12 tests PASS

- [ ] **Step 5: Delete `AppError` from `core/schemas.py`**

Remove the `AppError` class (lines 125-128) from `core/schemas.py`. Keep everything else (`TaggedSchema`, `TaggedModelSchema`).

- [ ] **Step 6: Run full core test suite**

Run: `python manage.py test core -v2`
Expected: All tests PASS. The two deleted `AppError` tests and their import are already removed in step 1.

- [ ] **Step 7: Commit**

```bash
git add core/exceptions.py core/schemas.py core/tests.py
git commit -m "refactor(core): rewrite AppException with @dataclass_transform and auto-Schema"
```

---

### Task 2: Migrate domain errors to `AppException` subclasses

**Files:**
- Create: `orders/exceptions.py`, `products/exceptions.py`, `blog/exceptions.py`
- Modify: `orders/schemas.py`, `products/schemas.py`, `blog/schemas.py`
- Modify: `orders/service.py`, `orders/api.py`, `products/api.py`, `blog/api.py`

- [ ] **Step 1: Create `orders/exceptions.py`**

```python
from core.exceptions import AppException


class OrderNotFoundError(AppException):
    id: int
    detail: str = "Order not found"


class OrderNotAccessibleError(AppException):
    id: int
    detail: str = "Order not accessible"
```

- [ ] **Step 2: Create `products/exceptions.py`**

```python
from core.exceptions import AppException


class ProductNotFoundError(AppException):
    id: int
    detail: str = "Product not found"


class ProductHiddenError(AppException):
    id: int
    detail: str = "Product is not available"
```

- [ ] **Step 3: Create `blog/exceptions.py`**

```python
from core.exceptions import AppException


class PostNotFoundError(AppException):
    id: int
    detail: str = "Post not found"
```

- [ ] **Step 4: Update `orders/schemas.py`**

Remove `OrderNotFoundError`, `OrderNotAccessibleError` classes (lines 43-48). Update `OrderErrors` to use `.Schema`:

```python
# Remove these two classes:
# class OrderNotFoundError(AppError): ...
# class OrderNotAccessibleError(AppError): ...

# Replace OrderErrors (line 51-52) with:
from orders.exceptions import OrderNotAccessibleError, OrderNotFoundError

class OrderErrors(RootModel[OrderNotFoundError.Schema | OrderNotAccessibleError.Schema]):
    pass
```

Also remove `AppError` from the `core.schemas` import (keep `TaggedSchema`).

- [ ] **Step 5: Update `products/schemas.py`**

Remove `ProductNotFoundError`, `ProductHiddenError` classes (lines 23-28). Update `ProductErrors`:

```python
# Remove these two classes:
# class ProductNotFoundError(AppError): ...
# class ProductHiddenError(AppError): ...

# Replace ProductErrors (line 31-32) with:
from products.exceptions import ProductHiddenError, ProductNotFoundError

class ProductErrors(RootModel[ProductNotFoundError.Schema | ProductHiddenError.Schema]):
    pass
```

Also remove `AppError` from the `core.schemas` import (keep `TaggedModelSchema`).

- [ ] **Step 6: Update `blog/schemas.py`**

Remove `PostNotFoundError` class (lines 23-24). Update `PostErrors`:

```python
# Remove: class PostNotFoundError(AppError): ...

# Replace PostErrors (line 27-28) with:
from blog.exceptions import PostNotFoundError

class PostErrors(RootModel[PostNotFoundError.Schema]):
    pass
```

Also remove `AppError` from the `core.schemas` import (keep `TaggedModelSchema`).

- [ ] **Step 7: Update `orders/service.py` raise sites**

Change imports (line 1): replace `from core.exceptions import AppException` with `from orders.exceptions import OrderNotAccessibleError, OrderNotFoundError`.

Remove the error imports from `orders.schemas` (lines 3-10): remove `OrderNotAccessibleError`, `OrderNotFoundError` from that import.

Update raise sites:
- Line 61: `raise AppException(OrderNotFoundError(id=order_id, detail="Order not found"))` → `raise OrderNotFoundError(id=order_id)`
- Line 64: `raise AppException(OrderNotAccessibleError(id=order_id, detail="Order not accessible"))` → `raise OrderNotAccessibleError(id=order_id)`

(Default `detail` messages are now on the exception classes.)

- [ ] **Step 8: Update `orders/api.py` imports**

Remove `OrderErrors` from `orders.schemas` import if needed (check if it's used in the response dict — it is, so keep it). Remove `OrderNotFoundError`, `OrderNotAccessibleError` if they were imported here (they aren't — only in `service.py`). No changes to `orders/api.py` beyond verifying imports are correct.

- [ ] **Step 9: Update `products/api.py` raise sites**

Change imports: replace `from core.exceptions import AppException` and `from products.schemas import ... ProductNotFoundError, ProductHiddenError ...` with `from products.exceptions import ProductHiddenError, ProductNotFoundError`. Keep the `ProductErrors, ProductResponse` import from `products.schemas`.

Update raise sites:
- Line 30-32: `raise AppException(ProductNotFoundError(id=product_id, detail=f"Product {product_id} not found"))` → `raise ProductNotFoundError(id=product_id, detail=f"Product {product_id} not found")`
- Line 35-37: `raise AppException(ProductHiddenError(id=product_id, detail=f"Product {product_id} is not available"))` → `raise ProductHiddenError(id=product_id, detail=f"Product {product_id} is not available")`

(These pass explicit `detail` overriding the default — that's fine.)

- [ ] **Step 10: Update `blog/api.py` raise sites**

Change imports: replace `from core.exceptions import AppException` and `from blog.schemas import ... PostNotFoundError ...` with `from blog.exceptions import PostNotFoundError`. Keep `PostErrors, PostResponse` import from `blog.schemas`.

Update raise site:
- Line 21-23: `raise AppException(PostNotFoundError(id=post_id, detail=f"Post with id {post_id} not found"))` → `raise PostNotFoundError(id=post_id, detail=f"Post with id {post_id} not found")`

- [ ] **Step 11: Run all tests**

Run: `python manage.py test -v2`
Expected: FAIL — `project/api.py` still has `handle_app_exception` referencing the old `AppException.error` attribute. That's expected — we fix that in Task 3.

Verify that domain error tests pass (the `test_domain_error_has_tag` test in `project/tests.py` should still pass since the raise → catch → response path is similar).

- [ ] **Step 12: Commit**

```bash
git add orders/exceptions.py products/exceptions.py blog/exceptions.py
git add orders/schemas.py products/schemas.py blog/schemas.py
git add orders/service.py orders/api.py products/api.py blog/api.py
git commit -m "refactor: migrate domain errors to AppException subclasses with direct raise"
```

---

### Task 3: Replace exception handler decorators with `TaggedErrorAPI` overrides

**Files:**
- Modify: `project/api.py`
- Modify: `project/tests.py`

- [ ] **Step 1: Write failing test for `on_exception` tag injection**

Add to `project/tests.py`:

```python
class OnExceptionTagInjectionTest(TestCase):
    """Verify that on_exception injects tags into framework error responses."""

    def test_http_error_gets_status_code_in_body(self) -> None:
        """HttpError subclass responses should include status_code in the body."""
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn("status_code", data)
        self.assertEqual(data["status_code"], 401)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test project.tests.OnExceptionTagInjectionTest -v2`
Expected: FAIL — current handlers don't inject `status_code` for auth errors.

- [ ] **Step 3: Rewrite `TaggedErrorAPI` in `project/api.py`**

Replace the entire `TaggedErrorAPI` class and all 6 `@api.exception_handler` decorators. The new `project/api.py` should be:

```python
import json
import logging
from typing import override

from django.http import Http404, HttpRequest, HttpResponse
from ninja.errors import HttpError, ValidationError
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
        # Deduplicate required keys when extra_properties overrides a base key
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
        # Ninja's default Exception handler re-raises in production.
        # We replace it to return a tagged JSON 500 response.
        self.add_exception_handler(Exception, self._handle_exception)

    @override
    def on_exception(self, request: HttpRequest, exc: Exception) -> HttpResponse:  # pyright: ignore[reportIncompatibleMethodOverride]
        response = super().on_exception(request, exc)
        try:
            body = json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return response
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
    def get_openapi_schema(self, **kwargs) -> OpenAPISchema:  # pyright: ignore[reportAny]
        schema = super().get_openapi_schema(**kwargs)
        for path_methods in schema.get("paths", {}).values():
            for method_detail in path_methods.values():
                if not isinstance(method_detail, dict) or "responses" not in method_detail:
                    continue
                responses = method_detail["responses"]
                has_auth = method_detail.get("security")

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
```

- [ ] **Step 4: Update existing tests in `project/tests.py`**

Update `FrameworkErrorTagTest.test_validation_error_has_tag` (line 39-47):
- Change `self.assertIn("errors", data)` to `self.assertIsInstance(data["detail"], list)`

Update `OpenAPISchemaInjectionTest.test_validation_error_item_schema_includes_ctx` (line 103-111):
- Change `content["properties"]["errors"]["items"]` to `content["properties"]["detail"]["items"]`

- [ ] **Step 5: Run all project tests**

Run: `python manage.py test project -v2`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `python manage.py test -v2`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add project/api.py project/tests.py
git commit -m "refactor(api): replace exception handler decorators with TaggedErrorAPI overrides"
```

---

### Task 4: Update TypeScript client

**Files:**
- Modify: `client/src/ts-pattern/errors.ts`
- Modify: `client/src/ts-pattern/orders.ts`
- Regenerate: `client/src/generated/types.gen.ts`

- [ ] **Step 1: Regenerate OpenAPI schema and TypeScript types**

Run: `python manage.py export_openapi_schema --output client/openapi.json && cd client && bun run generate`

(If `generate` script doesn't exist, check `client/package.json` for the correct command to run `@hey-api/openapi-ts`.)

- [ ] **Step 2: Update `client/src/ts-pattern/errors.ts` doc comment**

Change line 10 from:
```typescript
 *   const fields = flattenValidationErrors<ExtractFields<OrdersApiListOrdersData>>(e.errors);
```
to:
```typescript
 *   const fields = flattenValidationErrors<ExtractFields<OrdersApiListOrdersData>>(e.detail);
```

- [ ] **Step 3: Update `client/src/ts-pattern/orders.ts` call site**

Change line 44 from:
```typescript
      >(e.errors);
```
to:
```typescript
      >(e.detail);
```

- [ ] **Step 4: Run client tests**

Run: `cd client && bun test`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add client/
git commit -m "refactor(client): update validation error access from e.errors to e.detail"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full backend test suite**

Run: `python manage.py test -v2`
Expected: All tests PASS

- [ ] **Step 2: Run client tests**

Run: `cd client && bun test`
Expected: All tests PASS

- [ ] **Step 3: Verify OpenAPI schema is correct**

Run: `python manage.py runserver` (or use test client) and check `/api/openapi.json`:
- Domain errors have `const` tags (e.g., `OrderNotFoundError`)
- Framework errors have `const` tags (e.g., `ValidationError`, `AuthenticationError`)
- Validation error schema has `detail` as array, not string

- [ ] **Step 4: Commit any remaining changes**

```bash
git status
# If there are unstaged changes, review and commit
```
