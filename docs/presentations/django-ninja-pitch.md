# Django Ninja: The Missing Layer

---

## The Problem

Things we've been struggling with:

- TypeScript types exist, but no discriminated unions — frontend can't discriminate on response type
- No end-to-end type safety: model field changes don't propagate to the response schema
- Schema duplication — models defined once, serializers again manually
- No typed error contracts — frontend can't discriminate on error type
- Views bloated with boilerplate, hard to read

---

## Enter Django Ninja

Pydantic + Django. Sits on top of Django — not a replacement.

- Type-annotated views with automatic validation
- OpenAPI schema generated from the code
- Typed responses and errors, per status code
- Global exception handling

---

## ModelSchema

Schema fields derived from the model — no duplication.

```python
class AvailableProductSchema(ModelSchema):
    tag: Literal["available"] = Field(validation_alias="status")

    class Meta:
        model = Product
        exclude = ["status", "created", "updated"]
```

- Fields come from the model — define once
- `exclude` to drop what the API shouldn't expose
- `validation_alias` to remap ORM fields to API fields

---

## Polymorphic Responses

Different response shapes per order status, all typed.

```python
class OrderResult(
    RootModel[PendingOrderSchema | ShippedOrderSchema | CancelledOrderSchema]
):
    pass
```

- Each variant has `tag: Literal["pending"]` etc.
- `RootModel` produces a **named** OpenAPI type
- `ShippedOrderSchema` has `tracking_number` — `PendingOrderSchema` doesn't

---

## Typed Errors

Each status code has its own error schema.

```python
@router.get(
    "/{order_id}/",
    response={
        200: OrderResult,
        404: OrderNotFoundError,
        403: OrderNotAccessibleError,
    },
)
def get_order(request, order_id: int):
    return service.get_order(order_id)
```

- Each error status has its own schema
- `tag` field identifies the error type
- OpenAPI documents all of them

---

## FilterSchema

Query param filters declared as a schema — no manual `Q()` objects.

```python
class OrderFilters(FilterSchema):
    status: Order.Status | None = None
    q: str | None = Field(None, q=["customer_name__icontains"])
    min_total: Decimal | None = Field(None, q="total_price__gte")
    max_total: Decimal | None = Field(None, q="total_price__lte")
```

```python
def list_orders(request, filters: Query[OrderFilters]):
    return service.list_orders(filters)
```

- `status` validated as enum — 422 on invalid input

---

## Global Exception Handling

One handler registered on the API instance — no `try/except` in endpoints.

```python
@api.exception_handler(AppException)
def handle_app_exception(request, exc: AppException):
    return api.create_response(
        request, exc.error.model_dump(), status=exc.status_code
    )
```

Domain exceptions carry their own payload:

```python
class OrderNotFound(AppException):
    def __init__(self, order_id: int):
        super().__init__(404, OrderNotFoundError(id=order_id, detail="Order not found"))
```

---

## OpenAPI → TypeScript

Django Ninja generates an OpenAPI schema. hey-api turns it into TypeScript types.

```typescript
type OrderResult =
  | { tag: 'pending';   id: number; customer_name: string; total_price: string }
  | { tag: 'shipped';   id: number; tracking_number: string; shipped_at: string }
  | { tag: 'cancelled'; id: number; cancellation_reason: string; cancelled_at: string }

type OrdersApiGetOrderError =
  | { tag: 'order_not_found';      id: number; detail: string }
  | { tag: 'order_not_accessible'; id: number; detail: string }
```

- Switch on `tag` — TypeScript narrows the type
- Error types are **also** discriminated unions

---

## Architecture

Three layers, clear boundaries.

```
api.py  →  service.py  →  models.py
api.py  →  schemas.py
service.py  →  schemas.py
exceptions.py  →  schemas.py
```

- `api.py` — thin router; no ORM, no try/except
- `service.py` — business logic; raises typed exceptions
- `schemas.py` — Pydantic types; serve as service contracts
- `exceptions.py` — domain exceptions with HTTP payloads

---

## What We Built

Patterns implemented in this repo:

| Pattern | Where |
|---|---|
| `ModelSchema` | `products/schemas.py` |
| Polymorphic union (`RootModel`) | `products/`, `orders/` |
| Typed multi-status responses | `products/api.py`, `orders/api.py` |
| `FilterSchema` | `orders/schemas.py` |
| Global exception handler | `core/exceptions.py` |
| JWT auth on all routes | Both routers |

---

## Verdict

- **Discriminated unions** → `RootModel` + `tag: Literal[...]` generates proper TypeScript unions
- **End-to-end type safety** → model → `ModelSchema` → OpenAPI → TypeScript, one chain
- **Duplication** → `ModelSchema` derives fields from the model
- **Typed errors** → one global handler, typed error schema per status code
- **Boilerplate** → thin endpoints, logic in the service layer
