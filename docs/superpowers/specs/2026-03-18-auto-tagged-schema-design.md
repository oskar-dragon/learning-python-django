# Auto-derived Tags for TaggedSchema

## Problem

Every `TaggedSchema` subclass must manually declare `tag: Literal["some_value"]`, and callers must pass the tag string at construction time. This is redundant, error-prone, and verbose.

## Design

### Approach: `__init_subclass__` with keyword override

`TaggedSchema` uses `__init_subclass__` to auto-derive the `tag` field from the class name. An explicit override is available via a keyword argument on the class definition.

Inspired by Effect TS's `Data.TaggedError("HttpError")` pattern, where the class name is the tag — but leveraging Python's `cls.__name__` to avoid repeating it.

### Core mechanism

```python
from typing import Any, Literal

from ninja import Schema
from pydantic import ConfigDict


class TaggedSchema(Schema):
    model_config = ConfigDict(populate_by_name=True)
    tag: str  # base declares str; subclasses narrow to Literal

    def __init_subclass__(cls, tag: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        resolved_tag = tag or cls.__name__
        cls.__annotations__["tag"] = Literal[resolved_tag]
        cls.tag = resolved_tag  # class-level default so callers don't need to pass it
        cls.model_rebuild()
```

**Note:** We set `cls.__annotations__` for the `Literal` type, `cls.tag` for the default value, and call `model_rebuild()` to let Pydantic re-derive `model_fields` from annotations. This is safer than directly mutating `model_fields`, which may reference the parent's dict at `__init_subclass__` time. A spike is needed to verify this works correctly with `ninja.Schema`'s metaclass.

### Usage

```python
# Auto-derived tag: "PendingOrderSchema"
class PendingOrderSchema(TaggedSchema):
    id: int
    ...

# Explicit override: "custom"
class CustomSchema(TaggedSchema, tag="custom"):
    id: int
    ...
```

### AppError (intermediate class handling)

`AppError` extends `TaggedSchema`, which means `__init_subclass__` fires for `AppError` itself, auto-deriving `tag: Literal["AppError"]`. This is acceptable since `AppError` is never instantiated directly in production code — only its concrete subclasses are.

However, `core/tests.py` currently constructs `AppError` directly with `tag="test_error"`. These tests must be updated to either:
- Use a concrete test subclass of `AppError` instead, or
- Accept the `"AppError"` default tag

All `AppError` subclasses (`OrderNotFoundError`, `PostNotFoundError`, etc.) get their own auto-derived tags via the same mechanism.

### Construction

Tags are set as defaults, so callers no longer pass them:

```python
# Before
PendingOrderSchema(tag="pending", id=order.pk, ...)

# After
PendingOrderSchema(id=order.pk, ...)
```

This applies to both direct schema construction and dict-based construction in API handlers — dicts must use the new tag values to pass Pydantic's `Literal` validation.

## Affected files

1. **`core/schemas.py`** — Add `__init_subclass__` to `TaggedSchema`
2. **`core/tests.py`** — Update `AppError` direct construction (currently uses `tag="test_error"` which will fail `Literal["AppError"]` validation)
3. **`orders/schemas.py`** — Remove `tag: Literal[...]` from all 5 subclasses
4. **`orders/service.py`** — Remove `tag=...` from all 3 constructor calls in `_to_schema`
5. **`orders/exceptions.py`** — Remove `tag=...` from `OrderNotFoundError` and `OrderNotAccessibleError` constructor calls
6. **`blog/api.py`** — Remove `tag: Literal[...]` from `PostNotFoundError`; update dict construction on line 48 from `"post_not_found"` to `"PostNotFoundError"`
7. **`products/schemas.py`** — Remove `tag: Literal[...]` from `ProductNotFoundError` and `ProductHiddenError`. `AvailableProductSchema` and `OutOfStockProductSchema` are `ModelSchema` subclasses (not `TaggedSchema`) and stay as-is.
8. **`products/api.py`** — Update dict constructions: `"product_not_found"` → `"ProductNotFoundError"`, `"product_hidden"` → `"ProductHiddenError"` (lines 24-28, 36-40, 42-46)
9. **TypeScript client** — Regenerate client
10. **`client/src/ts-pattern/orders.ts`** — Update tag strings: `"pending"` → `"PendingOrderSchema"`, `"shipped"` → `"ShippedOrderSchema"`, `"cancelled"` → `"CancelledOrderSchema"`, `"order_not_found"` → `"OrderNotFoundError"`, `"order_not_accessible"` → `"OrderNotAccessibleError"`. Note: these files use generated types, so tag values may update automatically with client regeneration — verify.
11. **`client/src/ts-pattern/posts.ts`** — Update `"post_not_found"` → `"PostNotFoundError"`
12. **`client/src/ts-pattern/products.ts`** — Update `"product_not_found"` → `"ProductNotFoundError"`, `"product_hidden"` → `"ProductHiddenError"`. Product variant tags (`"available"`, `"out_of_stock"`) are from `ModelSchema` subclasses, not `TaggedSchema` — leave as-is.
13. **Tests** — Update expected tag values across all test files

## Tag value changes

This is a **breaking API change** — all tag values change from semantic names to class names. Any external consumers relying on the current tag strings will break. This is accepted as the project is in early development.

| Class | Old tag | New tag |
|---|---|---|
| `PendingOrderSchema` | `"pending"` | `"PendingOrderSchema"` |
| `ShippedOrderSchema` | `"shipped"` | `"ShippedOrderSchema"` |
| `CancelledOrderSchema` | `"cancelled"` | `"CancelledOrderSchema"` |
| `OrderNotFoundError` | `"order_not_found"` | `"OrderNotFoundError"` |
| `OrderNotAccessibleError` | `"order_not_accessible"` | `"OrderNotAccessibleError"` |
| `PostNotFoundError` | `"post_not_found"` | `"PostNotFoundError"` |
| `ProductNotFoundError` | `"product_not_found"` | `"ProductNotFoundError"` |
| `ProductHiddenError` | `"product_hidden"` | `"ProductHiddenError"` |

## Testing strategy

1. **`TaggedSchema` unit tests:**
   - Subclass without explicit tag gets `cls.__name__` as tag value and `Literal` type
   - Subclass with `tag="custom"` override gets the custom value
   - Tag is set as default (construction without passing `tag` works)
   - Tag value appears in serialized output (`.model_dump()` / `.model_json_schema()`)
   - Discriminated unions via `RootModel` still work correctly with auto-derived tags
   - Intermediate class (`AppError`) gets its own tag and doesn't break subclass tags

2. **Existing tests** — Update expected tag values to match new class names
