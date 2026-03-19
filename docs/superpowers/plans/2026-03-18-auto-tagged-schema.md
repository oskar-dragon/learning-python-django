# Auto-derived Tags for TaggedSchema — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `TaggedSchema` auto-derive the `tag` field from the class name (with optional override), eliminating manual `tag: Literal[...]` declarations and `tag=` constructor args across the codebase.

**Architecture:** `TaggedSchema.__init_subclass__` injects a `Literal["ClassName"]` annotation and class-level default for `tag`, then calls `model_rebuild()`. Subclasses can override via `class Foo(TaggedSchema, tag="custom"):`. All `AppError` subclasses inherit this behavior.

**Tech Stack:** Python 3.13, Django 6, Django Ninja, Pydantic v2, Hey API (TypeScript client generation), ts-pattern

**Spec:** `docs/superpowers/specs/2026-03-18-auto-tagged-schema-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `core/schemas.py` | Modify | Add `__init_subclass__` to `TaggedSchema` |
| `core/tests.py` | Modify | Update `AppError` tests to use concrete subclass |
| `orders/schemas.py` | Modify | Remove `tag: Literal[...]` from 5 subclasses |
| `orders/service.py` | Modify | Remove `tag=...` from 3 constructor calls |
| `orders/exceptions.py` | Modify | Remove `tag=...` from 2 constructor calls |
| `orders/tests.py` | Modify | Update expected tag values (8 assertions) |
| `blog/api.py` | Modify | Remove `tag: Literal[...]` from class; update dict tag value |
| `products/schemas.py` | Modify | Remove `tag: Literal[...]` from 2 error subclasses |
| `products/api.py` | Modify | Update 3 dict tag values |
| `products/tests.py` | Modify | Update expected tag values (2 assertions) |
| `client/src/ts-pattern/orders.ts` | Modify | Update 5 tag strings |
| `client/src/ts-pattern/posts.ts` | Modify | Update 2 tag strings |
| `client/src/ts-pattern/products.ts` | Modify | Update 4 tag strings |
| `client/src/generated/` | Regenerate | Regenerate TypeScript client |

---

### Task 1: Spike — verify `__init_subclass__` works with `ninja.Schema` and Pydantic v2

**Files:**
- Modify: `core/schemas.py`

This task is a quick verification that the mechanism works before we write real tests. We run it in a Python shell and verify the output. If it doesn't work, we adjust the approach before proceeding.

- [ ] **Step 1: Add `__init_subclass__` to `TaggedSchema`**

In `core/schemas.py`, replace the entire file with:

```python
from typing import Any, Literal

from ninja import Schema
from pydantic import ConfigDict


