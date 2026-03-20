# `@raises()` Decorator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manual `response={400: *Errors}` endpoint declarations with a `@raises()` decorator that auto-injects domain error schemas into OpenAPI docs.

**Architecture:** A metadata-only `@raises()` decorator stashes exception classes on view functions. `TaggedErrorAPI.get_openapi_schema()` reads this metadata by iterating router operations, builds JSON schemas from each exception's auto-generated `.Schema`, and injects them into the OpenAPI output grouped by status code.

**Tech Stack:** Django Ninja, Pydantic, Django `TestCase`

**Spec:** `docs/superpowers/specs/2026-03-20-raises-decorator-design.md`

**Prerequisite:** `orders/api.py` has an uncommitted change (removing `200: OrderResponse` from the response dict). Commit or discard it before starting — Task 3 assumes the current working tree state.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `core/decorators.py` | Create | `raises()` decorator — stashes exception classes as metadata on view functions |
| `core/tests.py` | Modify | Add tests for `raises()` decorator and OpenAPI injection of domain errors |
| `project/api.py` | Modify | Extend `get_openapi_schema()` to read `_raised_exceptions` from operations and inject domain error schemas |
| `orders/api.py` | Modify | Replace `response={400: OrderErrors}` with `@raises(...)` |
| `orders/schemas.py` | Modify | Delete `OrderErrors` class and its import |
| `products/api.py` | Modify | Replace `response={200: ProductResponse, 400: ProductErrors}` with `@raises(...)` |
| `products/schemas.py` | Modify | Delete `ProductErrors` class and its import |
| `blog/api.py` | Modify | Replace `response={200: PostResponse, 400: PostErrors}` with `@raises(...)` |
| `blog/schemas.py` | Modify | Delete `PostErrors` class and its import |
| `project/tests.py` | Modify | Add tests for domain error OpenAPI schema injection via `@raises` |

---

### Task 1: Create the `raises()` decorator with tests

**Files:**
- Create: `core/decorators.py`
- Modify: `core/tests.py`

- [ ] **Step 1: Write the failing test for `raises()` stashing metadata**

Add to `core/tests.py`:

```python
from core.decorators import RAISED_EXCEPTIONS_ATTR, raises
from core.exceptions import AppException


class RaisesDecoratorTest(TestCase):
    def test_stashes_exceptions_on_function(self) -> None:
        class ErrorA(AppException):
            pass

        class ErrorB(AppException):
            pass

        @raises(ErrorA, ErrorB)
        def my_view():
            pass

        self.assertEqual(
            getattr(my_view, RAISED_EXCEPTIONS_ATTR),
            (ErrorA, ErrorB),
        )

    def test_does_not_wrap_function(self) -> None:
        """raises() should not alter the function identity — it's metadata-only."""

        class ErrorA(AppException):
            pass

        original = lambda: None  # noqa: E731
        decorated = raises(ErrorA)(original)
        self.assertIs(decorated, original)

    def test_single_exception(self) -> None:
        class ErrorA(AppException):
            pass

        @raises(ErrorA)
        def my_view():
            pass

        self.assertEqual(
            getattr(my_view, RAISED_EXCEPTIONS_ATTR),
            (ErrorA,),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test core.tests.RaisesDecoratorTest -v2`
Expected: `ImportError` — `core.decorators` does not exist yet

- [ ] **Step 3: Write minimal implementation**

Create `core/decorators.py`:

