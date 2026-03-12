# Orders App Design

**Date:** 2026-03-12
**Status:** Approved

## Goal

Introduce a new `orders` Django app that demonstrates the company's layered architecture pattern (`api → service → model`) with clean module boundaries. Serves as an MVP demo showing engineers: path params, query params with filtering, typed errors, and polymorphic response types — all generating correct TypeScript types via the existing OpenAPI pipeline.

## Architecture

```
api.py → service.py → models.py
api.py → schemas.py
service.py → schemas.py
exceptions.py → schemas.py (error schemas)
project/api.py → core/exceptions.py (global handler)
```

Models never appear in `api.py`. The service layer can be swapped to call external services or other backends without touching the API layer.

## New Files

```
orders/
  models.py      — Django ORM model
  schemas.py     — Pydantic schemas (service return types + API serialization + FilterSchema)
  exceptions.py  — OrderNotFound, OrderNotAccessible
  service.py     — Business logic; returns schema instances, raises exceptions
  api.py         — Router + JWT auth; two endpoints
  tests.py       — Tests

core/
  exceptions.py  — NEW: AppException base class (AppError stays in core/schemas.py)
```

`project/api.py` gets one global exception handler for `AppException`, and the orders router is registered via `api.add_router("/orders/", orders_router)`.

## Data Model (`orders/models.py`)

Field declarations are illustrative — use the appropriate Django field types (`CharField`, `DecimalField(max_digits=10, decimal_places=2)`, `DateTimeField`, etc.) in the actual implementation.

```python
class Order(models.Model):
    class Status(TextChoices):
        DRAFT      = "draft"       # internal — triggers 403 on API access
        PENDING    = "pending"
        SHIPPED    = "shipped"
        CANCELLED  = "cancelled"

    customer_name = CharField(max_length=255)
    total_price   = DecimalField(max_digits=10, decimal_places=2)
    items_count   = IntegerField()
    status        = CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    tracking_number    = CharField(max_length=100, null=True, blank=True)  # shipped only
    shipped_at         = DateTimeField(null=True, blank=True)              # shipped only
    cancellation_reason = CharField(max_length=255, null=True, blank=True) # cancelled only
    cancelled_at       = DateTimeField(null=True, blank=True)              # cancelled only
    created_at    = DateTimeField(auto_now_add=True)
```

`draft` orders exist in the DB but are not accessible via the public API. Fetching one returns a typed 403 — demonstrating that model status != API-visible state.

## Schemas (`orders/schemas.py`)

Schemas serve double duty: they are both the service layer's return type contract and the API serialization format. No parallel type hierarchy needed.

**Why `TaggedSchema` and not `TaggedModelSchema`:** These schemas are the service layer's contract, intentionally decoupled from the ORM. Using `ModelSchema` would tie them to Django model field definitions, breaking the independence of the service layer. Fields are declared explicitly.

### Success schemas

All extend `TaggedSchema`. `tag` has a default value so the service constructs them without explicitly setting it:

```python
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
```

`OrderResult` uses the same `RootModel` pattern as `ProductResult` — generates a named type in OpenAPI, producing a clean TypeScript union via hey-api. `list[OrderResult]` in the list endpoint generates an array of this named type.

### Error schemas

`detail` is inherited from `AppError` (defined in `core/schemas.py`). `tag` has a default so exceptions can be constructed without passing it explicitly:

```python
class OrderNotFoundError(AppError):
    tag: Literal["order_not_found"] = "order_not_found"
    id: int

class OrderNotAccessibleError(AppError):
    tag: Literal["order_not_accessible"] = "order_not_accessible"
    id: int
```

### Filter schema

```python
class OrderFilters(FilterSchema):
    status: Order.Status | None = None
    q: str | None = Field(None, q=["customer_name__icontains"])
    min_total: Decimal | None = Field(None, q="total_price__gte")
    max_total: Decimal | None = Field(None, q="total_price__lte")
```

`status` is typed as `Order.Status | None` (not raw `str`) so Django Ninja validates the enum value and returns 422 on invalid input. `FilterSchema` handles ORM Q-expression generation for all fields.

## Core Exception Infrastructure (`core/exceptions.py`)

`AppException` is a new base class for all domain exceptions that carry a typed HTTP error payload. It is separate from `AppError` (the Pydantic schema in `core/schemas.py`).

```python
class AppException(Exception):
    def __init__(self, status_code: int, error: AppError):
        self.status_code = status_code
        self.error = error
```

Global handler registered in `project/api.py`:

```python
@api.exception_handler(AppException)
def handle_app_exception(request, exc: AppException):
    return api.create_response(request, exc.error.model_dump(), status=exc.status_code)
```

## Order Exceptions (`orders/exceptions.py`)

