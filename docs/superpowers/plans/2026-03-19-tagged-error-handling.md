# Tagged Error Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify all error responses (domain and framework) behind a `tag` field so the frontend can discriminate errors exclusively via `ts-pattern`, and simplify the backend by removing per-error exception wrappers.

**Architecture:** Simplify `AppException` to wrap any `AppError` without a status code (all domain errors → 400). Replace individual exception handlers with one centralized handler that normalizes all exceptions (domain, validation, auth, 404, etc.) into tagged JSON. Override `get_openapi_schema()` on a custom `NinjaExtraAPI` subclass to inject framework error schemas into every endpoint.

**Tech Stack:** Django Ninja, ninja-extra, Pydantic v2 (RootModel), hey-api/openapi-ts, ts-pattern, bun

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `core/exceptions.py` | Simplify `AppException` — remove `status_code` |
| Modify | `core/tests.py` | Update `AppExceptionTest` for new signature |
| Delete | `orders/exceptions.py` | Per-error wrappers no longer needed |
| Modify | `orders/schemas.py` | Add `OrderErrors` RootModel |
| Modify | `orders/service.py` | `raise AppException(error)` directly |
| Modify | `orders/api.py` | 400 for domain errors, remove exception wrapper imports |
| Modify | `orders/tests.py` | Domain errors now return 400 (not 404/403) |
| Modify | `products/schemas.py` | Add `ProductErrors` RootModel |
| Modify | `products/api.py` | Replace inline dicts with `raise AppException(error)` |
| Modify | `products/tests.py` | Domain errors now return 400 (not 404/403) |
| Modify | `blog/schemas.py` | Add `PostErrors` RootModel |
| Modify | `blog/api.py` | Replace inline dicts with `raise AppException(error)` |
| Modify | `blog/tests.py` | Domain errors now return 400 (not 404/403) |
| Modify | `project/api.py` | Centralized exception handler + custom API subclass with OpenAPI injection |
| Modify | `project/tests.py` | Add tests for framework error responses (validation, auth, 404, 500) |
| Regenerate | `client/openapi.json` | Regenerated from new schema |
| Regenerate | `client/src/generated/types.gen.ts` | Regenerated — will include framework error types |
| Modify | `client/src/ts-pattern/orders.ts` | Add framework errors to examples |
| Modify | `client/src/ts-pattern/products.ts` | Add framework errors to examples |
| Modify | `client/src/ts-pattern/posts.ts` | Add framework errors to examples |

---

### Task 1: Simplify `AppException` and update existing handler

Remove the `status_code` parameter. All domain errors return HTTP 400. Also update the existing exception handler in `project/api.py` to use `status=400` so that subsequent tasks can run without breakage.

**Files:**
- Modify: `core/exceptions.py`
- Modify: `core/tests.py`
- Modify: `project/api.py` (single line change to keep handler working)

- [ ] **Step 1: Update `AppExceptionTest` for new signature**

```python
# core/tests.py — replace the AppExceptionTest class

class AppExceptionTest(TestCase):
    def test_stores_error(self) -> None:
        class TestError(AppError):
            pass

        error = TestError(detail="something went wrong")
        exc = AppException(error)
        self.assertIs(exc.error, error)
        self.assertEqual(error.tag, "TestError")

    def test_is_exception_subclass(self) -> None:
        class TestError(AppError):
            pass

        error = TestError(detail="something went wrong")
        exc = AppException(error)
        self.assertIsInstance(exc, Exception)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test core.tests.AppExceptionTest -v2`
Expected: FAIL — `AppException.__init__` still requires `status_code`

- [ ] **Step 3: Simplify `AppException`**

```python
# core/exceptions.py — full file

from core.schemas import AppError


class AppException(Exception):
    def __init__(self, error: AppError) -> None:
        super().__init__()
        self.error = error
```

- [ ] **Step 4: Run core tests to verify they pass**

Run: `.venv/bin/python manage.py test core -v2`
Expected: PASS for `AppExceptionTest`

- [ ] **Step 5: Update existing handler in `project/api.py`**

Change the one line in the existing `handle_app_exception` from `status=exc.status_code` to `status=400`:

```python
# project/api.py — change only this line in handle_app_exception
@api.exception_handler(AppException)
def handle_app_exception(request: HttpRequest, exc: AppException) -> HttpResponse:
    return api.create_response(request, exc.error.model_dump(), status=400)
```

