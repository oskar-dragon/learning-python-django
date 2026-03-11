# TypeScript Client Generator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `client/` directory with Hey API config and a `generate:client` Taskfile task that exports the OpenAPI schema and generates TypeScript types + a fetch client.

**Architecture:** Django Ninja's `export_openapi_schema` management command dumps the OpenAPI schema to `client/openapi.json`. Hey API's `@hey-api/openapi-ts` reads that file and generates TypeScript types and SDK into `client/src/`. Both artifacts are gitignored. The Taskfile task orchestrates the whole flow. All `uv run manage.py` commands must be run from the repo root (where `manage.py` lives).

**Tech Stack:** Django Ninja, Bun, `@hey-api/openapi-ts`, `@hey-api/client-fetch`, `@hey-api/typescript`, `@hey-api/sdk`

---

> **Note on testing:** This feature is pure tooling configuration — no business logic. There is nothing to unit test. Verification is done by running the generator and inspecting its output.

---

## Chunk 1: Client directory and Taskfile task

### Task 1: Create `client/package.json`

**Files:**
- Create: `client/package.json`

- [ ] **Step 1: Create the file**

`@hey-api/client-fetch` is a runtime dependency (used by the generated client). The codegen plugins (`@hey-api/openapi-ts`, `@hey-api/typescript`, `@hey-api/sdk`) are dev dependencies.

```json
{
  "name": "client",
  "private": true,
  "dependencies": {
    "@hey-api/client-fetch": "latest"
  },
  "devDependencies": {
    "@hey-api/openapi-ts": "latest",
    "@hey-api/typescript": "latest",
    "@hey-api/sdk": "latest"
  }
}
```

- [ ] **Step 2: Run `bun install` inside `client/` to generate the lockfile**

Run from the repo root:

```bash
cd client && bun install
```

Expected: `bun.lock` created, `node_modules/` created.

- [ ] **Step 3: Commit**

```bash
git add client/package.json client/bun.lock
git commit -m "chore: add client package.json with hey-api dependencies"
```

---

### Task 2: Create `client/openapi-ts.config.ts`

**Files:**
- Create: `client/openapi-ts.config.ts`

- [ ] **Step 1: Create the config file**

```ts
import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "openapi.json",
  output: "src",
  plugins: ["@hey-api/client-fetch", "@hey-api/typescript", "@hey-api/sdk"],
});
```

- [ ] **Step 2: Commit**

```bash
git add client/openapi-ts.config.ts
git commit -m "chore: add hey-api openapi-ts config"
```

---

### Task 3: Update `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append the generated artifacts to `.gitignore`**

Add to the end of `.gitignore`:

```
# Hey API client generator artifacts
client/openapi.json
client/src/
client/node_modules/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore hey-api generated artifacts"
```

---

### Task 4: Add `generate:client` task to `Taskfile.yml`

**Files:**
- Modify: `Taskfile.yml`

- [ ] **Step 1: Add the task**

Add a new task after the existing `setup` task. Note: each `cmds` entry runs as an independent subshell from the repo root — the `uv run manage.py` step runs at the root, and the `cd client && ...` steps change into the client directory only for that command.

```yaml
  generate:client:
    desc: Export OpenAPI schema and generate TypeScript client
    cmds:
      - uv run manage.py export_openapi_schema > client/openapi.json
      - cd client && bun install
      - cd client && bunx @hey-api/openapi-ts
```

- [ ] **Step 2: Commit**

```bash
git add Taskfile.yml
git commit -m "chore: add generate:client Taskfile task"
```

---

### Task 5: Run the generator and verify

**Must be run from the repo root.**

- [ ] **Step 1: Run the task**

```bash
task generate:client
```

Expected output:
- `export_openapi_schema` writes the OpenAPI JSON to stdout, redirected into `client/openapi.json`
- `bun install` completes quickly (already installed)
- `bunx @hey-api/openapi-ts` runs and writes files into `client/src/`

If the first step fails with an import error, check that you're running from the repo root and that the `.env` file exists (copy from `.env.example` if needed).

- [ ] **Step 2: Inspect the generated output**

```bash
ls client/src/
cat client/src/types.gen.ts
```

The existing blog API already has discriminated unions, so look for:
- `PostSchema` as a union of `DraftPostSchema` and `PublishedPostSchema`, discriminated on `status`
- `PostNotFoundError` type (the 404 response body)
- Typed SDK functions for the blog endpoints with 200/404 response variants

- [ ] **Step 3: Verify `.gitignore` is working**

```bash
git status
```

Expected: `client/openapi.json`, `client/src/`, and `client/node_modules/` do NOT appear as untracked files.
