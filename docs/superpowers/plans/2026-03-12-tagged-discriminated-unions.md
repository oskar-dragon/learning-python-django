# Tagged Discriminated Unions Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manually-defined frontend union types with backend-generated discriminated unions, using a consistent `tag` field as the discriminant across all schemas.

**Architecture:** Add `TaggedSchema` + `tagged_union()` to `core/schemas.py` as the reusable foundation. Move product schemas to a new `products/schemas.py` file, rewriting them to use `TaggedSchema`. Update the blog's `PostNotFoundError` to stay consistent with the `AppError` rename. Regenerate the TypeScript client and remove manual type aliases from `products.ts`.

**Tech Stack:** Django Ninja, Pydantic v2, `@hey-api/openapi-ts`, ts-pattern

**Spec:** `docs/superpowers/specs/2026-03-12-tagged-discriminated-unions-design.md`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `core/schemas.py` | Modify | Add `TaggedSchema`, `tagged_union()`; update `AppError` |
| `products/schemas.py` | **Create** | Product schemas (moved + rewritten from `products/api.py`) |
| `products/api.py` | Modify | Remove inline schemas; import from `products/schemas.py`; update handler dicts |
| `products/tests.py` | Modify | `status`/`type` → `tag` in all assertions and filter predicates |
| `blog/api.py` | Modify | `PostNotFoundError.type` → `tag`; handler dict `"type"` → `"tag"` |
| `client/src/ts-pattern/products.ts` | Modify | Remove manual type aliases; update match discriminants to `tag` |

---

## Chunk 1: Core + Blog

### Task 1: Update product tests to expect `tag` (TDD red phase)

Update `products/tests.py` to assert the new `tag` field name before any implementation. Tests will fail — that's the point.

**Files:**
- Modify: `products/tests.py:88,94,141,148,157,164`

- [ ] **Step 1: Update filter predicates (lines 88, 94)**

```python
# Line 88 — was: p["status"] == "available"
available = next(p for p in response.json() if p["tag"] == "available")

# Line 94 — was: p["status"] == "out_of_stock"
oos = next(p for p in response.json() if p["tag"] == "out_of_stock")
```

- [ ] **Step 2: Update detail assertions (lines 141, 148)**

```python
# Line 141 — was: data["status"]
self.assertEqual(data["tag"], "available")

# Line 148 — was: data["status"]
self.assertEqual(data["tag"], "out_of_stock")
```

- [ ] **Step 3: Update error assertions (lines 157, 164)**

```python
# Line 157 — was: data["type"]
self.assertEqual(data["tag"], "product_hidden")

# Line 164 — was: data["type"]
self.assertEqual(data["tag"], "product_not_found")
```

- [ ] **Step 4: Run tests — confirm they fail**

```bash
uv run python manage.py test products --verbosity=2
```

Expected: multiple FAIL with `KeyError: 'tag'` or `AssertionError` — the API still returns `status`/`type`.

- [ ] **Step 5: Commit**

```bash
git add products/tests.py
git commit -m "test: update product tests to expect tag discriminant field"
```

---

### Task 2: Build core infrastructure

Replace `AppError` with a proper `TaggedSchema`-based hierarchy and add the `tagged_union()` helper.

**Files:**
- Modify: `core/schemas.py`

- [ ] **Step 1: Rewrite `core/schemas.py`**

Full file replacement — the existing file is 5 lines:

```python
import functools
from typing import Annotated, Union

from ninja import Schema
from pydantic import ConfigDict, Field


class TaggedSchema(Schema):
    """Base for all discriminated union schemas. All variants must declare tag: Literal[...]."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str


class AppError(TaggedSchema):
    """Base for all API error responses. Subclasses narrow tag to a Literal."""

    detail: str


def tagged_union(*schemas: type[TaggedSchema]):
    """Build a Pydantic discriminated union keyed on `tag`. Usage: tagged_union(A, B, C)."""
    union = functools.reduce(lambda a, b: Union[a, b], schemas)
    return Annotated[union, Field(discriminator="tag")]
```

- [ ] **Step 2: Verify no import errors**

```bash
uv run python -c "from core.schemas import TaggedSchema, AppError, tagged_union; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add core/schemas.py
git commit -m "feat: add TaggedSchema base class and tagged_union helper to core"
```

---

### Task 3: Fix blog error schema