- [ ] **Step 6: Run full test suite to verify nothing is broken**

Run: `.venv/bin/python manage.py test -v2`
Expected: Some order/product/blog detail tests will fail (they still expect 404/403 — this is expected, those tests get updated in Tasks 2-4). Core and list tests should pass.

- [ ] **Step 7: Commit**

```bash
git add core/exceptions.py core/tests.py project/api.py
git commit -m "refactor(core): simplify AppException — remove status_code, all domain errors return 400"
```

---

### Task 2: Delete per-error exception wrappers and update orders

Replace `OrderNotFound` / `OrderNotAccessible` exception subclasses with direct `raise AppException(error)`.

**Files:**
- Delete: `orders/exceptions.py`
- Modify: `orders/schemas.py`
- Modify: `orders/service.py`
- Modify: `orders/api.py`
- Modify: `orders/tests.py`

- [ ] **Step 1: Update order tests — domain errors now return 400**

In `orders/tests.py`, change `OrdersDetailAPITest`:

```python
# Change test_get_nonexistent_order_returns_404 → test_get_nonexistent_order_returns_400
def test_get_nonexistent_order_returns_400(self) -> None:
    response = self.client.get("/api/orders/99999/", HTTP_AUTHORIZATION=self.token)
    self.assertEqual(response.status_code, 400)
    data = response.json()
    self.assertEqual(data["tag"], "OrderNotFoundError")
    self.assertEqual(data["id"], 99999)

# Change test_get_draft_order_returns_403 → test_get_draft_order_returns_400
def test_get_draft_order_returns_400(self) -> None:
    response = self.client.get(f"/api/orders/{self.draft.pk}/", HTTP_AUTHORIZATION=self.token)
    self.assertEqual(response.status_code, 400)
    data = response.json()
    self.assertEqual(data["tag"], "OrderNotAccessibleError")
    self.assertEqual(data["id"], self.draft.pk)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test orders.tests.OrdersDetailAPITest -v2`
Expected: FAIL — still returning 404/403

- [ ] **Step 3: Add `OrderErrors` RootModel to schemas**

In `orders/schemas.py`, add after `OrderNotAccessibleError`:

```python
class OrderErrors(RootModel[OrderNotFoundError | OrderNotAccessibleError]):
    pass
```

- [ ] **Step 4: Update `orders/service.py` — raise `AppException` directly**

```python
# orders/service.py — full file

from core.exceptions import AppException
from orders.models import Order
from orders.schemas import (
    CancelledOrder,
    OrderFilters,
    OrderNotAccessibleError,
    OrderNotFoundError,
    PendingOrder,
    ShippedOrder,
)

OrderQueryResult = PendingOrder | ShippedOrder | CancelledOrder


def _to_schema(order: Order) -> OrderQueryResult:
    match order.status:
        case Order.Status.PENDING:
            return PendingOrder(
                id=order.pk,
                customer_name=order.customer_name,
                items_count=order.items_count,
                total_price=order.total_price,
                created_at=order.created_at,
            )
        case Order.Status.SHIPPED:
            return ShippedOrder(
                id=order.pk,
                customer_name=order.customer_name,
                items_count=order.items_count,
                total_price=order.total_price,
                tracking_number=order.tracking_number or "",
                shipped_at=order.shipped_at,  # pyright: ignore[reportArgumentType]
                created_at=order.created_at,
            )
        case Order.Status.CANCELLED:
            return CancelledOrder(
                id=order.pk,
                customer_name=order.customer_name,
                items_count=order.items_count,
                total_price=order.total_price,
                cancellation_reason=order.cancellation_reason or "",
                cancelled_at=order.cancelled_at,  # pyright: ignore[reportArgumentType]
                created_at=order.created_at,
            )
        case Order.Status.DRAFT | _:
            # DRAFT is excluded before _to_schema is called; this branch should never be reached
            raise ValueError(f"Unexpected order status in _to_schema: {order.status}")


def list_orders(filters: OrderFilters) -> list[OrderQueryResult]:
    # Draft orders are always excluded — they are an internal status not exposed to consumers.
    # list_orders never raises AppException: filters simply narrow results.
    qs = Order.objects.exclude(status=Order.Status.DRAFT)
    qs = filters.filter(qs)
    return [_to_schema(order) for order in qs]


def get_order(order_id: int) -> OrderQueryResult:
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        raise AppException(OrderNotFoundError(id=order_id, detail="Order not found"))

    if order.status == Order.Status.DRAFT:
        raise AppException(OrderNotAccessibleError(id=order_id, detail="Order not accessible"))

    return _to_schema(order)
```

