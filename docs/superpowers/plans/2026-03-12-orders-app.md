# Orders App Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a new `orders` Django app demonstrating the `api → service → model` layered architecture with polymorphic response types, query param filtering, typed errors, and global exception handling.

**Architecture:** Service layer returns Pydantic schema instances directly (schemas serve as both service contract and API serialization). A global `AppException` handler in `project/api.py` eliminates try/except from individual endpoints. Draft orders exist in the DB but are inaccessible via the API — demonstrating model status ≠ API-visible state.

**Spec:** `docs/superpowers/specs/2026-03-12-orders-app-design.md`

**Tech Stack:** Django 6, Django Ninja, ninja_extra (NinjaExtraAPI), ninja_jwt, Pydantic v2, FilterSchema, RootModel

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `core/exceptions.py` | Create | `AppException` base — carries status code + error schema |
| `core/tests.py` | Create | Unit tests for `AppException` |
| `project/api.py` | Modify | Register global `AppException` handler + orders router |
| `project/settings.py` | Modify | Add `orders.apps.OrdersConfig` to `INSTALLED_APPS` |
| `orders/__init__.py` | Create | App package |
| `orders/apps.py` | Create | `OrdersConfig` |
| `orders/models.py` | Create | `Order` Django model with Status choices |
| `orders/migrations/` | Generate | `python manage.py makemigrations orders` |
| `orders/schemas.py` | Create | Pydantic schemas (service types + API serialization) + `OrderFilters` |
| `orders/exceptions.py` | Create | `OrderNotFound`, `OrderNotAccessible` |
| `orders/service.py` | Create | Business logic; returns schema instances, raises domain exceptions |
| `orders/api.py` | Create | Thin router; two endpoints, no try/except |
| `orders/tests.py` | Create | Model unit tests + API integration tests |

---

## Chunk 1: Core Infrastructure and Orders App Scaffold

### Task 1: AppException infrastructure

**Files:**
- Create: `core/exceptions.py`
- Create: `core/tests.py`
- Modify: `project/api.py`

- [ ] **Step 1: Write a failing test for AppException**

Create `core/tests.py`:

```python
from django.test import TestCase

from core.exceptions import AppException
from core.schemas import AppError


class AppExceptionTest(TestCase):
    def test_stores_status_code_and_error(self) -> None:
        error = AppError(tag="test_error", detail="something went wrong")
        exc = AppException(404, error)
        self.assertEqual(exc.status_code, 404)
        self.assertIs(exc.error, error)

    def test_is_exception_subclass(self) -> None:
        error = AppError(tag="test_error", detail="something went wrong")
        exc = AppException(500, error)
        self.assertIsInstance(exc, Exception)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run python manage.py test core
```

Expected: `ModuleNotFoundError: No module named 'core.exceptions'`

- [ ] **Step 3: Create `core/exceptions.py`**

```python
from core.schemas import AppError


class AppException(Exception):
    def __init__(self, status_code: int, error: AppError) -> None:
        self.status_code = status_code
        self.error = error
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
uv run python manage.py test core
```

Expected: 2 tests pass.

- [ ] **Step 5: Register global handler in `project/api.py`**

The orders integration tests (Task 4) will verify the handler end-to-end. Replace the file contents. **Note:** this file will be updated again in Task 6 to add the orders router import — don't skip that step.

```python
from django.http import HttpRequest, HttpResponse
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController

from blog.api import router as blog_router
from core.exceptions import AppException
from products.api import router as products_router

api = NinjaExtraAPI()
api.register_controllers(NinjaJWTDefaultController)  # pyright: ignore[reportUnknownMemberType]


@api.exception_handler(AppException)
def handle_app_exception(request: HttpRequest, exc: AppException) -> HttpResponse:
    return api.create_response(request, exc.error.model_dump(), status=exc.status_code)


api.add_router("/blog", blog_router)
api.add_router("/products", products_router)
```

- [ ] **Step 6: Run all tests to confirm nothing is broken**

```bash
uv run python manage.py test
```

Expected: all existing tests + 2 new `core` tests pass.

- [ ] **Step 7: Commit**

```bash
git add core/exceptions.py core/tests.py project/api.py
git commit -m "feat: add AppException infrastructure and global handler"
```