`AppError` no longer has a `type` field — `PostNotFoundError` must be updated or it will fail at startup.

**Files:**
- Modify: `blog/api.py:13-15,47`

- [ ] **Step 1: Update `PostNotFoundError`**

```python
# blog/api.py — line 13-15
# Before:
class PostNotFoundError(AppError):
    type: Literal["post_not_found"]
    id: int

# After:
class PostNotFoundError(AppError):
    tag: Literal["post_not_found"] = "post_not_found"
    id: int
```

- [ ] **Step 2: Update handler return dict**

```python
# blog/api.py — line 47-50
# Before:
return 404, {
    "type": "post_not_found",
    "detail": f"Post with id {post_id} not found",
    "id": post_id,
}

# After:
return 404, {
    "tag": "post_not_found",
    "detail": f"Post with id {post_id} not found",
    "id": post_id,
}
```

- [ ] **Step 3: Run full test suite to catch any breakage**

`manage.py check` does not validate Pydantic schema construction — only a real test run does.

```bash
uv run python manage.py test --verbosity=2
```

Expected: all tests PASS. Products tests will still fail (that's correct — they're the TDD red phase from Task 1). Blog and any other tests must pass.

- [ ] **Step 4: Commit**

```bash
git add blog/api.py
git commit -m "fix: update PostNotFoundError and handler dict to use tag instead of type"
```

---

## Chunk 2: Products + Client

### Task 4: Create `products/schemas.py`

Move and rewrite all product schemas into a new file. This is where `ModelSchema` is replaced with explicit `TaggedSchema`-based schemas.

**Files:**
- Create: `products/schemas.py`

- [ ] **Step 1: Create `products/schemas.py`**

```python
from typing import Literal

from pydantic import Field

from core.schemas import AppError, TaggedSchema, tagged_union


class AvailableProductSchema(TaggedSchema):
    """Available product — has stock_count. tag maps from ORM's status field."""

    tag: Literal["available"] = Field(validation_alias="status", default="available")
    id: int
    name: str
    description: str
    price: str
    stock_count: int | None = None


class OutOfStockProductSchema(TaggedSchema):
    """Out-of-stock product — no stock_count. tag maps from ORM's status field."""

    tag: Literal["out_of_stock"] = Field(validation_alias="status", default="out_of_stock")
    id: int
    name: str
    description: str
    price: str


ProductResult = tagged_union(AvailableProductSchema, OutOfStockProductSchema)


class ProductNotFoundError(AppError):
    tag: Literal["product_not_found"] = "product_not_found"
    id: int


class ProductHiddenError(AppError):
    tag: Literal["product_hidden"] = "product_hidden"
    id: int
```

- [ ] **Step 2: Verify no import errors**

```bash
uv run python -c "from products.schemas import ProductResult, ProductNotFoundError, ProductHiddenError; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add products/schemas.py
git commit -m "feat: add products/schemas.py with TaggedSchema-based discriminated unions"
```

---

### Task 5: Update `products/api.py`

Replace inline schema definitions with imports from `products/schemas.py` and update handler dicts.

**Files:**
- Modify: `products/api.py`

- [ ] **Step 1: Rewrite `products/api.py`**

```python
from django.http import HttpRequest
from ninja import Router
from ninja_jwt.authentication import JWTAuth

from products.models import Product
from products.schemas import ProductHiddenError, ProductNotFoundError, ProductResult

router = Router(auth=JWTAuth())


@router.get("/", response=list[ProductResult])
def list_products(request: HttpRequest) -> list[Product]:
    return list(Product.objects.exclude(status=Product.Status.HIDDEN))


@router.get(
    "/{product_id}/",
    response={200: ProductResult, 404: ProductNotFoundError, 403: ProductHiddenError},
)
def get_product(request: HttpRequest, product_id: int) -> tuple[int, Product | dict[str, object]]:
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return 404, {
            "tag": "product_not_found",
            "detail": f"Product {product_id} not found",
            "id": product_id,
        }

    match product.status:
        case "available":
            return 200, product
        case "out_of_stock":
            return 200, product
        case "hidden":
            return 403, {
                "tag": "product_hidden",
                "detail": f"Product {product_id} is not available",
                "id": product_id,
            }
        case _:
            return 404, {
                "tag": "product_not_found",
                "detail": f"Product {product_id} not found",
                "id": product_id,
            }
```

- [ ] **Step 2: Run full test suite — all tests must pass**