- [ ] **Step 5: Update `orders/api.py` — use `OrderErrors` on 400**

```python
# orders/api.py — full file

from django.http import HttpRequest
from ninja import Query, Router
from ninja_jwt.authentication import JWTAuth

from orders import service
from orders.schemas import OrderErrors, OrderFilters, OrderResponse

router = Router(auth=JWTAuth())


@router.get("/", response=list[OrderResponse])
def list_orders(request: HttpRequest, filters: Query[OrderFilters]) -> list[OrderResponse]:
    return service.list_orders(filters)  # pyright: ignore[reportReturnType]


@router.get(
    "/{order_id}/",
    response={200: OrderResponse, 400: OrderErrors},
)
def get_order(request: HttpRequest, order_id: int) -> OrderResponse:
    # Errors are raised as AppException — caught by the global handler in project/api.py
    return service.get_order(order_id)  # pyright: ignore[reportReturnType]
```

- [ ] **Step 6: Delete `orders/exceptions.py`**

```bash
git rm orders/exceptions.py
```

- [ ] **Step 7: Run order tests**

Run: `.venv/bin/python manage.py test orders -v2`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add orders/
git commit -m "refactor(orders): use AppException directly, add OrderErrors RootModel, domain errors return 400"
```

---

### Task 3: Migrate products to `raise AppException`

Products currently returns inline dicts. Migrate to `raise AppException(error)`.

**Files:**
- Modify: `products/schemas.py`
- Modify: `products/api.py`
- Modify: `products/tests.py`

- [ ] **Step 1: Update product tests — domain errors now return 400**

In `products/tests.py`, change `ProductsDetailAPITest`:

```python
# Change test_get_hidden_product_returns_403 → test_get_hidden_product_returns_400
def test_get_hidden_product_returns_400(self) -> None:
    response = self.client.get(
        f"/api/products/{self.hidden.pk}/", HTTP_AUTHORIZATION=self.token
    )
    self.assertEqual(response.status_code, 400)
    data = response.json()
    self.assertEqual(data["tag"], "ProductHiddenError")
    self.assertEqual(data["id"], self.hidden.pk)