---

### Task 2: Orders app scaffold, model, and migration

**Files:**
- Create: `orders/__init__.py`, `orders/apps.py`, `orders/models.py`, `orders/tests.py` (model tests only)
- Generate: `orders/migrations/0001_initial.py`
- Modify: `project/settings.py`

- [ ] **Step 1: Write failing model tests**

Create `orders/tests.py` with model-level tests only (API tests come in Task 4):

```python
from typing import override

from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja_jwt.tokens import AccessToken

from orders.models import Order

User = get_user_model()


class OrderModelTest(TestCase):
    def test_default_status_is_pending(self) -> None:
        order = Order(customer_name="Alice", total_price="50.00", items_count=2)
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_str_representation(self) -> None:
        order = Order(pk=1, customer_name="Alice", total_price="50.00", items_count=2, status=Order.Status.PENDING)
        self.assertEqual(str(order), "Order 1 (pending)")

    def test_status_choices_are_complete(self) -> None:
        statuses = {s.value for s in Order.Status}
        self.assertEqual(statuses, {"draft", "pending", "shipped", "cancelled"})
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run python manage.py test orders
```

Expected: `ModuleNotFoundError: No module named 'orders'`

- [ ] **Step 3: Create the app package files**

Create `orders/__init__.py` — empty file.

Create `orders/apps.py`:
```python
from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"
```

- [ ] **Step 4: Create `orders/models.py`**

All optional fields (`tracking_number`, `shipped_at`, `cancellation_reason`, `cancelled_at`) are `null=True, blank=True` — this is required because a pending order has no shipping or cancellation data. The integration tests in Task 4 depend on this.

```python
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        PENDING = "pending"
        SHIPPED = "shipped"
        CANCELLED = "cancelled"

    customer_name = models.CharField(max_length=255)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    items_count = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    tracking_number = models.CharField(max_length=100, null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Order {self.pk} ({self.status})"
```

- [ ] **Step 5: Register the app in `project/settings.py`**

Add `"orders.apps.OrdersConfig"` after `"products.apps.ProductsConfig"` in `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ninja",
    "ninja_extra",
    "ninja_jwt",
    "blog.apps.BlogConfig",
    "products.apps.ProductsConfig",
    "orders.apps.OrdersConfig",
]
```

- [ ] **Step 6: Generate and apply migration**

```bash
uv run python manage.py makemigrations orders
uv run python manage.py migrate
```

Expected: `orders/migrations/0001_initial.py` created and applied.

- [ ] **Step 7: Run model tests to confirm they pass**

```bash
uv run python manage.py test orders
```

Expected: 3 model tests pass.

- [ ] **Step 8: Run all tests to confirm nothing broken**

```bash
uv run python manage.py test
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git status
git add orders/__init__.py orders/apps.py orders/models.py orders/migrations/ orders/tests.py project/settings.py
git commit -m "feat: scaffold orders app with Order model"
```

---

## Chunk 2: Schemas, Exceptions, and Tests

### Task 3: Orders schemas and exceptions

**Files:**
- Create: `orders/schemas.py`
- Create: `orders/exceptions.py`

- [ ] **Step 1: Create `orders/schemas.py`**

```python
from datetime import datetime
from decimal import Decimal
from typing import Literal

from ninja.schema import FilterSchema
from pydantic import Field, RootModel

from core.schemas import AppError, TaggedSchema
from orders.models import Order


class PendingOrderSchema(TaggedSchema):
    tag: Literal["pending"] = "pending"
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    created_at: datetime


class ShippedOrderSchema(TaggedSchema):
    tag: Literal["shipped"] = "shipped"
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    tracking_number: str
    shipped_at: datetime
    created_at: datetime


class CancelledOrderSchema(TaggedSchema):
    tag: Literal["cancelled"] = "cancelled"
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    cancellation_reason: str
    cancelled_at: datetime
    created_at: datetime


class OrderResult(RootModel[PendingOrderSchema | ShippedOrderSchema | CancelledOrderSchema]):
    pass


class OrderNotFoundError(AppError):
    tag: Literal["order_not_found"] = "order_not_found"
    id: int


class OrderNotAccessibleError(AppError):
    tag: Literal["order_not_accessible"] = "order_not_accessible"
    id: int


class OrderFilters(FilterSchema):
    status: Order.Status | None = None
    q: str | None = Field(None, q=["customer_name__icontains"])
    min_total: Decimal | None = Field(None, q="total_price__gte")
    max_total: Decimal | None = Field(None, q="total_price__lte")
```

