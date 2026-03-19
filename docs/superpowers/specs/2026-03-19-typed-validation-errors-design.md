# Typed Validation Errors Design

## Problem

Validation errors return a flat array of `{ type, loc, msg }` items. On the frontend, there's no type-safe way to access errors for a specific field — you have to iterate the array and match on `loc` strings manually.

## Goals

- Frontend gets autocomplete on field names when accessing validation errors (e.g., `fields.query?.status?.msg`)
- Backend response shape stays exactly as-is — flat `errors` array, no transformation
- Per-endpoint validation error types generated automatically from existing request schemas — no manual boilerplate
- A typed frontend utility transforms the flat array into a field-keyed object at the call site

## Design

### 1. Backend Response Shape (no change)

The `handle_validation_error` handler continues to return the current shape:

```json
{
    "tag": "ValidationError",
    "detail": "Validation error",
    "errors": [
        { "type": "enum", "loc": ["query", "status"], "msg": "Input should be..." }
    ]
}
```

No backend response changes.

### 2. Per-Endpoint OpenAPI Schema for 422

`TaggedErrorAPI.get_openapi_schema()` currently injects a single global `ValidationError` schema (with `errors: Array<{type, loc, msg}>`) on every endpoint. This changes to generate a **per-endpoint** 422 schema that includes a `fields` property describing which fields can produce validation errors, grouped by param source.

For each endpoint, the override:

1. Iterates `self._routers` → `router.path_operations` → `PathView.operations` to get each `Operation` object (the serialized OpenAPI dict doesn't contain operation references, so we must traverse the router tree)
2. For each operation, reads `operation.models` — the list of parameter models Ninja already parsed
3. Reads `__ninja_param_source__` (e.g., `"query"`, `"body"`, `"path"`) from each model
4. Reads field names via `__ninja_flatten_map__` keys (for query/path/header/cookie params) or `model_fields` keys (for body params). Note: `__ninja_flatten_map__` keys are the external-facing parameter names (e.g., `status`, `q`), not internal ORM lookup names — this is the correct source for the schema
5. Matches each operation to its serialized path entry (using the path and method) and injects a per-endpoint 422 schema with both the flat `errors` array AND a `fields` object describing available field names
6. Includes both query and path params in `fields` — path params can fail validation too (e.g., passing a string where an int is expected)

The generated schema for `GET /api/orders/` would look like:

```json
{
    "type": "object",
    "properties": {
        "tag": { "type": "string", "const": "ValidationError" },
        "detail": { "type": "string" },
        "errors": {
            "type": "array",
            "items": { "$ref": "#/components/schemas/ValidationErrorItem" }
        },
        "fields": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "object",
                    "properties": {
                        "status": { "$ref": "#/components/schemas/ValidationErrorItem" },
                        "q": { "$ref": "#/components/schemas/ValidationErrorItem" },
                        "min_total": { "$ref": "#/components/schemas/ValidationErrorItem" },
                        "max_total": { "$ref": "#/components/schemas/ValidationErrorItem" }
                    }
                }
            }
        }
    },
    "required": ["tag", "detail", "errors"]
}
```

`ValidationErrorItem` is registered once in `components/schemas`:

```json
{
    "type": "object",
    "properties": {
        "type": { "type": "string" },
        "loc": { "type": "array", "items": { "oneOf": [{"type": "string"}, {"type": "integer"}] } },
        "msg": { "type": "string" }
    },
    "required": ["type", "loc", "msg"]
}
```

The `fields` property is **not required** and **not returned by the backend** — it exists only in the OpenAPI schema to inform codegen of the available field names. This is a schema-only construct that gives TypeScript the type information it needs.

The per-endpoint 422 schemas are inlined in each endpoint's responses (not registered in `components/schemas`). `@hey-api/openapi-ts` generates distinct TypeScript types from inline schemas using the operation ID — e.g., `OrdersApiListOrdersErrors[422]` — which gives us per-endpoint types without manual naming.

### 3. Generated TypeScript Types

For `GET /api/orders/` (query params only) the codegen produces:

```typescript
422: {
    tag: 'ValidationError';
    detail: string;
    errors: Array<ValidationErrorItem>;
    fields?: {
        query?: {
            status?: ValidationErrorItem;
            q?: ValidationErrorItem;
            min_total?: ValidationErrorItem;
            max_total?: ValidationErrorItem;
        };
    };
};
```

For `GET /api/orders/{order_id}/` (query + path params):

```typescript
422: {
    tag: 'ValidationError';
    detail: string;
    errors: Array<ValidationErrorItem>;
    fields?: {
        path?: {
            order_id?: ValidationErrorItem;
        };
    };
};
```

For `GET /api/blog/posts/` (no params):

```typescript
422: {
    tag: 'ValidationError';
    detail: string;
    errors: Array<ValidationErrorItem>;
};
```

### 4. Frontend Utility: `toFieldErrors`

A utility function transforms the flat `errors` array into a field-keyed object matching the `fields` type:

```typescript
type ValidationErrorItem = { type: string; loc: (string | number)[]; msg: string };

function toFieldErrors<TFields>(
    errors: ValidationErrorItem[]
): TFields {
    const result: Record<string, Record<string, ValidationErrorItem>> = {};
    for (const error of errors) {
        const [source, field] = error.loc;
        if (typeof source === "string" && (typeof field === "string" || typeof field === "number")) {
            const fieldKey = String(field);
            result[source] ??= {};
            // First error per field wins — subsequent errors for the same field are dropped
            result[source][fieldKey] ??= error;
        }
    }
    return result as TFields;
}
```

The utility groups by the first two `loc` elements (param source and field name), regardless of how deep the `loc` path goes. For list params (e.g., `?ids=1&ids=foo`) where `loc` is `["query", "ids", 0]`, or nested body fields where `loc` is `["body", "address", "street"]`, the error is keyed by the top-level field name (`ids`, `address`). First error per field wins.

### 5. Frontend Usage

```typescript
import type { OrdersApiListOrdersErrors } from "../generated/types.gen";

type OrdersValidationFields = NonNullable<OrdersApiListOrdersErrors[422]["fields"]>;

.with({ tag: "ValidationError" }, (e) => {
    const fields = toFieldErrors<OrdersValidationFields>(e.errors);
    fields.query?.status?.msg     // autocomplete, typed
    fields.query?.q?.msg          // works
    fields.query?.bogus           // compile error
})
```

## What Changes

| Component | Before | After |
|-----------|--------|-------|
| Backend response | Flat `errors` array | No change |
| OpenAPI 422 schema | Global, same for all endpoints | Per-endpoint, includes `fields` with field names |
| Generated TypeScript | `errors: Array<{type, loc, msg}>` | Same, plus optional `fields` with typed field names |
| Frontend access | Iterate array, match on `loc` strings | `toFieldErrors()` utility with autocomplete |

## What Stays the Same

- `handle_validation_error` handler — no changes
- Domain errors (400) — unchanged
- Auth errors (401/403) — still globally injected
- InternalError (500) — still globally injected
- All other exception handlers — unchanged

## Files to Change

- `project/api.py` — modify `TaggedErrorAPI.get_openapi_schema()` to generate per-endpoint 422 schemas with `fields` property; add `ValidationErrorItem` to `components/schemas`
- `project/tests.py` — update `OpenAPISchemaInjectionTest` to verify per-endpoint field names in 422 schema
- `client/src/ts-pattern/errors.ts` — new file with `toFieldErrors` utility
- `client/src/ts-pattern/orders.ts` — update example to demonstrate `toFieldErrors` usage
- `client/` — regenerate types