# Change test_get_nonexistent_product_returns_404 → test_get_nonexistent_product_returns_400
def test_get_nonexistent_product_returns_400(self) -> None:
    response = self.client.get("/api/products/99999/", HTTP_AUTHORIZATION=self.token)
    self.assertEqual(response.status_code, 400)
    data = response.json()
    self.assertEqual(data["tag"], "ProductNotFoundError")
    self.assertEqual(data["id"], 99999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test products.tests.ProductsDetailAPITest -v2`
Expected: FAIL — still returning 404/403

- [ ] **Step 3: Add `ProductErrors` RootModel to schemas**

In `products/schemas.py`, add after `ProductHiddenError`:

```python
class ProductErrors(RootModel[ProductNotFoundError | ProductHiddenError]):
    pass
```

- [ ] **Step 4: Update `products/api.py` — use `raise AppException`**

```python
# products/api.py — full file

from django.http import HttpRequest
from ninja import Router
from ninja_jwt.authentication import JWTAuth

from core.exceptions import AppException
from products.models import Product
from products.schemas import (
    ProductErrors,
    ProductHiddenError,
    ProductNotFoundError,
    ProductResponse,
)

router = Router(auth=JWTAuth())


@router.get("/", response=list[ProductResponse])
def list_products(request: HttpRequest) -> list[Product]:
    return list(Product.objects.exclude(status=Product.Status.HIDDEN))


@router.get(
    "/{product_id}/",
    response={200: ProductResponse, 400: ProductErrors},
)
def get_product(request: HttpRequest, product_id: int) -> Product:
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        raise AppException(ProductNotFoundError(id=product_id, detail=f"Product {product_id} not found"))

    if product.status == Product.Status.HIDDEN:
        raise AppException(ProductHiddenError(id=product_id, detail=f"Product {product_id} is not available"))

    return product
```

- [ ] **Step 5: Run product tests**

Run: `.venv/bin/python manage.py test products -v2`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add products/
git commit -m "refactor(products): use AppException, add ProductErrors RootModel, domain errors return 400"
```

---

### Task 4: Migrate blog to `raise AppException`

Blog currently returns inline dicts. Migrate to `raise AppException(error)`.

**Files:**
- Modify: `blog/schemas.py`
- Modify: `blog/api.py`
- Modify: `blog/tests.py`

- [ ] **Step 1: Update blog tests — domain errors now return 400**

In `blog/tests.py`, change `BlogDetailAPITest`:

```python
# Change test_get_nonexistent_post_returns_404 → test_get_nonexistent_post_returns_400
def test_get_nonexistent_post_returns_400(self) -> None:
    response = self.client.get("/api/blog/post/99999")
    self.assertEqual(response.status_code, 400)
    data = response.json()
    self.assertEqual(data["tag"], "PostNotFoundError")
    self.assertEqual(data["id"], 99999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test blog.tests.BlogDetailAPITest.test_get_nonexistent_post_returns_400 -v2`
Expected: FAIL — still returning 404

- [ ] **Step 3: Add `PostErrors` RootModel to schemas**

In `blog/schemas.py`, add after `PostNotFoundError`:

```python
class PostErrors(RootModel[PostNotFoundError]):
    pass
```

- [ ] **Step 4: Update `blog/api.py` — use `raise AppException`**

```python
# blog/api.py — full file

from django.http import HttpRequest
from ninja import Router

from blog.models import Post
from blog.schemas import PostErrors, PostNotFoundError, PostResponse
from core.exceptions import AppException

router = Router()


@router.get("/posts/", response=list[PostResponse])
def get_posts(request: HttpRequest):
    return Post.objects.all()


@router.get("/post/{post_id}", response={200: PostResponse, 400: PostErrors})
def get_post(request: HttpRequest, post_id: int):
    try:
        return 200, Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        raise AppException(PostNotFoundError(id=post_id, detail=f"Post with id {post_id} not found"))
```

- [ ] **Step 5: Run blog tests**

Run: `.venv/bin/python manage.py test blog -v2`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add blog/
git commit -m "refactor(blog): use AppException, add PostErrors RootModel, domain errors return 400"
```

---

### Task 5: Centralized exception handler

Replace the single `AppException` handler with a catch-all that normalizes all exception types into tagged JSON responses.

**Files:**
- Modify: `project/api.py`
- Modify: `project/tests.py`

- [ ] **Step 1: Write tests for framework error responses**

Add to `project/tests.py`:

```python
# project/tests.py — add these test classes after existing ones

class FrameworkErrorTagTest(TestCase):
    """Verify that framework exceptions produce tagged JSON responses."""

    def test_validation_error_has_tag(self) -> None:
        """Invalid query param triggers ninja ValidationError → tagged 422."""
        # orders list with invalid status value triggers validation error
        user = User.objects.create_user(username="fwuser", password="pass123!")
        token = f"Bearer {AccessToken.for_user(user)}"
        response = self.client.get("/api/orders/?status=bogus", HTTP_AUTHORIZATION=token)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertEqual(data["tag"], "ValidationError")
        self.assertIn("errors", data)

    def test_authentication_error_has_tag(self) -> None:
        """Missing auth on a protected endpoint → tagged 401."""
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertEqual(data["tag"], "AuthenticationError")

    def test_not_found_error_has_tag(self) -> None:
        """Request to a non-existent URL → tagged 404."""
        response = self.client.get("/api/nonexistent/")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["tag"], "NotFoundError")

    def test_domain_error_has_tag(self) -> None:
        """AppException → tagged 400."""
        user = User.objects.create_user(username="domuser", password="pass123!")
        token = f"Bearer {AccessToken.for_user(user)}"
        response = self.client.get("/api/orders/99999/", HTTP_AUTHORIZATION=token)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["tag"], "OrderNotFoundError")
```

Note: `HttpError` and `InternalError` (500 catch-all) handlers are implemented but not tested here because they're difficult to trigger through normal API endpoints. `HttpError` is raised by Django Ninja internals, and `InternalError` requires an unhandled exception. Both handlers are simple tag-wrapping — the risk of regression is low.

Note: add the necessary imports at the top of `project/tests.py`:

```python
from ninja_jwt.tokens import AccessToken
from orders.models import Order
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test project.tests.FrameworkErrorTagTest -v2`
Expected: FAIL — current handler only catches `AppException`, framework errors use ninja defaults (no `tag`)

- [ ] **Step 3: Implement centralized exception handler**

```python
# project/api.py — full file

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
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python manage.py test -v2`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add project/api.py project/tests.py
git commit -m "feat(project): centralized exception handler — all errors return tagged JSON"
```

