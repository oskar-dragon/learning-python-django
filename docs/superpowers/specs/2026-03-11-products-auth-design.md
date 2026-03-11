# Products API + JWT Authentication — Design Spec

**Date:** 2026-03-11

## Goal

Add a `products` Django app with a type-safe, discriminated-union API demonstrating domain errors and discriminated responses on both backend and frontend. Add JWT authentication via `django-ninja-jwt` to protect the product endpoints. Regenerate the TypeScript client and add `ts-pattern` exhaustive matching examples.

## Context

The project already has a discriminated union pattern in `blog/api.py` (Draft vs Published posts) and a type-safe TypeScript client generated from the OpenAPI schema via `@hey-api/openapi-ts`. The `AppError` base schema in `core/schemas.py` is used for typed domain errors. This feature extends those patterns to a new domain and adds JWT auth as the next layer of the learning progression.

## New App: `products`

A new Django app `products/` alongside `blog/`. Keeps product concerns isolated.

### Product Model

Fields:
- `name` (CharField, max 255)
- `description` (TextField)
- `price` (DecimalField, max_digits=10, decimal_places=2)
- `stock_count` (PositiveIntegerField) — raw inventory count; only serialized when status is `available`
- `status` (CharField with choices: `available`, `out_of_stock`, `hidden`)
- `created`, `updated` (auto timestamps)

No user FK — products are not user-owned in this example.

A Django migration will be generated for this model.

## API Design

### Endpoints

Both endpoints require JWT authentication (applied at router level — see Authentication section).

- `GET /api/products/` — returns list of products, excluding hidden ones
- `GET /api/products/{product_id}` — returns a single product or a domain error

### Discriminated Response Union

Two response schemas, discriminated on `status`. Each schema uses an explicit `fields` list in `Meta` to control which model fields are serialized — `OutOfStockProductSchema` omits `stock_count`:

```python
class AvailableProductSchema(ModelSchema):
    status: Literal["available"]

    class Meta:
        model = Product
        fields = ["id", "name", "description", "price", "stock_count", "status"]

class OutOfStockProductSchema(ModelSchema):
    status: Literal["out_of_stock"]

    class Meta:
        model = Product
        fields = ["id", "name", "description", "price", "status"]
        # stock_count deliberately excluded — not meaningful when out of stock

ProductSchema = Annotated[
    AvailableProductSchema | OutOfStockProductSchema,
    Field(discriminator="status")
]
```

`hidden` products are never returned in a positive response — attempting to fetch one yields `ProductHiddenError`. The `list_products` endpoint filters them out with `.exclude(status="hidden")`.

Using `list[ProductSchema]` as the response type follows the same pattern as the existing `list[PostSchema]` in `blog/api.py`, which is confirmed to work with Django Ninja's OpenAPI schema generation.

### Discriminated Error Union

Two error schemas extending `AppError`, discriminated on `type`:

```python
class ProductNotFoundError(AppError):
    type: Literal["product_not_found"]
    id: int

class ProductHiddenError(AppError):
    type: Literal["product_hidden"]
    id: int
```

`ProductHiddenError` uses HTTP 403 rather than 404 — the user is authenticated but the product is restricted. This is a deliberate choice: 403 is accurate for "you don't have access," and since users must be authenticated to reach these endpoints, leaking the existence of a hidden product to an authenticated user is acceptable.

### Endpoint Response Map

Auth is applied at the router level (not per-endpoint). Endpoint declarations:

```python
@router.get("/", response=list[ProductSchema])
def list_products(request: HttpRequest): ...

@router.get("/{product_id}", response={200: ProductSchema, 404: ProductNotFoundError, 403: ProductHiddenError})
def get_product(request: HttpRequest, product_id: int): ...
```

### Backend Type Safety

The `get_product` implementation uses a `match` statement on `product.status`. Type safety here operates at the **API contract level**: the return type annotation enforces that every branch returns a type compatible with the declared response map. basedpyright will flag a branch that returns an incompatible type. The match statement itself operates on a plain string field, so basedpyright does not narrow `product` to a specific schema type within branches — the narrowing happens at serialization time in Django Ninja.

```python
match product.status:
    case "available":
        return 200, product
    case "out_of_stock":
        return 200, product
    case "hidden":
        return 403, {"type": "product_hidden", "detail": f"Product {product_id} is not available", "id": product_id}
    case _:
        # Unreachable if status choices are exhaustive, but makes the type checker happy
        return 404, {"type": "product_not_found", "detail": f"Product {product_id} not found", "id": product_id}
```

The real backend type safety benefit is demonstrated by the schema definitions: `Literal["available"]` and `Literal["out_of_stock"]` on the response schemas ensure the OpenAPI discriminator is generated correctly, which flows through to generated TypeScript types. The match statement communicates intent and makes future status additions visible.

## Authentication

### Library

`django-ninja-jwt` (with `ninja-extra` as a dependency). Provides a ready-made JWT controller and `JWTAuth()` class.

### API Change

`project/api.py` switches from `NinjaAPI` to `NinjaExtraAPI`. This is a drop-in superset — existing blog routes are unaffected. Add `ninja_extra` and `ninja_jwt` to `INSTALLED_APPS` in `settings.py`. The `NinjaJWTDefaultController` is registered on the API instance:

```python
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController

api = NinjaExtraAPI()
api.register_controllers(NinjaJWTDefaultController)
```

### New Token Endpoints (from `NinjaJWTDefaultController`)

Registered under the default prefix `/token/` relative to the API mount point (`/api/`):

- `POST /api/token/pair` — username + password → access + refresh tokens
- `POST /api/token/refresh` — refresh token → new access token
- `POST /api/token/verify` — validates a token

### Product Router Auth

Auth applied at router level — all product endpoints are automatically protected:

```python
from ninja_jwt.authentication import JWTAuth

router = Router(auth=JWTAuth())
```

`request.auth` is available in all product handlers, containing the decoded JWT claims (user ID, username, etc.).

## TypeScript Client

### Type Regeneration

Run the existing task — no pipeline changes needed:

```sh
task generate:client
```

This exports the updated OpenAPI schema and regenerates `types.gen.ts` and `sdk.gen.ts` with the new product types and error types.

### New File: `client/src/ts-pattern/products.ts`

Mirrors `client/src/ts-pattern/posts.ts`. Three examples building in complexity:

1. **Match on product union** — exhaustive match on `available` vs `out_of_stock`, accessing variant-specific fields
2. **Match on error union** — exhaustive match on `product_not_found` vs `product_hidden`
3. **Combined result match** — one exhaustive chain covering all success and error variants (the realistic usage pattern)

### Auth Header Configuration

The `@hey-api/client-fetch` client exported from `client.gen.ts` supports runtime reconfiguration. Show how to set the Bearer token before making authenticated requests:

```typescript
import { client } from './client.gen';

// Call after obtaining a token from POST /api/token/pair
client.setConfig({
    headers: { Authorization: `Bearer ${accessToken}` }
});
```

The exact method signature should be verified against the generated `client.gen.ts` and `@hey-api/client-fetch` source at implementation time, as it may vary by version.

## Out of Scope

- User registration or password reset endpoints
- Token revocation / blacklisting
- Pagination on the products list
- Product creation/update/delete endpoints (read-only for now)
- Tests (covered separately when TDD skill is invoked at implementation time)