Note on `OrderFilters.status`: no `q=` annotation is needed — `FilterSchema` generates `status=<value>` (exact match) automatically for fields without it.

- [ ] **Step 2: Create `orders/exceptions.py`**

```python
from core.exceptions import AppException
from orders.schemas import OrderNotAccessibleError, OrderNotFoundError


class OrderNotFound(AppException):
    def __init__(self, order_id: int) -> None:
        super().__init__(404, OrderNotFoundError(id=order_id, detail="Order not found"))


class OrderNotAccessible(AppException):
    def __init__(self, order_id: int) -> None:
        super().__init__(
            403, OrderNotAccessibleError(id=order_id, detail="Order not accessible")
        )
```

- [ ] **Step 3: Run tests (smoke check — no import errors)**

```bash
uv run python manage.py test
```

Expected: all existing tests pass with no import errors.

- [ ] **Step 4: Commit**

```bash
git add orders/schemas.py orders/exceptions.py
git commit -m "feat: add orders schemas and exceptions"
```

---

### Task 4: Write API integration tests (TDD red phase)

**Files:**
- Modify: `orders/tests.py` (add API test classes)

Tests hit the HTTP API end-to-end. They will fail until the service and router are wired up in Tasks 5 and 6.

Note: `shipped_at` and `cancelled_at` are passed as ISO string values — Django's ORM accepts ISO strings for `DateTimeField` when saving to the database. The project runs Python 3.13, so `from typing import override` and `@override` on `setUp` are valid.

- [ ] **Step 1: Add API test classes to `orders/tests.py`**

Append to the existing `orders/tests.py` (after `OrderModelTest`):

