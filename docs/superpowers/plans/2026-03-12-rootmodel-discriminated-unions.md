# RootModel Discriminated Unions Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `tagged_union()` type alias with `RootModel` subclasses and `TaggedModelSchema` so that hey-api generates named, clean discriminated union types in TypeScript.

**Architecture:** Add `TaggedModelSchema` to `core/schemas.py`, migrate product schemas from manual field declarations to `ModelSchema`-based `Meta.exclude`, replace the `tagged_union()` type alias with a `RootModel` subclass, remove `tagged_union()`, regenerate the TypeScript client, and verify the output.

**Tech Stack:** Django Ninja, Pydantic v2 (`RootModel`, `ModelSchema`), `@hey-api/openapi-ts`, ts-pattern

**Spec:** `docs/superpowers/specs/2026-03-12-rootmodel-discriminated-unions-design.md`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `core/schemas.py` | Modify | Add `TaggedModelSchema`; remove `tagged_union()` |
| `products/schemas.py` | Modify | Switch to `TaggedModelSchema` + `Meta.exclude`; `RootModel` for `ProductResult` |
| `products/api.py` | Verify | Already imports `ProductResult` — no handler changes needed. Verify `RootModel` serializes correctly via existing tests. |
| `products/tests.py` | None | Existing tests verify the API contract; they pass unchanged |
| `client/openapi.json` | Regenerated | Updated OpenAPI spec with named `ProductResult` component |
| `client/src/generated/` | Regenerated | Updated TypeScript types |
| `client/src/ts-pattern/products.ts` | Modify | Import `ProductResult` as named type |

---

## Chunk 1: Backend Changes

### Task 1: Add `TaggedModelSchema` to core

Add the new base class alongside the existing `TaggedSchema`. This is additive — nothing breaks.

**Files:**
- Modify: `core/schemas.py`

- [ ] **Step 1: Add `TaggedModelSchema` class**

Add after `AppError`, before `tagged_union()`:

```python
from ninja import ModelSchema, Schema

# ... existing TaggedSchema and AppError ...

class TaggedModelSchema(ModelSchema):
    """Base for discriminated union schemas backed by a Django model. Fields derived via Meta."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str
```

Note: the `ninja` import line must be updated to `from ninja import ModelSchema, Schema`.

- [ ] **Step 2: Verify no import errors**

```bash
uv run python -c "from core.schemas import TaggedModelSchema; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run full test suite**

```bash
uv run python manage.py test --verbosity=2
```

Expected: all tests PASS (additive change, nothing uses `TaggedModelSchema` yet).

- [ ] **Step 4: Commit**

```bash
git add core/schemas.py
git commit -m "feat: add TaggedModelSchema base class for model-backed discriminated unions"
```

---

### Task 2: Migrate product schemas to `TaggedModelSchema` + `RootModel`

Replace manual field declarations with `ModelSchema`-based `Meta.exclude` and swap the `tagged_union()` type alias for a `RootModel` subclass.

**Files:**
- Modify: `products/schemas.py`

- [ ] **Step 1: Rewrite `products/schemas.py`**

Full file replacement:

```python
from typing import Literal

from pydantic import Field, RootModel

from core.schemas import AppError, TaggedModelSchema
from products.models import Product


class AvailableProductSchema(TaggedModelSchema):
    """Available product — has stock_count. tag maps from ORM's status field."""

    tag: Literal["available"] = Field(validation_alias="status")

    class Meta:
        model = Product
        exclude = ["status", "created", "updated"]


class OutOfStockProductSchema(TaggedModelSchema):
    """Out-of-stock product — no stock_count. tag maps from ORM's status field."""

    tag: Literal["out_of_stock"] = Field(validation_alias="status")

    class Meta:
        model = Product
        exclude = ["status", "stock_count", "created", "updated"]


class ProductResult(RootModel[AvailableProductSchema | OutOfStockProductSchema]):
    """Named discriminated union for product success responses."""

    pass


class ProductNotFoundError(AppError):
    tag: Literal["product_not_found"]
    id: int


class ProductHiddenError(AppError):
    tag: Literal["product_hidden"]
    id: int
