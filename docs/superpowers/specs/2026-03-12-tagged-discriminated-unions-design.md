# Tagged Discriminated Unions Design

**Date:** 2026-03-12
**Status:** Approved

## Problem

The frontend manually defines union types that should be generated from the backend OpenAPI schema:

```typescript
// client/src/ts-pattern/products.ts — manual, fragile, must be repeated per resource
type ProductSchema = AvailableProductSchema | OutOfStockProductSchema;
type ProductApiError = ProductNotFoundError | ProductHiddenError;
```

Additionally, the current discriminant fields are inconsistent: success schemas use `status`, error schemas use `type`. This prevents exhaustive pattern matching with a single consistent discriminant.

## Goal

- Backend defines named discriminated union types
- OpenAPI schema exports them as named components
- hey-api generates them as TypeScript types
- Frontend imports and uses them without manual assembly
- All variants (success and error) use a consistent `tag` discriminant field

## Constraints

- Django model `status` field is not renamed — only the Pydantic schema layer changes
- HTTP status codes are preserved (200/403/404) — no flattening to a single status code
- hey-api configuration (`openapi-ts.config.ts`) is unchanged
- `tag` (no underscore) is used as the discriminant field. The Effect.ts `_tag` convention uses underscore to signal internal/structural metadata — this is a JS ecosystem convention that does not apply in a REST API context, and `_tag` cannot be a Pydantic model field name directly (underscore-prefixed names are treated as private attributes in Pydantic v2)

## Design

### Core Infrastructure (`core/schemas.py`)

Three reusable building blocks that every API in the project uses.

**`TaggedSchema`** — base class for all discriminated union schemas. Inherits from Django Ninja's `Schema` (which provides `from_attributes=True` and is itself a `BaseModel` subclass) so ORM objects can be serialized directly without extra config.

```python
from ninja import Schema
from pydantic import ConfigDict

class TaggedSchema(Schema):
    model_config = ConfigDict(populate_by_name=True)
    tag: str
```

`populate_by_name=True` ensures schemas can be constructed using either the field name (`tag=`) or the validation alias (`status=`). Without this, only the alias is accepted at construction time.

**`AppError`** — updated to inherit from `TaggedSchema`. Renames the existing `type` field to `tag`. All error schemas inherit from this.

```python
class AppError(TaggedSchema):
    detail: str
```

**`tagged_union()`** — helper that eliminates the `Annotated[Union[...], Field(discriminator="tag")]` boilerplate. `Union[schemas]` with a tuple argument is not valid Python; the correct approach is `functools.reduce`:

```python
import functools
from typing import Union, Annotated
from pydantic import Field

def tagged_union(*schemas: type[TaggedSchema]):
    union = functools.reduce(lambda a, b: Union[a, b], schemas)
    return Annotated[union, Field(discriminator="tag")]
```

### Schemas File (`products/schemas.py`)

Currently all product schemas live in `products/api.py`. As part of this change, they move to a new `products/schemas.py`. This is the right structure for scalability — all future resources follow the same `<app>/schemas.py` convention.

All four schemas are updated. **Note:** the current schemas use Django Ninja's `ModelSchema` (automatic field derivation from the Django model). We drop `ModelSchema` in favour of explicit `TaggedSchema`-based schemas. Tradeoff: fields must be declared explicitly, but we gain full control over discriminated union shape. If the `Product` model gains new fields, they will not automatically appear in the schema.

**Success schemas** — `validation_alias="status"` maps the Django ORM object's `status` attribute to the `tag` field at validation time. No `default` is set — this keeps `tag` in the OpenAPI `required` array, so hey-api generates `tag: 'available'` (required) rather than `tag?: 'available'` (optional). Requires `from_attributes=True` which is provided by inheriting from `ninja.Schema` via `TaggedSchema`.

Note: `populate_by_name=True` (set on `TaggedSchema`) means both `status=` and `tag=` are accepted at construction time.