```python
def _create_order(
    customer_name: str,
    status: Order.Status,
    total_price: str = "100.00",
    items_count: int = 2,
    tracking_number: str | None = None,
    shipped_at: str | None = None,
    cancellation_reason: str | None = None,
    cancelled_at: str | None = None,
) -> Order:
    return Order.objects.create(
        customer_name=customer_name,
        status=status,
        total_price=total_price,
        items_count=items_count,
        tracking_number=tracking_number,
        shipped_at=shipped_at,
        cancellation_reason=cancellation_reason,
        cancelled_at=cancelled_at,
    )


class OrdersListAPITest(TestCase):
    token: str  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        user = User.objects.create_user(username="listuser", password="pass123!")
        self.token = f"Bearer {AccessToken.for_user(user)}"

        _create_order("Alice", Order.Status.PENDING, total_price="50.00")
        _create_order(
            "Bob",
            Order.Status.SHIPPED,
            total_price="200.00",
            tracking_number="TRACK123",
            shipped_at="2026-01-01T10:00:00Z",
        )
        _create_order(
            "Charlie",
            Order.Status.CANCELLED,
            total_price="75.00",
            cancellation_reason="Changed mind",
            cancelled_at="2026-01-02T10:00:00Z",
        )
        _create_order("DraftUser", Order.Status.DRAFT, total_price="999.00")

    def test_list_requires_auth(self) -> None:
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 401)

    def test_list_returns_non_draft_orders(self) -> None:
        response = self.client.get("/api/orders/", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 3)
        names = {o["customer_name"] for o in data}
        self.assertEqual(names, {"Alice", "Bob", "Charlie"})

    def test_list_pending_order_has_correct_tag(self) -> None:
        response = self.client.get("/api/orders/", HTTP_AUTHORIZATION=self.token)
        pending = next(o for o in response.json() if o["customer_name"] == "Alice")
        self.assertEqual(pending["tag"], "pending")
        self.assertNotIn("tracking_number", pending)
        self.assertNotIn("cancellation_reason", pending)

    def test_list_shipped_order_has_tracking_number(self) -> None:
        response = self.client.get("/api/orders/", HTTP_AUTHORIZATION=self.token)
        shipped = next(o for o in response.json() if o["customer_name"] == "Bob")
        self.assertEqual(shipped["tag"], "shipped")
        self.assertEqual(shipped["tracking_number"], "TRACK123")

    def test_list_cancelled_order_has_cancellation_reason(self) -> None:
        response = self.client.get("/api/orders/", HTTP_AUTHORIZATION=self.token)
        cancelled = next(o for o in response.json() if o["customer_name"] == "Charlie")
        self.assertEqual(cancelled["tag"], "cancelled")
        self.assertEqual(cancelled["cancellation_reason"], "Changed mind")

    def test_filter_by_status(self) -> None:
        response = self.client.get(
            "/api/orders/?status=pending", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer_name"], "Alice")

    def test_filter_by_q_customer_name(self) -> None:
        response = self.client.get("/api/orders/?q=bob", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer_name"], "Bob")

    def test_filter_by_min_total(self) -> None:
        response = self.client.get(
            "/api/orders/?min_total=100", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 200)
        names = {o["customer_name"] for o in response.json()}
        # DraftUser (999.00) is excluded because drafts are always filtered out
        self.assertEqual(names, {"Bob", "Charlie"})

    def test_filter_by_max_total(self) -> None:
        response = self.client.get(
            "/api/orders/?max_total=60", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 200)
        names = {o["customer_name"] for o in response.json()}
        self.assertEqual(names, {"Alice"})

    def test_invalid_status_returns_422(self) -> None:
        response = self.client.get(
            "/api/orders/?status=bogus", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 422)


class OrdersDetailAPITest(TestCase):
    token: str  # pyright: ignore[reportUninitializedInstanceVariable]
    pending: Order  # pyright: ignore[reportUninitializedInstanceVariable]
    shipped: Order  # pyright: ignore[reportUninitializedInstanceVariable]
    cancelled: Order  # pyright: ignore[reportUninitializedInstanceVariable]
    draft: Order  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        user = User.objects.create_user(username="detailuser", password="pass123!")
        self.token = f"Bearer {AccessToken.for_user(user)}"

        self.pending = _create_order("Alice", Order.Status.PENDING, total_price="50.00")
        self.shipped = _create_order(
            "Bob",
            Order.Status.SHIPPED,
            total_price="200.00",
            tracking_number="TRACK123",
            shipped_at="2026-01-01T10:00:00Z",
        )
        self.cancelled = _create_order(
            "Charlie",
            Order.Status.CANCELLED,
            total_price="75.00",
            cancellation_reason="Changed mind",
            cancelled_at="2026-01-02T10:00:00Z",
        )
        self.draft = _create_order("DraftUser", Order.Status.DRAFT, total_price="999.00")

    def test_detail_requires_auth(self) -> None:
        response = self.client.get(f"/api/orders/{self.pending.pk}/")
        self.assertEqual(response.status_code, 401)

    def test_get_pending_order(self) -> None:
        response = self.client.get(
            f"/api/orders/{self.pending.pk}/", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "pending")
        self.assertEqual(data["customer_name"], "Alice")
        self.assertNotIn("tracking_number", data)
        self.assertNotIn("cancellation_reason", data)

    def test_get_shipped_order(self) -> None:
        response = self.client.get(
            f"/api/orders/{self.shipped.pk}/", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "shipped")
        self.assertEqual(data["tracking_number"], "TRACK123")
        self.assertIn("shipped_at", data)

    def test_get_cancelled_order(self) -> None:
        response = self.client.get(
            f"/api/orders/{self.cancelled.pk}/", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "cancelled")
        self.assertEqual(data["cancellation_reason"], "Changed mind")
        self.assertIn("cancelled_at", data)

    def test_get_nonexistent_order_returns_404(self) -> None:
        response = self.client.get("/api/orders/99999/", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["tag"], "order_not_found")
        self.assertEqual(data["id"], 99999)

    def test_get_draft_order_returns_403(self) -> None:
        response = self.client.get(
            f"/api/orders/{self.draft.pk}/", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["tag"], "order_not_accessible")
        self.assertEqual(data["id"], self.draft.pk)
```

- [ ] **Step 2: Run tests to verify they fail (red phase)**

```bash
uv run python manage.py test orders
```