```python
class OrderNotFound(AppException):
    def __init__(self, order_id: int):
        super().__init__(404, OrderNotFoundError(id=order_id, detail="Order not found"))

class OrderNotAccessible(AppException):
    def __init__(self, order_id: int):
        super().__init__(403, OrderNotAccessibleError(id=order_id, detail="Order not accessible"))
```

## Service Layer (`orders/service.py`)

```python
OrderQueryResult = PendingOrderSchema | ShippedOrderSchema | CancelledOrderSchema

def list_orders(filters: OrderFilters) -> list[OrderQueryResult]:
    ...

def get_order(order_id: int) -> OrderQueryResult:
    """Raises OrderNotFound, OrderNotAccessible."""
    ...
```

The service:
- `list_orders`: applies `filters.filter(Order.objects.exclude(status=Order.Status.DRAFT))` — draft orders are silently excluded from list results; they are an internal status not exposed to API consumers
- `get_order`: fetches by ID, raises `OrderNotFound` if missing, raises `OrderNotAccessible` if `status == DRAFT`, otherwise constructs and returns the matching schema variant
- Matches on `order.status` to construct the appropriate schema instance (`PendingOrderSchema`, `ShippedOrderSchema`, or `CancelledOrderSchema`)

## API Layer (`orders/api.py`)

```python
router = Router(auth=JWTAuth())

@router.get("/", response=list[OrderResult])
def list_orders(request, filters: Query[OrderFilters]):
    return service.list_orders(filters)

@router.get(
    "/{order_id}/",
    response={200: OrderResult, 404: OrderNotFoundError, 403: OrderNotAccessibleError},
)
def get_order(request, order_id: int):
    return service.get_order(order_id)
```

No try/except in endpoints — exceptions propagate to the global handler in `project/api.py`.

## Endpoints

| Method | Path | Auth | Query params | Responses |
|--------|------|------|-------------|-----------|
| GET | `/orders/` | JWT | `status`, `q`, `min_total`, `max_total` | `list[OrderResult]` |
| GET | `/orders/{order_id}/` | JWT | — | `200: OrderResult`, `404: OrderNotFoundError`, `403: OrderNotAccessibleError` |

## Generated TypeScript

Following the same `RootModel` + hey-api pipeline:

```typescript
type PendingOrderSchema    = { tag: 'pending';   id: number; customer_name: string; items_count: number; total_price: string; created_at: string }
type ShippedOrderSchema    = { tag: 'shipped';   id: number; customer_name: string; items_count: number; total_price: string; tracking_number: string; shipped_at: string; created_at: string }
type CancelledOrderSchema  = { tag: 'cancelled'; id: number; customer_name: string; items_count: number; total_price: string; cancellation_reason: string; cancelled_at: string; created_at: string }

type OrderResult = PendingOrderSchema | ShippedOrderSchema | CancelledOrderSchema;

type OrderNotFoundError      = { tag: 'order_not_found';      id: number; detail: string }
type OrderNotAccessibleError = { tag: 'order_not_accessible'; id: number; detail: string }

type OrdersApiGetOrderError = OrderNotFoundError | OrderNotAccessibleError;
```

## Test Cases (`orders/tests.py`)

Tests must cover:

**`list_orders` (`GET /orders/`)**
- Returns 401 without JWT
- Returns all non-draft orders (pending, shipped, cancelled)
- Draft orders are excluded silently
- Filter by `status=pending` returns only pending orders
- Filter by `q=<name>` returns matching customer names (case-insensitive)
- Filter by `min_total` / `max_total` returns orders within price range
- Each returned item has the correct `tag` and variant-specific fields

**`get_order` (`GET /orders/{order_id}/`)**
- Returns 401 without JWT
- Returns pending order with `tag="pending"` and correct fields
- Returns shipped order with `tag="shipped"` and `tracking_number`, `shipped_at`
- Returns cancelled order with `tag="cancelled"` and `cancellation_reason`, `cancelled_at`
- Returns 404 (`tag="order_not_found"`) for non-existent order
- Returns 403 (`tag="order_not_accessible"`) for draft order

## Demo Patterns Covered

| Pattern | Where |
|---------|-------|
| Path param | `GET /orders/{order_id}/` |
| Query params (text search, enum filter, range) | `GET /orders/?q=...&status=...&min_total=...` |
| Polymorphic response (3 variants, different fields) | `OrderResult` |
| Typed errors (404 + 403 with distinct schemas) | `get_order` endpoint |
| Service layer (no ORM in api.py) | `service.py` |
| Global exception handling | `core/exceptions.py` + `project/api.py` |
| JWT auth | Both endpoints |

## Scalability Pattern

This establishes the template for all future apps:

1. `schemas.py` — define service types (Pydantic schemas with tag defaults) + `RootModel` union + `FilterSchema`
2. `exceptions.py` — domain exceptions extending `AppException`
3. `service.py` — business logic; returns schema instances, raises domain exceptions
4. `api.py` — thin router; no ORM, no try/except