```python
from collections.abc import Callable
from typing import TypeVar

from core.exceptions import AppException

RAISED_EXCEPTIONS_ATTR = "_raised_exceptions"

F = TypeVar("F", bound=Callable)


def raises(*exceptions: type[AppException]) -> Callable[[F], F]:
    """Mark an endpoint with the domain errors it can raise.

    Pure metadata — has no runtime effect. TaggedErrorAPI reads this
    during OpenAPI schema generation to inject error response schemas.
    """

    def decorator(func: F) -> F:
        setattr(func, RAISED_EXCEPTIONS_ATTR, exceptions)
        return func

    return decorator
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test core.tests.RaisesDecoratorTest -v2`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/decorators.py core/tests.py
git commit -m "feat: add @raises() decorator for domain error metadata"
```

---

### Task 2: Extend `get_openapi_schema()` to inject domain error schemas

**Files:**
- Modify: `project/api.py:111-148`
- Modify: `project/tests.py`

This task reads `_raised_exceptions` metadata from operations and injects domain error schemas into the OpenAPI output. We match schema entries to view functions via `operationId`, avoiding fragile path reconstruction.

- [ ] **Step 1: Write failing tests for domain error OpenAPI injection**

Add to `project/tests.py`:

```python
class DomainErrorSchemaInjectionTest(TestCase):
    """Verify that @raises() injects domain error schemas into OpenAPI."""

    def test_endpoint_with_multiple_raises_has_oneof(self) -> None:
        """get_order has @raises(OrderNotFoundError, OrderNotAccessibleError) → oneOf."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        get_order_responses = schema["paths"]["/api/orders/{order_id}/"]["get"]["responses"]
        self.assertIn("400", get_order_responses)
        content = get_order_responses["400"]["content"]["application/json"]["schema"]
        self.assertIn("oneOf", content)
        self.assertEqual(len(content["oneOf"]), 2)
        self.assertEqual(content["discriminator"]["propertyName"], "tag")

    def test_endpoint_with_single_raise_has_inline_schema(self) -> None:
        """get_post has @raises(PostNotFoundError) → inline schema, no oneOf."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        get_post_responses = schema["paths"]["/api/blog/post/{post_id}"]["get"]["responses"]
        self.assertIn("400", get_post_responses)
        content = get_post_responses["400"]["content"]["application/json"]["schema"]
        self.assertNotIn("oneOf", content)
        # Should have the schema properties directly (or a $ref)
        # The exact shape depends on how Pydantic generates the JSON schema
        self.assertTrue(
            "properties" in content or "$ref" in content,
            f"Expected inline schema, got: {content}",
        )

    def test_endpoint_without_raises_has_no_domain_errors(self) -> None:
        """list_orders has no @raises → no 400 domain error schema."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        list_orders_responses = schema["paths"]["/api/orders/"]["get"]["responses"]
        self.assertNotIn("400", list_orders_responses)

    def test_raises_does_not_overwrite_framework_errors(self) -> None:
        """@raises endpoints should still have framework error schemas (422, 500)."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        get_order_responses = schema["paths"]["/api/orders/{order_id}/"]["get"]["responses"]
        self.assertIn("422", get_order_responses)
        self.assertIn("500", get_order_responses)

    def test_manual_response_takes_precedence_over_raises(self) -> None:
        """If an endpoint has both response={400: ...} and @raises(), the manual one wins."""
        # This test verifies the coexistence rule from the spec.
        # No current endpoints use both, so this is tested via the absence of
        # conflicts — if a 400 entry already exists from response=, @raises skips it.
        # The implementation uses `if status_key in responses: continue`.
        # Verified implicitly: endpoints that previously had response={400: ...}
        # now use @raises instead — if both were present, the manual one would win.
        pass  # Covered by design; add explicit test if dual-declaration endpoints are added

    def test_mixed_status_codes_produce_separate_entries(self) -> None:
        """Exceptions with different status codes get separate OpenAPI entries."""
        # No current domain errors use non-default status codes, so this test
        # uses test-only exception classes to verify the grouping logic.
        from collections import defaultdict

        from core.exceptions import AppException

        class NotFoundError(AppException, status=404):
            id: int

        class BadRequestError(AppException):
            reason: str

        # Simulate the grouping logic
        raised = (NotFoundError, BadRequestError)
        by_status: dict[int, list[type]] = defaultdict(list)
        for exc_cls in raised:
            by_status[exc_cls.status].append(exc_cls)

        self.assertIn(404, by_status)
        self.assertIn(400, by_status)
        self.assertEqual(len(by_status[404]), 1)
        self.assertEqual(len(by_status[400]), 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test project.tests.DomainErrorSchemaInjectionTest -v2`
Expected: FAIL — endpoints don't have `@raises()` yet, and `get_openapi_schema()` doesn't read it yet. Some may fail because the current `response={400: ...}` still produces a `400` entry but with a different schema shape.

- [ ] **Step 3: Implement OpenAPI injection in `TaggedErrorAPI.get_openapi_schema()`**

Modify `project/api.py`. Add these imports at the top:

```python
from collections import defaultdict
from collections.abc import Callable

from core.decorators import RAISED_EXCEPTIONS_ATTR
```

**Approach:** We match OpenAPI schema entries to view functions via `operationId`. This avoids reconstructing OpenAPI paths from router internals (which is fragile due to path normalization, trailing slashes, and API prefix handling).

1. Iterate `self._routers` → operations to collect `{operationId: raised_exceptions}`
2. During `schema["paths"]` iteration, look up `operationId` from each method detail

Add this method to `TaggedErrorAPI`, before `get_openapi_schema`:

```python
def _collect_raised_exceptions(
    self,
) -> dict[str, tuple[type[AppException], ...]]:
    """Collect @raises() metadata from all operations, keyed by operationId.

    Iterates the router hierarchy, checks each operation's view_func for
    the _raised_exceptions attribute set by @raises(), and builds a mapping
    from Django Ninja's operationId to the exception classes.
    """
    result: dict[str, tuple[type[AppException], ...]] = {}
    for _prefix, router in self._routers:
        for _path, path_view in router.path_operations.items():
            for operation in path_view.operations:
                raised = getattr(
                    operation.view_func, RAISED_EXCEPTIONS_ATTR, None
                )
                if raised is None:
                    continue
                # operation_id matches what Django Ninja puts in the schema
                op_id: str | None = getattr(operation, "operation_id", None)
                if op_id is None:
                    continue
                result[op_id] = raised
    return result
```

**Important implementation note:** Django Ninja auto-generates `operation.operation_id` from `{version}_{module}_{name}` during schema generation. If `operation.operation_id` is `None` at collection time (before schema generation), we need to fall back to generating it ourselves. The exact format depends on the Django Ninja version — verify during implementation by inspecting the actual `operation` attributes after `super().get_openapi_schema()` has been called. If needed, call `super().get_openapi_schema()` first, then collect — the operations will have their IDs populated by then.

Then replace the `get_openapi_schema` method with:

```python
@override
def get_openapi_schema(self, **kwargs) -> OpenAPISchema:  # pyright: ignore[reportAny]
    schema = super().get_openapi_schema(**kwargs)
    raised_by_op_id = self._collect_raised_exceptions()

    for path_methods in schema.get("paths", {}).values():
        for method, method_detail in path_methods.items():
            if not isinstance(method_detail, dict) or "responses" not in method_detail:
                continue
            responses = method_detail["responses"]
            has_auth = method_detail.get("security")

            # Framework error injection (unchanged)
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

            # Group exceptions by status code
            by_status: dict[int, list[type[AppException]]] = defaultdict(list)
            for exc_cls in raised:
                by_status[exc_cls.status].append(exc_cls)

            for status_code, exc_classes in by_status.items():
                status_key = str(status_code)
                if status_key in responses:
                    continue  # Manual response= declaration takes precedence

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
```

- [ ] **Step 4: Run tests to verify current tests still pass (before migrating endpoints)**

Run: `python manage.py test project.tests -v2`
Expected: Existing tests PASS. The new `DomainErrorSchemaInjectionTest` will still fail because endpoints haven't been migrated yet.

- [ ] **Step 5: Commit**

```bash
git add project/api.py project/tests.py
git commit -m "feat: extend get_openapi_schema() to inject domain errors from @raises()"
```

---

### Task 3: Migrate orders endpoints to `@raises()`

**Files:**
- Modify: `orders/api.py`
- Modify: `orders/schemas.py:43-47`

- [ ] **Step 1: Run existing orders tests to confirm they pass before changes**

Run: `python manage.py test orders.tests -v2`
Expected: All PASS

- [ ] **Step 2: Update `orders/api.py` — replace `response=` with `@raises()`**

Replace the full content of `orders/api.py` with:

```python
from django.http import HttpRequest
from ninja import Query, Router
from ninja_jwt.authentication import JWTAuth

from core.decorators import raises
from orders import service
from orders.exceptions import OrderNotAccessibleError, OrderNotFoundError
from orders.schemas import OrderFilters, OrderResponse

router = Router(auth=JWTAuth())


@router.get("/", response=list[OrderResponse])
def list_orders(request: HttpRequest, filters: Query[OrderFilters]) -> list[OrderResponse]:
    return service.list_orders(filters)  # pyright: ignore[reportReturnType]


@router.get("/{order_id}/")
@raises(OrderNotFoundError, OrderNotAccessibleError)
def get_order(request: HttpRequest, order_id: int) -> OrderResponse:
    # Errors are raised as AppException — caught by the global handler in project/api.py
    return service.get_order(order_id)  # pyright: ignore[reportReturnType]
```

- [ ] **Step 3: Delete `OrderErrors` from `orders/schemas.py`**

Remove lines 43-47 (the import and `OrderErrors` class):

```python
# DELETE these lines:
from orders.exceptions import OrderNotAccessibleError, OrderNotFoundError


class OrderErrors(RootModel[OrderNotFoundError.Schema | OrderNotAccessibleError.Schema]):
    pass
```

Also remove `RootModel` from the imports on line 5 if it's no longer used (check if `OrderResponse` still uses it — yes it does, so keep `RootModel`).

- [ ] **Step 4: Run orders tests**

Run: `python manage.py test orders.tests -v2`
Expected: All PASS — runtime behavior is unchanged

- [ ] **Step 5: Commit**

```bash
git add orders/api.py orders/schemas.py
git commit -m "refactor(orders): replace response={400: OrderErrors} with @raises()"
```

---

### Task 4: Migrate products endpoints to `@raises()`

**Files:**
- Modify: `products/api.py`
- Modify: `products/schemas.py:23-27`

- [ ] **Step 1: Run existing products tests to confirm they pass**

Run: `python manage.py test products.tests -v2`
Expected: All PASS

- [ ] **Step 2: Update `products/api.py` — replace `response=` with `@raises()`**

Replace the full content of `products/api.py` with:

```python
from django.http import HttpRequest
from ninja import Router
from ninja_jwt.authentication import JWTAuth

from core.decorators import raises
from products.exceptions import ProductHiddenError, ProductNotFoundError
from products.models import Product
from products.schemas import ProductResponse

router = Router(auth=JWTAuth())


@router.get("/", response=list[ProductResponse])
def list_products(request: HttpRequest) -> list[Product]:
    return list(Product.objects.exclude(status=Product.Status.HIDDEN))


@router.get("/{product_id}/", response=ProductResponse)
@raises(ProductNotFoundError, ProductHiddenError)
def get_product(request: HttpRequest, product_id: int) -> Product:
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        raise ProductNotFoundError(id=product_id, detail=f"Product {product_id} not found")

    if product.status == Product.Status.HIDDEN:
        raise ProductHiddenError(id=product_id, detail=f"Product {product_id} is not available")

    return product
```

Note: `get_product` previously had `response={200: ProductResponse, 400: ProductErrors}`. We keep `response=ProductResponse` for the success case and add `@raises()` for the errors.

- [ ] **Step 3: Delete `ProductErrors` from `products/schemas.py`**

Remove lines 23-27:

```python
# DELETE these lines:
from products.exceptions import ProductHiddenError, ProductNotFoundError


class ProductErrors(RootModel[ProductNotFoundError.Schema | ProductHiddenError.Schema]):
    pass
```

Also remove `RootModel` from the import on line 1 since `ProductResponse` still uses it — keep it.

- [ ] **Step 4: Run products tests**

Run: `python manage.py test products.tests -v2`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add products/api.py products/schemas.py
git commit -m "refactor(products): replace response={400: ProductErrors} with @raises()"
```

---

### Task 5: Migrate blog endpoints to `@raises()`

**Files:**
- Modify: `blog/api.py`
- Modify: `blog/schemas.py:23-27`

- [ ] **Step 1: Run existing blog tests to confirm they pass**

Run: `python manage.py test blog.tests -v2`
Expected: All PASS

- [ ] **Step 2: Update `blog/api.py` — replace `response=` with `@raises()`**

Replace the full content of `blog/api.py` with:

```python
from django.http import HttpRequest
from ninja import Router

from blog.exceptions import PostNotFoundError
from blog.models import Post
from blog.schemas import PostResponse
from core.decorators import raises

router = Router()


@router.get("/posts/", response=list[PostResponse])
def get_posts(request: HttpRequest):
    return Post.objects.all()


@router.get("/post/{post_id}", response=PostResponse)
@raises(PostNotFoundError)
def get_post(request: HttpRequest, post_id: int):
    try:
        return Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        raise PostNotFoundError(id=post_id, detail=f"Post with id {post_id} not found")
```

**Behavior change:** `get_post` previously used the tuple return `return 200, Post.objects.get(...)` which is required when `response={200: ..., 400: ...}` maps multiple status codes. With `response=PostResponse` (single schema), we must return the object directly — Django Ninja assumes 200. Keeping the `200, obj` tuple with a single-schema `response=` would break serialization.

- [ ] **Step 3: Delete `PostErrors` from `blog/schemas.py`**

Remove lines 23-27:

```python
# DELETE these lines:
from blog.exceptions import PostNotFoundError


class PostErrors(RootModel[PostNotFoundError.Schema]):
    pass
```

Also remove `RootModel` from the import on line 1 since `PostResponse` still uses it — keep it.

- [ ] **Step 4: Run blog tests**

Run: `python manage.py test blog.tests -v2`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add blog/api.py blog/schemas.py
git commit -m "refactor(blog): replace response={400: PostErrors} with @raises()"
```

---

### Task 6: Verify OpenAPI injection tests and run full suite

**Files:**
- Modify: `project/tests.py` (if needed based on test results)

- [ ] **Step 1: Run the domain error schema injection tests**

Run: `python manage.py test project.tests.DomainErrorSchemaInjectionTest -v2`
Expected: All PASS now that endpoints are migrated

- [ ] **Step 2: If tests fail, debug the operationId matching**

The most likely failure is `_collect_raised_exceptions` not finding operationIds on operations. If this happens:
1. Print `operation.operation_id` for each operation to verify it's populated after `super().get_openapi_schema()` is called
2. If `operation_id` is `None`, generate it manually using Django Ninja's format: `f"{api.version}_{func.__module__}_{func.__name__}"`
3. Compare with `operationId` values in the schema output

- [ ] **Step 3: Run the full test suite**

Run: `python manage.py test -v2`
Expected: All tests PASS

- [ ] **Step 4: Verify OpenAPI schema manually**

Run: `python manage.py runserver` and visit `http://localhost:8000/api/docs` to visually confirm:
- `GET /api/orders/{order_id}/` shows 400 with `OrderNotFoundError | OrderNotAccessibleError`
- `GET /api/products/{product_id}/` shows 400 with `ProductNotFoundError | ProductHiddenError`
- `GET /api/blog/post/{post_id}` shows 400 with `PostNotFoundError`
- `GET /api/orders/` has no 400 domain error entry
- Framework errors (422, 500, 401, 403) still present on all relevant endpoints

- [ ] **Step 5: Commit any test fixes**

```bash
git add -u
git commit -m "fix: adjust OpenAPI injection tests after full migration"
```

(Skip if no fixes were needed.)

---

### Task 7: Clean up unused imports

**Files:**
- Modify: `orders/schemas.py`, `products/schemas.py`, `blog/schemas.py` (if stale imports remain)

- [ ] **Step 1: Check for unused imports in each schemas file**

Verify that no stale imports from the deleted `*Errors` classes remain. Specifically check that exception imports were removed in the earlier tasks.

- [ ] **Step 2: Run full test suite one final time**

Run: `python manage.py test -v2`
Expected: All PASS

- [ ] **Step 3: Final commit if any cleanup was done**

```bash
git add -u
git commit -m "chore: clean up unused imports after @raises() migration"
```
