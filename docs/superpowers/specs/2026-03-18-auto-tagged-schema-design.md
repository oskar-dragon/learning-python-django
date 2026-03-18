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
from pydantic.fields import FieldInfo


class TaggedSchema(Schema):
    model_config = ConfigDict(populate_by_name=True)
    tag: str  # base declares str; subclasses narrow to Literal

    def __init_subclass__(cls, tag: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        resolved_tag = tag or cls.__name__
        cls.__annotations__["tag"] = Literal[resolved_tag]
        cls.model_fields["tag"] = FieldInfo(default=resolved_tag)
        cls.model_rebuild()
```

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

### AppError

`AppError` extends `TaggedSchema` and inherits the auto-tag behavior. No changes needed to `AppError` itself — all error subclasses get auto-tags automatically.

### Construction

Tags are set as defaults, so callers no longer pass them:

```python
# Before
PendingOrderSchema(tag="pending", id=order.pk, ...)

# After
PendingOrderSchema(id=order.pk, ...)
```

## Affected files

1. **`core/schemas.py`** — Add `__init_subclass__` to `TaggedSchema`
2. **`orders/schemas.py`** — Remove `tag: Literal[...]` from all 5 subclasses
3. **`orders/service.py`** — Remove `tag=...` from all 3 constructor calls in `_to_schema`
4. **`blog/api.py`** — Remove `tag: Literal[...]` from `PostNotFoundError`
5. **`products/schemas.py`** — Remove `tag: Literal[...]` from `ProductNotFoundError` and `ProductHiddenError`. `AvailableProductSchema` and `OutOfStockProductSchema` are `ModelSchema` subclasses (not `TaggedSchema`) and stay as-is.
6. **TypeScript client** — Regenerate; update `ts-pattern` matching files for new tag values
7. **Tests** — Update expected tag values

## Tag value changes

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

2. **Existing tests** — Update expected tag values to match new class names