```

- [ ] **Step 2: Verify schema construction works**

```bash
uv run python -c "
from products.schemas import ProductResult, AvailableProductSchema, OutOfStockProductSchema
print('AvailableProductSchema fields:', list(AvailableProductSchema.model_fields.keys()))
print('OutOfStockProductSchema fields:', list(OutOfStockProductSchema.model_fields.keys()))
print('ProductResult type:', type(ProductResult))
print('OK')
"
```

Expected: `AvailableProductSchema` includes `tag, id, name, description, price, stock_count`. `OutOfStockProductSchema` includes `tag, id, name, description, price` (no `stock_count`). Neither includes `status`, `created`, or `updated`.

- [ ] **Step 3: Run full test suite**

```bash
uv run python manage.py test --verbosity=2
```

Expected: all tests PASS. The API contract is unchanged — responses still have the same `tag`, field set, and HTTP status codes. **Critical:** `products/api.py` uses `list[ProductResult]` and `{200: ProductResult, ...}` where `ProductResult` is now a `RootModel` subclass. The existing tests verify the exact JSON shape (field presence, `tag` values, HTTP status codes). If `RootModel` causes serialization issues (e.g., extra `root` key wrapping), the tests will catch it here. If tests fail, investigate Django Ninja's `RootModel` handling before proceeding.

- [ ] **Step 4: Commit**

```bash
git add products/schemas.py
git commit -m "feat: migrate product schemas to TaggedModelSchema + RootModel"
```

---

### Task 3: Remove `tagged_union()` from core

Now that no code uses `tagged_union()`, remove it.

**Files:**
- Modify: `core/schemas.py`

- [ ] **Step 1: Remove `tagged_union()` and its imports**

Remove the `tagged_union` function and the `functools`, `Annotated`, `Union`, and `Field` imports that are no longer needed. The final file should be:

```python
from ninja import ModelSchema, Schema
from pydantic import ConfigDict


class TaggedSchema(Schema):
    """Base for all discriminated union schemas. All variants must declare tag: Literal[...]."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str


class AppError(TaggedSchema):
    """Base for all API error responses. Subclasses narrow tag to a Literal."""

    detail: str


class TaggedModelSchema(ModelSchema):
    """Base for discriminated union schemas backed by a Django model. Fields derived via Meta."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str
```

- [ ] **Step 2: Verify no import errors across the project**

```bash
uv run python -c "from core.schemas import TaggedSchema, AppError, TaggedModelSchema; print('OK')"
uv run python -c "from products.schemas import ProductResult; print('OK')"
uv run python -c "from products.api import router; print('OK')"
```

Expected: all print `OK`. No code imports `tagged_union` anymore.

- [ ] **Step 3: Run full test suite**

```bash
uv run python manage.py test --verbosity=2
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add core/schemas.py
git commit -m "refactor: remove tagged_union() helper — replaced by RootModel subclasses"
```

---

### Task 4: Verify OpenAPI output

Confirm that `ProductResult` appears as a named `$ref` component (the empirical verification from the spec).

**Files:**
- None modified — verification only

- [ ] **Step 1: Export and inspect the OpenAPI schema**

```bash
uv run manage.py export_openapi_schema | python -m json.tool > /tmp/openapi-check.json
```

Check for `ProductResult` as a named component:

```bash
python -c "
import json
with open('/tmp/openapi-check.json') as f:
    spec = json.load(f)
schemas = spec.get('components', {}).get('schemas', {})
print('Named components:', list(schemas.keys()))
print()
if 'ProductResult' in schemas:
    print('ProductResult schema:', json.dumps(schemas['ProductResult'], indent=2))
else:
    print('WARNING: ProductResult is NOT a named component — check inline references')
print()
# Check how the detail endpoint references ProductResult
detail = spec['paths']['/api/products/{product_id}/']['get']['responses']['200']
print('Detail 200 response:', json.dumps(detail, indent=2))
"
```

Expected: `ProductResult` appears in `components/schemas` with `anyOf` (NOT `oneOf`) containing `$ref`s to `AvailableProductSchema` and `OutOfStockProductSchema`. No `discriminator` key in the `ProductResult` schema — this is critical because `anyOf` without `discriminator` is what makes hey-api produce clean unions instead of intersection noise. The detail endpoint's 200 response references `$ref: #/components/schemas/ProductResult`.

**If `ProductResult` is NOT a named component:** Django Ninja inlined the `RootModel`. Stop here and investigate — the design assumed this would work. Check Django Ninja docs for how to register a `RootModel` as a named schema, or consider alternative approaches (e.g., custom schema registration).

- [ ] **Step 2: Commit the updated OpenAPI spec**

