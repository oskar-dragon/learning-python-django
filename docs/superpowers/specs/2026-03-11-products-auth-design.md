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
- `stock_count` (PositiveIntegerField) — raw inventory count; meaningful only when status is `available`
- `status` (CharField with choices: `available`, `out_of_stock`, `hidden`)
- `created`, `updated` (auto timestamps)

No user FK — products are not user-owned in this example.

## API Design

### Endpoints

Both endpoints require JWT authentication.

- `GET /api/products/` — returns list of products visible to the user (excludes hidden)
- `GET /api/products/{product_id}` — returns a single product or a domain error

### Discriminated Response Union

Two response schemas, discriminated on `status`:

```python
class AvailableProductSchema(ModelSchema):
    status: Literal["available"]
    # fields: id, name, description, price, stock_count, status

class OutOfStockProductSchema(ModelSchema):
    status: Literal["out_of_stock"]
    # fields: id, name, description, price, status (no stock_count)

ProductSchema = Annotated[
    AvailableProductSchema | OutOfStockProductSchema,
    Field(discriminator="status")
]
```

`hidden` products are never returned in a positive response — attempting to fetch one yields `ProductHiddenError`.

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

### Endpoint Response Map

```python
@router.get("/", response=list[ProductSchema], auth=JWTAuth())
def list_products(request): ...

@router.get("/{product_id}", response={200: ProductSchema, 404: ProductNotFoundError, 403: ProductHiddenError}, auth=JWTAuth())
def get_product(request, product_id: int): ...
```

### Backend Type Safety

The `get_product` endpoint uses a `match` statement on `product.status` to construct the response, giving basedpyright exhaustive coverage. Adding a new status value without handling it in the match causes a type error at check time.

```python
match product.status:
    case "available":
        return 200, product  # basedpyright narrows to AvailableProductSchema
    case "out_of_stock":
        return 200, product  # basedpyright narrows to OutOfStockProductSchema
    case "hidden":
        return 403, {"type": "product_hidden", "detail": "...", "id": product_id}
```

Auth is applied at the **router level** so all product endpoints are protected without repeating `auth=` per route.

## Authentication

### Library

`django-ninja-jwt` (with `ninja-extra` as a dependency). Provides a ready-made JWT controller and `JWTAuth()` class.

### API Change

`project/api.py` switches from `NinjaAPI` to `NinjaExtraAPI`. This is a drop-in superset — existing blog routes are unaffected.

### New Token Endpoints (from `NinjaJWTDefaultController`)

- `POST /api/token/pair` — username + password → access + refresh tokens
- `POST /api/token/refresh` — refresh token → new access token
- `POST /api/token/verify` — validates a token

### Product Router Auth

Auth applied at router level:

```python
router = Router(auth=JWTAuth())
```

`request.auth` is available in all product handlers, containing the decoded JWT claims.

## TypeScript Client

### Type Regeneration

Run the existing task — no pipeline changes needed:

```sh
task generate:client
```

This exports the updated OpenAPI schema and regenerates `types.gen.ts` and `sdk.gen.ts` with the new product types and error types.

### New File: `client/src/ts-pattern/products.ts`

Mirrors `client/src/ts-pattern/posts.ts`. Three examples building in complexity:

1. **Match on product union** — exhaustive match on `available` vs `out_of_stock`
2. **Match on error union** — exhaustive match on `product_not_found` vs `product_hidden`
3. **Combined result match** — one exhaustive chain covering all success and error variants (the realistic usage pattern)

### Auth Header

Show how to configure the `@hey-api/client-fetch` client with a Bearer token:

```typescript
import { client } from './client.gen';
client.setConfig({ headers: { Authorization: `Bearer ${accessToken}` } });
```

## Out of Scope

- User registration or password reset endpoints
- Token revocation / blacklisting
- Pagination on the products list
- Product creation/update/delete endpoints (read-only for now)
- Tests (covered separately when TDD skill is invoked at implementation time)