```bash
uv run python manage.py test --verbosity=2
```

Expected: all tests PASS. If any test fails here, the schema or handler dict is wrong — check the `tag` field mapping and validation alias before proceeding.

- [ ] **Step 3: Verify OpenAPI schema generates cleanly**

```bash
uv run python manage.py export_openapi_schema | python -m json.tool | grep -A5 "ProductResult\|discriminator"
```

Expected: some output containing `discriminator` and/or `ProductResult`. Note whether `ProductResult` appears as a named component or is inlined (as per spec — either is acceptable).

- [ ] **Step 4: Commit**

```bash
git add products/api.py
git commit -m "feat: update products API to use ProductResult and tag discriminant"
```

---

### Task 6: Regenerate TypeScript client and update `products.ts`

**Files:**
- Modify: `client/src/ts-pattern/products.ts`
- Regenerated: `client/src/generated/` (all `.gen.ts` files)

- [ ] **Step 1: Regenerate the client**

```bash
task generate:client
```

Expected: exits cleanly, `client/src/generated/` files updated with `tag` instead of `status`/`type`.

- [ ] **Step 2: Verify `tag` appears in generated types**

```bash
grep -n "tag" client/src/generated/types.gen.ts | head -20
```

Expected: lines showing `tag: 'available'`, `tag: 'out_of_stock'`, `tag: 'product_not_found'`, `tag: 'product_hidden'`.

- [ ] **Step 3: Update `products.ts`**

Replace the entire file with the updated version. Key changes: remove manual type aliases, update all `.with({ status: ... })` and `.with({ type: ... })` patterns to `.with({ tag: ... })`.

```typescript
import { match } from "ts-pattern";
import type {
  AvailableProductSchema,
  OutOfStockProductSchema,
  ProductHiddenError,
  ProductNotFoundError,
} from "../generated/types.gen";

// ProductResult is the discriminated union of AvailableProductSchema | OutOfStockProductSchema.
// It is generated by hey-api from the backend's named union type — no manual definition needed.
// The tag field is the discriminant; TypeScript narrows per branch automatically.

// Example 1: match on success variants only.
// stock_count is only accessible when tag is "available" — TypeScript
// narrows the type per branch, so accessing it on the "out_of_stock" branch
// would be a compile error.
function describeProduct(product: AvailableProductSchema | OutOfStockProductSchema): string {
  return match(product)
    .with({ tag: "available" }, (p) => `Available: ${p.name} — ${p.stock_count} in stock at $${p.price}`)
    .with({ tag: "out_of_stock" }, (p) => `Out of stock: ${p.name} at $${p.price}`)
    .exhaustive();
}

// Example 2: match on errors only.
function describeError(error: ProductNotFoundError | ProductHiddenError): string {
  return match(error)
    .with({ tag: "product_not_found" }, (e) => `Product ${e.id} not found: ${e.detail}`)
    .with({ tag: "product_hidden" }, (e) => `Product ${e.id} is restricted: ${e.detail}`)
    .exhaustive();
}

// Example 3: combined success + error match in one exhaustive chain.
// Demonstrates the realistic usage pattern after calling productsApiGetProduct().
// Remove any .with(...) arm to see the TypeScript compile error from .exhaustive().
function handleProductResult(
  result: AvailableProductSchema | OutOfStockProductSchema | ProductNotFoundError | ProductHiddenError
): string {
  return match(result)
    .with({ tag: "available" }, (p) => `Available: ${p.name} (${p.stock_count} left)`)
    .with({ tag: "out_of_stock" }, (p) => `Sold out: ${p.name}`)
    .with({ tag: "product_not_found" }, (e) => `Not found: product ${e.id}`)
    .with({ tag: "product_hidden" }, (e) => `Restricted: product ${e.id}`)
    .exhaustive();
}

// Auth setup example: configure the hey-api client with a Bearer token
// before making authenticated requests to the products endpoints.
//
// import { client } from "../generated";
// client.setConfig({ headers: { Authorization: `Bearer ${token}` } });
```

- [ ] **Step 4: Check TypeScript compiles**

```bash
cd client && bunx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Run backend tests — full green phase confirmation**

```bash
uv run python manage.py test --verbosity=2
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add client/src/generated/ client/src/ts-pattern/products.ts
git commit -m "feat: regenerate client with tag discriminant and update products.ts"
```