class TaggedSchema(Schema):
    """Base for all discriminated union schemas. Subclasses auto-derive tag from class name."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str

    def __init_subclass__(cls, tag: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        resolved_tag = tag or cls.__name__
        cls.__annotations__["tag"] = Literal[resolved_tag]
        cls.tag = resolved_tag
        cls.model_rebuild()


class AppError(TaggedSchema):
    """Base for all API error responses. Subclasses narrow tag to a Literal."""

    detail: str
```

- [ ] **Step 2: Verify in Django shell**

Run: `uv run manage.py shell -c "
from core.schemas import TaggedSchema, AppError
from pydantic import RootModel
from typing import Literal, get_type_hints

# Test 1: AppError gets auto-tag
e = AppError(detail='test')
print(f'AppError tag: {e.tag!r}')
assert e.tag == 'AppError', f'Expected AppError, got {e.tag!r}'

# Test 2: Subclass gets auto-tag
class FooError(AppError):
    code: int
f = FooError(detail='x', code=1)
print(f'FooError tag: {f.tag!r}')
assert f.tag == 'FooError', f'Expected FooError, got {f.tag!r}'

# Test 3: Override works
class BarSchema(TaggedSchema, tag='custom'):
    val: int
b = BarSchema(val=1)
print(f'BarSchema tag: {b.tag!r}')
assert b.tag == 'custom', f'Expected custom, got {b.tag!r}'

# Test 4: Literal type in JSON schema
schema = FooError.model_json_schema()
print(f'FooError JSON schema tag: {schema[\"properties\"][\"tag\"]}')

# Test 5: model_dump includes tag
print(f'FooError dump: {f.model_dump()}')

# Test 6: RootModel discriminated union
class ASchema(TaggedSchema):
    a: int
class BSchema(TaggedSchema):
    b: str
Union = RootModel[ASchema | BSchema]
parsed = Union.model_validate({'tag': 'ASchema', 'a': 42})
print(f'Union parsed: {parsed.root}')
assert isinstance(parsed.root, ASchema)

print('ALL SPIKE CHECKS PASSED')
"`

Expected: All assertions pass, `ALL SPIKE CHECKS PASSED` printed.

If any check fails, stop and diagnose. The implementation approach may need adjustment (e.g., using `FieldInfo` directly, or setting `model_fields` explicitly).

- [ ] **Step 3: Commit the spike**

```bash
git add core/schemas.py
git commit -m "feat: add __init_subclass__ to TaggedSchema for auto-derived tags"
```

---

### Task 2: Write and pass `TaggedSchema` unit tests

**Files:**
- Modify: `core/tests.py`

- [ ] **Step 1: Write the failing tests**

Replace `core/tests.py` with:

```python
from typing import Literal, get_args, get_type_hints

from django.test import TestCase
from pydantic import RootModel

from core.exceptions import AppException
from core.schemas import AppError, TaggedSchema


class TaggedSchemaAutoTagTest(TestCase):
    """Tests for TaggedSchema's __init_subclass__ auto-tag mechanism."""

    def test_subclass_gets_class_name_as_tag(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        instance = MySchema(value=1)
        self.assertEqual(instance.tag, "MySchema")

    def test_tag_has_literal_type(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        hints = get_type_hints(MySchema, include_extras=True)
        self.assertEqual(hints["tag"], Literal["MySchema"])

    def test_explicit_tag_override(self) -> None:
        class CustomSchema(TaggedSchema, tag="custom"):
            value: int

        instance = CustomSchema(value=1)
        self.assertEqual(instance.tag, "custom")

    def test_explicit_tag_override_has_literal_type(self) -> None:
        class CustomSchema(TaggedSchema, tag="custom"):
            value: int

        hints = get_type_hints(CustomSchema, include_extras=True)
        self.assertEqual(hints["tag"], Literal["custom"])

    def test_tag_included_in_model_dump(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        data = MySchema(value=1).model_dump()
        self.assertEqual(data["tag"], "MySchema")

    def test_tag_in_json_schema(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        schema = MySchema.model_json_schema()
        tag_prop = schema["properties"]["tag"]
        self.assertEqual(tag_prop["const"], "MySchema")

    def test_discriminated_union_with_root_model(self) -> None:
        class AlphaSchema(TaggedSchema):
            a: int

        class BetaSchema(TaggedSchema):
            b: str

        Union = RootModel[AlphaSchema | BetaSchema]

        alpha = Union.model_validate({"tag": "AlphaSchema", "a": 42})
        self.assertIsInstance(alpha.root, AlphaSchema)

        beta = Union.model_validate({"tag": "BetaSchema", "b": "hello"})
        self.assertIsInstance(beta.root, BetaSchema)

    def test_intermediate_class_gets_own_tag(self) -> None:
        """AppError is an intermediate class — it should get tag='AppError'."""
        error = AppError(detail="test")
        self.assertEqual(error.tag, "AppError")

    def test_intermediate_class_does_not_break_subclass_tags(self) -> None:
        class ConcreteError(AppError):
            code: int

        error = ConcreteError(detail="test", code=42)
        self.assertEqual(error.tag, "ConcreteError")
        self.assertNotEqual(error.tag, "AppError")


class AppExceptionTest(TestCase):
    def test_stores_status_code_and_error(self) -> None:
        class TestError(AppError):
            pass

        error = TestError(detail="something went wrong")
        exc = AppException(404, error)
        self.assertEqual(exc.status_code, 404)
        self.assertIs(exc.error, error)
        self.assertEqual(error.tag, "TestError")

    def test_is_exception_subclass(self) -> None:
        class TestError(AppError):
            pass

        error = TestError(detail="something went wrong")
        exc = AppException(500, error)
        self.assertIsInstance(exc, Exception)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run manage.py test core -v2`

Expected: All tests pass. If the spike in Task 1 succeeded, these should all pass.

- [ ] **Step 3: Commit**

```bash
git add core/tests.py
git commit -m "test: add TaggedSchema auto-tag unit tests and update AppException tests"
```

---

### Task 3: Update orders app — schemas, service, exceptions

**Files:**
- Modify: `orders/schemas.py` — remove `tag: Literal[...]` from 5 classes
- Modify: `orders/service.py` — remove `tag=...` from 3 constructor calls
- Modify: `orders/exceptions.py` — remove `tag=...` from 2 constructor calls
- Modify: `orders/tests.py` — update 8 tag assertions

- [ ] **Step 1: Update `orders/schemas.py`**

Remove the `tag: Literal[...]` line from each of these 5 classes:
- `PendingOrderSchema` (line 13): remove `tag: Literal["pending"]`
- `ShippedOrderSchema` (line 22): remove `tag: Literal["shipped"]`
- `CancelledOrderSchema` (line 33): remove `tag: Literal["cancelled"]`
- `OrderNotFoundError` (line 48): remove `tag: Literal["order_not_found"]`
- `OrderNotAccessibleError` (line 53): remove `tag: Literal["order_not_accessible"]`

Also remove `Literal` from the imports since it's no longer used.

After edits, the file should look like:

```python
from datetime import datetime
from decimal import Decimal

from ninja.filter_schema import FilterSchema
from pydantic import Field, RootModel

from core.schemas import AppError, TaggedSchema
from orders.models import Order


class PendingOrderSchema(TaggedSchema):
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    created_at: datetime


class ShippedOrderSchema(TaggedSchema):
    id: int
    customer_name: str
    items_count: int
    total_price: Decimal
    tracking_number: str
    shipped_at: datetime
    created_at: datetime


class CancelledOrderSchema(TaggedSchema):
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
    id: int


class OrderNotAccessibleError(AppError):
    id: int


class OrderFilters(FilterSchema):
    status: Order.Status | None = None
    q: str | None = Field(None, q=["customer_name__icontains"])  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
    min_total: Decimal | None = Field(None, q="total_price__gte")  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
    max_total: Decimal | None = Field(None, q="total_price__lte")  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
```

- [ ] **Step 2: Update `orders/service.py`**

Remove `tag=...` from all three constructor calls in `_to_schema`. The match arms become:

```python
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
        shipped_at=order.shipped_at,  # pyright: ignore[reportArgumentType]
        created_at=order.created_at,
    )
case Order.Status.CANCELLED:
    return CancelledOrderSchema(
        id=order.pk,
        customer_name=order.customer_name,
        items_count=order.items_count,
        total_price=order.total_price,
        cancellation_reason=order.cancellation_reason or "",
        cancelled_at=order.cancelled_at,  # pyright: ignore[reportArgumentType]
        created_at=order.created_at,
    )
```

- [ ] **Step 3: Update `orders/exceptions.py`**

Remove `tag=...` from both constructor calls:

```python
from core.exceptions import AppException
from orders.schemas import OrderNotAccessibleError, OrderNotFoundError


class OrderNotFound(AppException):
    def __init__(self, order_id: int) -> None:
        super().__init__(
            404, OrderNotFoundError(id=order_id, detail="Order not found")
        )


class OrderNotAccessible(AppException):
    def __init__(self, order_id: int) -> None:
        super().__init__(
            403,
            OrderNotAccessibleError(
                id=order_id, detail="Order not accessible"
            ),
        )
```

- [ ] **Step 4: Update `orders/tests.py`**

Update these 8 tag assertions to use new class-name-based tags:

| Line | Old value | New value |
|---|---|---|
| 94 | `"pending"` | `"PendingOrderSchema"` |
| 101 | `"shipped"` | `"ShippedOrderSchema"` |
| 107 | `"cancelled"` | `"CancelledOrderSchema"` |
| 179 | `"pending"` | `"PendingOrderSchema"` |
| 188 | `"shipped"` | `"ShippedOrderSchema"` |
| 198 | `"cancelled"` | `"CancelledOrderSchema"` |
| 206 | `"order_not_found"` | `"OrderNotFoundError"` |
| 213 | `"order_not_accessible"` | `"OrderNotAccessibleError"` |

- [ ] **Step 5: Run order tests**

Run: `uv run manage.py test orders -v2`

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add orders/schemas.py orders/service.py orders/exceptions.py orders/tests.py
git commit -m "refactor(orders): remove manual tag declarations, use auto-derived tags"
```

---

### Task 4: Update products app — schemas, API, tests

**Files:**
- Modify: `products/schemas.py` — remove `tag: Literal[...]` from 2 error subclasses
- Modify: `products/api.py` — update 3 dict tag values
- Modify: `products/tests.py` — update 2 tag assertions

- [ ] **Step 1: Update `products/schemas.py`**

Remove `tag: Literal[...]` from `ProductNotFoundError` (line 39) and `ProductHiddenError` (line 44). Also remove `Literal` from the imports.

After edits, the error classes become:

```python
class ProductNotFoundError(AppError):
    id: int


class ProductHiddenError(AppError):
    id: int
```

**Do NOT touch** `AvailableProductSchema` or `OutOfStockProductSchema` — they are `ModelSchema` subclasses, not `TaggedSchema`.

- [ ] **Step 2: Update `products/api.py`**

Update the 3 dict-based tag values:

| Line | Old value | New value |
|---|---|---|
| 25 | `"tag": "product_not_found"` | `"tag": "ProductNotFoundError"` |
| 37 | `"tag": "product_hidden"` | `"tag": "ProductHiddenError"` |
| 43 | `"tag": "product_not_found"` | `"tag": "ProductNotFoundError"` |

- [ ] **Step 3: Update `products/tests.py`**

Update these 2 tag assertions:

| Line | Old value | New value |
|---|---|---|
| 157 | `"product_hidden"` | `"ProductHiddenError"` |
| 164 | `"product_not_found"` | `"ProductNotFoundError"` |

- [ ] **Step 4: Run product tests**

Run: `uv run manage.py test products -v2`

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add products/schemas.py products/api.py products/tests.py
git commit -m "refactor(products): remove manual tag declarations, use auto-derived tags"
```

---

### Task 5: Update blog app — API

**Files:**
- Modify: `blog/api.py` — remove `tag: Literal[...]` from class; update dict tag value

- [ ] **Step 1: Update `blog/api.py`**

Two changes:
1. Remove `tag: Literal["post_not_found"]` (line 14) from `PostNotFoundError`
2. Update the dict construction on line 48: `"tag": "post_not_found"` → `"tag": "PostNotFoundError"`

**Do NOT remove the `Literal` import** — it is still used by `DraftPostSchema` (line 19) and `PublishedPostSchema` (line 27).

After edits, `PostNotFoundError` becomes:

```python
class PostNotFoundError(AppError):
    id: int
```

And the dict on line 47-51 becomes:

```python
        return 404, {
            "tag": "PostNotFoundError",
            "detail": f"Post with id {post_id} not found",
            "id": post_id,
        }
```

- [ ] **Step 2: Run blog tests**

Run: `uv run manage.py test blog -v2`

Expected: Tests pass (blog/tests.py is empty, but run it to catch import errors).

- [ ] **Step 3: Commit**

```bash
git add blog/api.py
git commit -m "refactor(blog): remove manual tag declaration, use auto-derived tag"
```

---

### Task 6: Run full test suite

- [ ] **Step 1: Run all tests**

Run: `uv run manage.py test -v2`

Expected: All tests pass across core, orders, products, blog.

- [ ] **Step 2: Run type checker**

Run: `uv run basedpyright`

Expected: No new errors. If there are existing errors, ensure none are caused by this change.

---

### Task 7: Regenerate TypeScript client and update ts-pattern files

**Files:**
- Regenerate: `client/src/generated/`
- Modify: `client/src/ts-pattern/orders.ts`
- Modify: `client/src/ts-pattern/posts.ts`
- Modify: `client/src/ts-pattern/products.ts`

- [ ] **Step 1: Export OpenAPI schema and regenerate client**

Run from project root:

```bash
task generate:client
```

This runs `uv run manage.py export_openapi_schema > client/openapi.json`, then `bun install` and `bunx @hey-api/openapi-ts` in the client directory.

- [ ] **Step 2: Verify generated types reflect new tag values**

Run: `grep -n "tag.*Pending\|tag.*Shipped\|tag.*Cancelled\|tag.*OrderNot\|tag.*PostNot\|tag.*ProductNot\|tag.*ProductHid" client/src/generated/types.gen.ts`

Expected: Tag values should now be `"PendingOrderSchema"`, `"ShippedOrderSchema"`, etc. instead of the old semantic names.

- [ ] **Step 3: Update `client/src/ts-pattern/orders.ts`**

Update tag strings in `describeOrder`:

| Line | Old | New |
|---|---|---|
| 14 | `{ tag: "pending" }` | `{ tag: "PendingOrderSchema" }` |
| 18 | `{ tag: "shipped" }` | `{ tag: "ShippedOrderSchema" }` |
| 23 | `{ tag: "cancelled" }` | `{ tag: "CancelledOrderSchema" }` |

Update tag strings in `describeError`:

| Line | Old | New |
|---|---|---|
| 35 | `{ tag: "order_not_found" }` | `{ tag: "OrderNotFoundError" }` |
| 39 | `{ tag: "order_not_accessible" }` | `{ tag: "OrderNotAccessibleError" }` |

- [ ] **Step 4: Update `client/src/ts-pattern/posts.ts`**

Update tag strings (3 occurrences):

| Line | Old | New |
|---|---|---|
| 47 | `{ tag: "post_not_found" }` | `{ tag: "PostNotFoundError" }` |
| 67 | `{ tag: "post_not_found" }` | `{ tag: "PostNotFoundError" }` |

Also update the comment on line 41 that references `tag` as discriminant — no change needed, the comment is generic.

- [ ] **Step 5: Update `client/src/ts-pattern/products.ts`**

Update error tag strings only — product variant tags (`"available"`, `"out_of_stock"`) are from `ModelSchema`, not `TaggedSchema`, so leave them alone.

| Line | Old | New |
|---|---|---|
| 29 | `{ tag: "product_not_found" }` | `{ tag: "ProductNotFoundError" }` |
| 33 | `{ tag: "product_hidden" }` | `{ tag: "ProductHiddenError" }` |
| 50 | `{ tag: "product_not_found" }` | `{ tag: "ProductNotFoundError" }` |
| 51 | `{ tag: "product_hidden" }` | `{ tag: "ProductHiddenError" }` |

- [ ] **Step 6: Type-check TypeScript**

Run from `client/`:

```bash
bun run tsc --noEmit
```

Expected: No type errors. The generated types should match the new tag literals, making ts-pattern's `.exhaustive()` checks pass.

- [ ] **Step 7: Commit**

```bash
git add client/
git commit -m "refactor(client): regenerate types and update ts-pattern tag values"
```
