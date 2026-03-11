# TypeScript Client Generator — Design Spec

**Date:** 2026-03-11

## Goal

Add a Hey API TypeScript client generator so we can inspect how Django Ninja's discriminated unions and error responses translate to TypeScript types.

## Approach

Export the OpenAPI schema using Django Ninja's built-in management command, then generate a full Hey API client (types + fetch services) against that file. No running server required.

## Taskfile Task

A single `generate:client` task in `Taskfile.yml`:

1. `uv run manage.py export_openapi_schema --output client/openapi.json`
2. `cd client && bun install`
3. `cd client && bunx @hey-api/openapi-ts`

## Directory Layout

`client/` is a pre-committed directory. Its contents at commit time:

```
client/
  package.json              # devDeps: @hey-api/openapi-ts; deps: @hey-api/client-fetch
  bun.lock                  # committed
  openapi-ts.config.ts      # Hey API config
  openapi.json              # gitignored (generated artifact)
  src/                      # gitignored (generated artifact — filenames depend on Hey API version)
```

## Hey API Config (`openapi-ts.config.ts`)

```ts
import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "openapi.json",
  output: "src",
  plugins: ["@hey-api/client-fetch", "@hey-api/typescript", "@hey-api/sdk"],
});
```

## Gitignore Additions

Add to root `.gitignore`:

```
client/openapi.json
client/src/
```

## What We Expect to See

The `PostSchema` discriminated union (on `status`) should generate something like:

```ts
type PostSchema =
  | ({ status: "DF" } & DraftPostSchema)
  | ({ status: "PB" } & PublishedPostSchema);
```

The `get_post` endpoint (200 | 404) should generate typed response variants covering both `PostSchema` and `PostNotFoundError`.

## Out of Scope

- Frontend application
- CI integration for the generator
- Committing generated files