```bash
uv run manage.py export_openapi_schema > client/openapi.json
git add client/openapi.json
git commit -m "chore: regenerate openapi.json with RootModel-based ProductResult"
```

---

## Chunk 2: Client Regeneration & Frontend

### Task 5: Regenerate TypeScript client and verify types

**Files:**
- Regenerated: `client/src/generated/` (all `.gen.ts` files)

- [ ] **Step 1: Regenerate the client**

```bash
task generate:client
```

Expected: exits cleanly, `client/src/generated/` files updated.

- [ ] **Step 2: Verify `ProductResult` is a named type**

```bash
grep -n "ProductResult" client/src/generated/types.gen.ts
```

Expected: a line like `export type ProductResult = AvailableProductSchema | OutOfStockProductSchema;` — a clean union with no intersection pattern (`{ tag: '...' } &`).

**If the generated type still has intersection noise** (e.g., `({ tag: 'available' } & AvailableProductSchema) | ...`): STOP and investigate. This means the OpenAPI spec still has `oneOf + discriminator` instead of `anyOf`. Go back to Task 4 and check the OpenAPI output. The design relies on `anyOf` without `discriminator` to suppress the intersections.

- [ ] **Step 3: Verify individual schemas still have `tag` as literal**

```bash
grep -A2 "tag:" client/src/generated/types.gen.ts
```

Expected: `tag: 'available'` on `AvailableProductSchema`, `tag: 'out_of_stock'` on `OutOfStockProductSchema`, etc.

- [ ] **Step 4: Verify response types reference `ProductResult`**

```bash
grep -A5 "ProductsApiGetProductResponses" client/src/generated/types.gen.ts
```

Expected: the 200 response type is `ProductResult` (not an inline union).

- [ ] **Step 5: Commit**

```bash
git add client/src/generated/
git commit -m "feat: regenerate client with named ProductResult union type"
```

---

### Task 6: Update `products.ts` to use `ProductResult` import

Now that `ProductResult` is a named generated type, import and use it directly.

**Files:**
- Modify: `client/src/ts-pattern/products.ts`

- [ ] **Step 1: Update imports and type annotations**

Replace the file contents:

```typescript
import { match } from "ts-pattern";
import type {
  ProductResult,
  ProductHiddenError,
  ProductNotFoundError,
  ProductsApiGetProductError,
} from "../generated/types.gen";

// Example 1: match on success variants only.
// stock_count is only accessible when tag is "available" — TypeScript
// narrows the type per branch, so accessing it on the "out_of_stock" branch
// would be a compile error.
function describeProduct(product: ProductResult): string {
  return match(product)
    .with({ tag: "available" }, (p) => `Available: ${p.name} — ${p.stock_count} in stock at $${p.price}`)
    .with({ tag: "out_of_stock" }, (p) => `Out of stock: ${p.name} at $${p.price}`)
    .exhaustive();
}

// Example 2: match on errors only.
// Uses the generated error union type — no manual assembly.
function describeError(error: ProductsApiGetProductError): string {
  return match(error)
    .with({ tag: "product_not_found" }, (e) => `Product ${e.id} not found: ${e.detail}`)
    .with({ tag: "product_hidden" }, (e) => `Product ${e.id} is restricted: ${e.detail}`)
    .exhaustive();
}

// Example 3: combined success + error match in one exhaustive chain.
// Demonstrates the realistic usage pattern after calling productsApiGetProduct().
function handleProductResult(
  result: ProductResult | ProductsApiGetProductError
): string {
  return match(result)
    .with({ tag: "available" }, (p) => `Available: ${p.name} (${p.stock_count} left)`)
    .with({ tag: "out_of_stock" }, (p) => `Sold out: ${p.name}`)
    .with({ tag: "product_not_found" }, (e) => `Not found: product ${e.id}`)
    .with({ tag: "product_hidden" }, (e) => `Restricted: product ${e.id}`)
    .exhaustive();
}

// Auth setup: configure the hey-api client with a Bearer token
// before making authenticated requests to the products endpoints.
//
// import { client } from "../generated";
// client.setConfig({ headers: { Authorization: `Bearer ${token}` } });
```

- [ ] **Step 2: Check TypeScript compiles**

```bash
cd client && bunx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Run backend tests — full green confirmation**

```bash
uv run python manage.py test --verbosity=2
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add client/src/ts-pattern/products.ts
git commit -m "feat: use generated ProductResult and ProductsApiGetProductError types in products.ts"
```