`price` uses `Decimal` (matching the model's `DecimalField`) rather than `str` — Decimal serializes as a JSON string on the wire but is the semantically correct Python type. `stock_count` is `int` (not `int | None`) — the model declares `PositiveIntegerField(default=0)`, never nullable.

```python
class AvailableProductSchema(TaggedSchema):
    tag: Literal["available"] = Field(validation_alias="status")
    id: int
    name: str
    description: str
    price: Decimal
    stock_count: int

class OutOfStockProductSchema(TaggedSchema):
    tag: Literal["out_of_stock"] = Field(validation_alias="status")
    id: int
    name: str
    description: str
    price: Decimal
```

**Named success union:**

```python
ProductResult = tagged_union(AvailableProductSchema, OutOfStockProductSchema)
```

Whether `ProductResult` appears as a named component in the OpenAPI `components/schemas` section (vs. being inlined) depends on Django Ninja internals — **to be verified during implementation**. If it is inlined, hey-api will still generate a usable union type, but it may not be named `ProductResult`.

**Error schemas** — rename `type` → `tag`, inherit from `AppError`:

```python
class ProductNotFoundError(AppError):
    tag: Literal["product_not_found"] = "product_not_found"
    id: int

class ProductHiddenError(AppError):
    tag: Literal["product_hidden"] = "product_hidden"
    id: int
```

### Products Endpoint (`products/api.py`)

Two endpoints change:

**Detail endpoint** — response type changes from the inline union to `ProductResult`:

```python
@router.get("/{product_id}/", response={200: ProductResult, 404: ProductNotFoundError, 403: ProductHiddenError})
```

**List endpoint** — response type changes from `list[ProductSchema]` to `list[ProductResult]`:

```python
@router.get("/", response=list[ProductResult])
```

**Handler return dicts** — the error handler dicts must change `"type"` → `"tag"`:

```python
# Before:
return 404, {"type": "product_not_found", "detail": ..., "id": product_id}

# After:
return 404, {"tag": "product_not_found", "detail": ..., "id": product_id}
```

### Client Generation

Running `task generate:client` regenerates the TypeScript client. hey-api generates:

- `ProductResult` (or equivalent union) — named discriminated union type
- `AvailableProductSchema`, `OutOfStockProductSchema` — now with `tag` instead of `status`
- `ProductNotFoundError`, `ProductHiddenError` — now with `tag` instead of `type`

### Frontend (`client/src/ts-pattern/products.ts`)

The manual type aliases are removed. Match patterns use `tag` consistently:

```typescript
// Before — manual, fragile:
type ProductSchema = AvailableProductSchema | OutOfStockProductSchema;
type ProductApiError = ProductNotFoundError | ProductHiddenError;

// After — nothing. Types come from the generated client.
import type { ProductResult, ProductNotFoundError, ProductHiddenError } from "../generated";
```

Pattern matching:

```typescript
match(result)
  .with({ tag: "available" }, (p) => ...)
  .with({ tag: "out_of_stock" }, (p) => ...)
  .with({ tag: "product_not_found" }, (e) => ...)
  .with({ tag: "product_hidden" }, (e) => ...)
  .exhaustive()
```

### Blog App (`blog/api.py`) — partially in scope

Renaming `AppError.type → tag` is a cross-cutting change. The minimum required updates to avoid breakage:

- `PostNotFoundError` currently defines `type: Literal["post_not_found"]` — rename to `tag`
- The handler return dict `{"type": "post_not_found", ...}` — change `"type"` → `"tag"`

`DraftPostSchema` and `PublishedPostSchema` are **deferred**. Their `status` values are Django's abbreviated two-letter codes (`"DF"`, `"PB"`). Migrating them to `tag` requires remapping values (not just keys), which needs a `@field_validator` — not just `validation_alias`. This is a separate migration with its own scope. These schemas continue using `status` as their discriminant for now.

`posts.ts` placeholder types (`AuthError`, `ValidationError`) use `type` as their discriminant. These are local TODO stubs, not generated types. They remain unchanged here and will be replaced by generated types in a future task when the blog API gets full error handling.

`posts.ts` success match patterns (`{ status: "DF" }`, `{ status: "PB" }`) are also unchanged — they are tied to the deferred schema migration above.

### Tests

`products/tests.py` uses the old field names in three patterns — all must be updated:

- Equality assertions: `data["status"] == "available"` → `data["tag"] == "available"`
- Filter predicates (easy to miss): `next(p for p in results if p["status"] == "available")` → `p["tag"] == "available"`
- Error field: `data["type"] == "product_not_found"` → `data["tag"] == "product_not_found"`

Blog tests (if any) follow the same pattern for error fields.

## Scalability Pattern

Every future API follows the same recipe:

1. Schemas live in `<app>/schemas.py`, not in `api.py`
2. All schemas inherit from `TaggedSchema` (or `AppError` for errors)
3. One named result union per resource: `PostResult = tagged_union(DraftPostSchema, PublishedPostSchema)`
4. Errors inherit `AppError`, narrow `tag` to a `Literal`
5. Endpoint response uses the named result type
6. Handler error dicts use `"tag"` as the key

No developer needs to touch `Annotated`, `Union`, `Field(discriminator=...)`, or define manual union aliases.