Expected: API tests fail with AssertionError (404 response) — the router is not registered yet. The 3 model tests still pass.

- [ ] **Step 3: Commit the failing tests**

```bash
git add orders/tests.py
git commit -m "test: add orders API integration tests (red phase)"
```

---

## Chunk 3: Service, API, and Client

### Task 5: Implement the orders service

**Files:**
- Create: `orders/service.py`

- [ ] **Step 1: Create `orders/service.py`**

```python
from orders.exceptions import OrderNotAccessible, OrderNotFound
from orders.models import Order
from orders.schemas import (
    CancelledOrderSchema,
    OrderFilters,
    PendingOrderSchema,
    ShippedOrderSchema,
)

OrderQueryResult = PendingOrderSchema | ShippedOrderSchema | CancelledOrderSchema


def _to_schema(order: Order) -> OrderQueryResult:
    match order.status:
        case Order.Status.PENDING:
            return PendingOrderSchema(
                id=order.pk,
                customer_name=order.customer_name,
                items_count=order.items_count,
                total_price=order.total_price,
                created_at=order.created_at,
            )
        case Order.Status.SHIPPED:
            return ShippedOrderSchema(
                id=order.pk,
                customer_name=order.customer_name,
                items_count=order.items_count,
                total_price=order.total_price,
                tracking_number=order.tracking_number or "",
                shipped_at=order.shipped_at,  # type: ignore[arg-type]
                created_at=order.created_at,
            )
        case Order.Status.CANCELLED:
            return CancelledOrderSchema(
                id=order.pk,
                customer_name=order.customer_name,
                items_count=order.items_count,
                total_price=order.total_price,
                cancellation_reason=order.cancellation_reason or "",
                cancelled_at=order.cancelled_at,  # type: ignore[arg-type]
                created_at=order.created_at,
            )
        case Order.Status.DRAFT | _:
            # DRAFT is excluded before _to_schema is called; this branch should never be reached
            raise ValueError(f"Unexpected order status in _to_schema: {order.status}")


def list_orders(filters: OrderFilters) -> list[OrderQueryResult]:
    # Draft orders are always excluded — they are an internal status not exposed to consumers.
    # list_orders never raises OrderNotFound/OrderNotAccessible: filters simply narrow results.
    qs = Order.objects.exclude(status=Order.Status.DRAFT)
    qs = filters.filter(qs)
    return [_to_schema(order) for order in qs]


def get_order(order_id: int) -> OrderQueryResult:
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        raise OrderNotFound(order_id)

    if order.status == Order.Status.DRAFT:
        raise OrderNotAccessible(order_id)

    return _to_schema(order)
```

- [ ] **Step 2: Run type check on service**

```bash
uv run basedpyright orders/service.py
```

Expected: no errors (the `type: ignore` comments suppress the nullable field warnings).

- [ ] **Step 3: Run tests (still failing — router not registered yet)**

```bash
uv run python manage.py test orders
```

Expected: `Not Found: /api/orders/` — API tests still fail. Model tests still pass.

- [ ] **Step 4: Commit**

```bash
git add orders/service.py
git commit -m "feat: implement orders service"
```

---

### Task 6: Implement the orders API and register the router

**Files:**
- Create: `orders/api.py`
- Modify: `project/api.py`

- [ ] **Step 1: Create `orders/api.py`**

`list_orders` never raises errors (filters silently narrow results), so its `response=` only declares success. Errors from `get_order` are raised as `AppException` subclasses and caught by the global handler — the `-> OrderResult` annotation is correct at the Python level.

```python
from django.http import HttpRequest
from ninja import Query, Router
from ninja_jwt.authentication import JWTAuth

from orders import service
from orders.schemas import (
    OrderFilters,
    OrderNotAccessibleError,
    OrderNotFoundError,
    OrderResult,
)

router = Router(auth=JWTAuth())


@router.get("/", response=list[OrderResult])
def list_orders(request: HttpRequest, filters: Query[OrderFilters]) -> list[OrderResult]:
    return service.list_orders(filters)  # type: ignore[return-value]


@router.get(
    "/{order_id}/",
    response={200: OrderResult, 404: OrderNotFoundError, 403: OrderNotAccessibleError},
)
def get_order(request: HttpRequest, order_id: int) -> OrderResult:
    # Errors are raised as AppException subclasses — caught by the global handler in project/api.py
    return service.get_order(order_id)  # type: ignore[return-value]
```