---

### Task 6: OpenAPI schema injection for framework errors

Override `get_openapi_schema()` to inject framework error responses (ValidationError, AuthenticationError, etc.) into every endpoint's OpenAPI spec. This task modifies `project/api.py` as produced by Task 5.

**Files:**
- Modify: `project/api.py` (add `TaggedErrorAPI` subclass, replace `NinjaExtraAPI()` with `TaggedErrorAPI()`)

- [ ] **Step 1: Write test for OpenAPI schema injection**

Add to `project/tests.py`:

```python
class OpenAPISchemaInjectionTest(TestCase):
    """Verify that framework error schemas are injected into every endpoint."""

    def test_endpoint_has_validation_error_schema(self) -> None:
        """Every endpoint should have a 422 response with ValidationError schema."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        # Check a specific endpoint — get_order
        get_order_responses = schema["paths"]["/api/orders/{order_id}/"]["get"]["responses"]
        self.assertIn("422", get_order_responses)
        content = get_order_responses["422"]["content"]["application/json"]["schema"]
        # Should reference or inline a schema with tag = "ValidationError"
        self.assertIn("properties", content)
        self.assertEqual(content["properties"]["tag"]["const"], "ValidationError")

    def test_authenticated_endpoint_has_auth_error_schema(self) -> None:
        """Endpoints with auth should have 401 and 403 responses."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        get_order_responses = schema["paths"]["/api/orders/{order_id}/"]["get"]["responses"]
        self.assertIn("401", get_order_responses)
        self.assertIn("403", get_order_responses)

    def test_unauthenticated_endpoint_has_no_auth_error_schema(self) -> None:
        """Endpoints without auth should NOT have 401/403 responses."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        get_posts_responses = schema["paths"]["/api/blog/posts/"]["get"]["responses"]
        self.assertNotIn("401", get_posts_responses)
        self.assertNotIn("403", get_posts_responses)

    def test_every_endpoint_has_internal_error_schema(self) -> None:
        """Every endpoint should have a 500 response with InternalError schema."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        for path, methods in schema["paths"].items():
            for method, details in methods.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    self.assertIn(
                        "500",
                        details["responses"],
                        f"{method.upper()} {path} missing 500 response",
                    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test project.tests.OpenAPISchemaInjectionTest -v2`
Expected: FAIL — no 422/401/403/500 in current OpenAPI output

- [ ] **Step 3: Subclass `NinjaExtraAPI` with OpenAPI injection**

Replace the `api = NinjaExtraAPI()` line in `project/api.py` with a custom subclass. Add this class before the `api = ...` line:

```python
from typing import override
from ninja.openapi.schema import OpenAPISchema

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
                            "content": {"application/json": {"schema": _AUTHENTICATION_ERROR_SCHEMA}},
                        }
                    if "403" not in responses:
                        responses["403"] = {
                            "description": "Forbidden",
                            "content": {"application/json": {"schema": _AUTHORIZATION_ERROR_SCHEMA}},
                        }

        return schema
```

Then change `api = NinjaExtraAPI()` to `api = TaggedErrorAPI()`.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python manage.py test project -v2`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `.venv/bin/python manage.py test -v2`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add project/api.py project/tests.py
git commit -m "feat(project): inject framework error schemas into OpenAPI spec via TaggedErrorAPI"
```

---

### Task 7: Regenerate client types and update ts-pattern examples

Regenerate the OpenAPI schema and TypeScript types, then update the ts-pattern examples to include framework error handling.

**Files:**
- Regenerate: `client/openapi.json`
- Regenerate: `client/src/generated/`
- Modify: `client/src/ts-pattern/orders.ts`
- Modify: `client/src/ts-pattern/products.ts`
- Modify: `client/src/ts-pattern/posts.ts`

- [ ] **Step 1: Export the OpenAPI schema**

```bash
.venv/bin/python manage.py export_openapi_schema --output client/openapi.json
```

