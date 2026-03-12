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

## Design

### Core Infrastructure (`core/schemas.py`)

Three reusable building blocks that every API in the project uses:

**`TaggedSchema`** — base class for all discriminated union schemas. Declares `tag: str` as a required field. All schemas that participate in a discriminated union inherit from this.

```python
class TaggedSchema(BaseModel):
    tag: str
```

**`AppError`** — updated to inherit from `TaggedSchema`. Renames the existing `type` field to `tag`. All error schemas inherit from this.

```python
class AppError(TaggedSchema):
    detail: str
```

**`tagged_union()`** — helper function that eliminates the `Annotated[Union[...], Field(discriminator="tag")]` boilerplate. Lives in `core` so every API can use it.

```python
def tagged_union(*schemas: type[TaggedSchema]):
    return Annotated[Union[schemas], Field(discriminator="tag")]
```

### Products API (`products/schemas.py`)

All four product schemas inherit from `TaggedSchema` or `AppError`.

**Success schemas** — the Django model keeps its `status` DB field untouched. The Pydantic schema maps it to `tag` via `validation_alias`:

```python
class AvailableProductSchema(TaggedSchema):
    tag: Literal["available"] = Field(validation_alias="status", default="available")
    id: int | None = None
    name: str
    description: str
    price: str
    stock_count: int | None = None

class OutOfStockProductSchema(TaggedSchema):
    tag: Literal["out_of_stock"] = Field(validation_alias="status", default="out_of_stock")
    id: int | None = None
    name: str
    description: str
    price: str
```

**Named success union** — generated via the `tagged_union` helper:

```python
ProductResult = tagged_union(AvailableProductSchema, OutOfStockProductSchema)
```

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

The response type for the detail endpoint changes from `ProductSchema` to `ProductResult`. Handler logic is untouched.

```python
@router.get("/{product_id}/", response={200: ProductResult, 404: ProductNotFoundError, 403: ProductHiddenError})
```

### OpenAPI Schema

Django Ninja + Pydantic v2 automatically generates a proper `oneOf` + `discriminator` block for `ProductResult` in the OpenAPI schema, with `tag` as the discriminator property. `ProductResult` appears as a named component in `components/schemas`.

### Client Generation

Running `task generate:client` regenerates the TypeScript client. hey-api generates:

- `ProductResult` — named discriminated union type
- `AvailableProductSchema`, `OutOfStockProductSchema` — now with `tag` instead of `status`
- `ProductNotFoundError`, `ProductHiddenError` — now with `tag` instead of `type`

### Frontend (`client/src/ts-pattern/products.ts`)

The manual type aliases are removed. Match patterns use `tag` consistently:

```typescript
// Before — manual, fragile:
type ProductSchema = AvailableProductSchema | OutOfStockProductSchema;
type ProductApiError = ProductNotFoundError | ProductHiddenError;

// After — nothing. Types come from generated client.
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

## Scalability Pattern

Every future API follows the same recipe:

1. All schemas inherit from `TaggedSchema` (or `AppError` for errors)
2. One named result union per resource: `PostResult = tagged_union(DraftPostSchema, PublishedPostSchema)`
3. Errors inherit `AppError`, narrow `tag` to a `Literal`
4. Endpoint response uses the named result type

No developer needs to touch `Annotated`, `Union`, `Field(discriminator=...)`, or define manual union aliases.

## Constraints

- Django model `status` field is not renamed — only the Pydantic schema layer changes
- HTTP status codes are preserved (200/403/404) — no flattening to a single status code
- hey-api configuration (`openapi-ts.config.ts`) is unchanged
- Pydantic v2 `_` prefix limitation: field is named `tag` in both Python and JSON (not `_tag`). The Effect.ts `_tag` convention uses underscore to signal internal/structural metadata — this is a JS ecosystem convention that does not apply meaningfully in a REST API context.