- [ ] **Step 2: Register the orders router in `project/api.py`**

```python
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
```

- [ ] **Step 3: Run all tests (green phase)**

```bash
uv run python manage.py test
```

Expected: all tests pass, including all new orders tests.

- [ ] **Step 4: Run lint and type check**

```bash
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
```

Fix any issues before committing.

- [ ] **Step 5: Commit**

```bash
git status
git add orders/api.py project/api.py
git commit -m "feat: implement orders API endpoints and register router"
```

---

### Task 7: Regenerate TypeScript client and add usage example

**Files:**
- Modify: `client/openapi.json` (generated)
- Modify: `client/src/generated/` (generated)
- Create: `client/src/ts-pattern/orders.ts`

- [ ] **Step 1: Regenerate the client**

```bash
task generate:client
```

Expected: `client/openapi.json` and `client/src/generated/types.gen.ts` updated with orders types.

- [ ] **Step 2: Verify generated types in `client/src/generated/types.gen.ts`**

Check that these types are present (names may vary slightly):

```typescript
type PendingOrderSchema    = { tag: 'pending';   id: number; customer_name: string; ... }
type ShippedOrderSchema    = { tag: 'shipped';   id: number; ... tracking_number: string; ... }
type CancelledOrderSchema  = { tag: 'cancelled'; id: number; ... cancellation_reason: string; ... }
type OrderResult           = PendingOrderSchema | ShippedOrderSchema | CancelledOrderSchema;
type OrderNotFoundError    = { tag: 'order_not_found'; id: number; detail: string }
type OrderNotAccessibleError = { tag: 'order_not_accessible'; id: number; detail: string }
```

**If `OrderResult` is inlined (not a named type):** Django Ninja may not have registered the `RootModel` subclass as a `$ref` component. Verify that `OrderResult` is defined as a class (`class OrderResult(RootModel[...]):`), not a type alias. This is the same issue that was previously solved for `ProductResult`.

- [ ] **Step 3: Create `client/src/ts-pattern/orders.ts`**

```typescript
import { match } from "ts-pattern";
import type {
  CancelledOrderSchema,
  OrderNotAccessibleError,
  OrderNotFoundError,
  OrderResult,
  PendingOrderSchema,
  ShippedOrderSchema,
} from "../generated/types.gen";

function describeOrder(order: OrderResult): string {
  return match(order)
    .with({ tag: "pending" }, (o: PendingOrderSchema) => `Order for ${o.customer_name} is pending`)
    .with(
      { tag: "shipped" },
      (o: ShippedOrderSchema) =>
        `Order for ${o.customer_name} shipped — tracking: ${o.tracking_number}`
    )
    .with(
      { tag: "cancelled" },
      (o: CancelledOrderSchema) =>
        `Order for ${o.customer_name} cancelled — reason: ${o.cancellation_reason}`
    )
    .exhaustive();
}

function describeError(error: OrderNotFoundError | OrderNotAccessibleError): string {
  return match(error)
    .with({ tag: "order_not_found" }, (e: OrderNotFoundError) => `Order ${e.id} not found`)
    .with(
      { tag: "order_not_accessible" },
      (e: OrderNotAccessibleError) => `Order ${e.id} is not accessible`
    )
    .exhaustive();
}

export { describeError, describeOrder };
```

- [ ] **Step 4: Commit**

```bash
git status
git add client/
git commit -m "feat: regenerate client and add orders TypeScript usage example"
```

---

## Done

At this point:
- `uv run python manage.py test` — all tests pass
- `GET /api/orders/` — returns filtered list of non-draft orders with correct polymorphic tags
- `GET /api/orders/{id}/` — returns typed order or typed 403/404 error via global handler
- `GET /api/docs` — shows full OpenAPI documentation including all schemas and errors
- `client/src/generated/types.gen.ts` — contains `OrderResult`, all variant schemas, error types
- `client/src/ts-pattern/orders.ts` — demonstrates exhaustive TypeScript pattern matching