If the management command doesn't exist, fetch it from the running server:

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8000 &
sleep 2
curl -s http://localhost:8000/api/openapi.json | python3 -m json.tool > client/openapi.json
kill %1
```

- [ ] **Step 2: Verify the exported schema includes framework errors**

Spot-check `client/openapi.json` for `422`, `401`, `500` responses and `ValidationError`/`AuthenticationError`/`InternalError` schemas.

- [ ] **Step 3: Regenerate TypeScript types**

```bash
cd client && bun run openapi-ts && cd ..
```

- [ ] **Step 4: Verify generated types include framework error types**

Check `client/src/generated/types.gen.ts` for new types like `ValidationError`, `AuthenticationError`, `AuthorizationError`, `InternalError`.

- [ ] **Step 5: Update `client/src/ts-pattern/orders.ts`**

```typescript
// client/src/ts-pattern/orders.ts — full file

import { match } from "ts-pattern";
import type {
  CancelledOrder,
  OrderResponse,
  PendingOrder,
  ShippedOrder,
} from "../generated/types.gen";

// Import the generated error union type for get_order
import type { OrdersApiGetOrderError } from "../generated/types.gen";

function describeOrder(order: OrderResponse): string {
  return match(order)
    .with(
      { tag: "PendingOrder" },
      (o: PendingOrder) => `Order for ${o.customer_name} is pending`,
    )
    .with(
      { tag: "ShippedOrder" },
      (o: ShippedOrder) =>
        `Order for ${o.customer_name} shipped — tracking: ${o.tracking_number}`,
    )
    .with(
      { tag: "CancelledOrder" },
      (o: CancelledOrder) =>
        `Order for ${o.customer_name} cancelled — reason: ${o.cancellation_reason}`,
    )
    .exhaustive();
}

// All errors — domain and framework — discriminated by tag.
function describeError(error: OrdersApiGetOrderError): string {
  return match(error)
    .with(
      { tag: "OrderNotFoundError" },
      (e) => `Order ${e.id} not found`,
    )
    .with(
      { tag: "OrderNotAccessibleError" },
      (e) => `Order ${e.id} is not accessible`,
    )
    .with({ tag: "ValidationError" }, () => "Invalid request")
    .with({ tag: "AuthenticationError" }, () => "Please log in")
    .with({ tag: "AuthorizationError" }, () => "Access denied")
    .with({ tag: "InternalError" }, () => "Something went wrong")
    .exhaustive();
}

export { describeError, describeOrder };
```

Note: the exact shape of the generated error union type depends on what `@hey-api/openapi-ts` produces for the new schema. The implementer must check the actual generated type names and adjust imports accordingly. The pattern above is the target — the tag-based matching is what matters.

- [ ] **Step 6: Update `client/src/ts-pattern/products.ts`**

Follow the same pattern as orders: update `describeError` and `handleProductResponse` to include framework error tags. Use the generated error union type from `types.gen.ts`.

- [ ] **Step 7: Update `client/src/ts-pattern/posts.ts`**

Follow the same pattern: update `describeError` and `handlePostResult` to include framework error tags. Use the generated error union type from `types.gen.ts`.

- [ ] **Step 8: Verify TypeScript compiles**

```bash
cd client && bun run tsc --noEmit && cd ..
```

If there's no `tsconfig.json` or `tsc` isn't configured, at minimum verify the ts-pattern files have no import errors by running them through bun:

```bash
cd client && bun build src/ts-pattern/orders.ts src/ts-pattern/products.ts src/ts-pattern/posts.ts --no-bundle && cd ..
```

- [ ] **Step 9: Commit**

```bash
git add client/
git commit -m "refactor(client): regenerate types and update ts-pattern for tagged error handling"
```

---

### Task 8: Final verification

Run the full test suite and verify everything works end to end.

- [ ] **Step 1: Run full backend test suite**

Run: `.venv/bin/python manage.py test -v2`
Expected: ALL PASS

- [ ] **Step 2: Run linter and type checker**

```bash
.venv/bin/ruff check .
.venv/bin/basedpyright
```

Expected: No errors (or only pre-existing ones)

- [ ] **Step 3: Verify OpenAPI schema manually**

```bash
.venv/bin/python -c "
import django; import os; os.environ['DJANGO_SETTINGS_MODULE']='project.settings'; django.setup()
from project.api import api
schema = api.get_openapi_schema()
import json; print(json.dumps(dict(schema), indent=2)[:2000])
"
```

Spot-check that endpoints have 400 (domain errors), 422, 401/403 (if auth), and 500 responses.

- [ ] **Step 4: Commit any final fixes if needed**
