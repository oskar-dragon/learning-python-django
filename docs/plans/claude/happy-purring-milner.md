# Add `ctx` to ValidationError item schema

## Context

Manual testing revealed that the actual 422 ValidationError response includes a `ctx` field on each error item (e.g. `{"type":"enum","loc":[...],"msg":"...","ctx":{"expected":"..."}}`), but `_VALIDATION_ERROR_ITEM_SCHEMA` in `project/api.py` only declares `{type, loc, msg}`. This means `client/openapi.json` and the generated TypeScript types are missing `ctx`, so the client type doesn't reflect what the API actually returns.

## Approach

Add `ctx` as an optional field to `_VALIDATION_ERROR_ITEM_SCHEMA`, then regenerate the OpenAPI schema and TypeScript client.

## Steps

### 1. Update `_VALIDATION_ERROR_ITEM_SCHEMA` in `project/api.py`

Add `ctx` as an optional property (object with `additionalProperties`). Do **not** add it to `required`.

```python
_VALIDATION_ERROR_ITEM_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "loc": {"type": "array", "items": {"type": "string"}},
        "msg": {"type": "string"},
        "ctx": {"type": "object"},
    },
    "required": ["type", "loc", "msg"],
}
```

### 2. Regenerate schema and TypeScript client

```bash
task generate:client
```

This runs `manage.py export_openapi_schema > client/openapi.json` then `bunx @hey-api/openapi-ts`.

## Critical files

- `project/api.py` — `_VALIDATION_ERROR_ITEM_SCHEMA` at line 42

## Verification

Check that `client/src/generated/types.gen.ts` now includes `ctx?: Record<string, unknown>` (or similar) on the validation error item type.
