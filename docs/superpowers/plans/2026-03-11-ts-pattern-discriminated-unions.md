# ts-pattern Discriminated Unions Examples — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add type-level ts-pattern usage examples in `client/src/ts-pattern/posts.ts` demonstrating discriminated union pattern matching with the Hey API generated types.

**Architecture:** A single TypeScript file imports the Hey API generated types, defines a local `PostSchema` alias and placeholder error types, then demonstrates three progressively complex `match` examples. The type-checker (`tsc --noEmit`) is the verification step — no runtime execution needed.

**Tech Stack:** TypeScript, ts-pattern, Bun (package manager + type-checker runner), Hey API generated types (`client/src/types.gen.ts`)

**Spec:** `docs/superpowers/specs/2026-03-11-ts-pattern-discriminated-unions-design.md`

---

## Chunk 1: Add dependency and create examples file

### Task 1: Add ts-pattern to client/package.json

**Files:**
- Modify: `client/package.json`

- [ ] **Step 1: Add ts-pattern dependency**

In `client/package.json`, add `"ts-pattern": "latest"` to `dependencies`:

```json
{
  "name": "client",
  "private": true,
  "dependencies": {
    "@hey-api/client-fetch": "latest",
    "ts-pattern": "latest"
  },
  "devDependencies": {
    "@hey-api/openapi-ts": "latest",
    "@types/bun": "latest"
  },
  "module": "src/index.ts",
  "type": "module",
  "peerDependencies": {
    "typescript": "^5"
  }
}
```

- [ ] **Step 2: Install the dependency**

```bash
cd client && bun install
```

Expected: `bun install` completes, `ts-pattern` appears in `bun.lock`.

- [ ] **Step 3: Commit**

```bash
git add client/package.json client/bun.lock
git commit -m "chore: add ts-pattern dependency"
```

---

### Task 2: Create client/src/ts-pattern/posts.ts

**Files:**
- Create: `client/src/ts-pattern/posts.ts`

- [ ] **Step 1: Create the file**

Create `client/src/ts-pattern/posts.ts` with the following content:

```ts
import { match } from "ts-pattern";
import type {
  DraftPostSchema,
  PublishedPostSchema,
  PostNotFoundError,
} from "../types.gen";

// Local alias for the post union type.
// The Hey API generator expresses this inline in response types;
// we define it here for readability.
type PostSchema = DraftPostSchema | PublishedPostSchema;

// Placeholder error types — replace with generated types once backend is built.
// TODO: replace AuthError/ValidationError with generated types once backend is built
type AuthError = { type: "auth_error"; message: string };
type ValidationError = { type: "validation_error"; field: string; message: string };
type ApiError = PostNotFoundError | AuthError | ValidationError;

// Example 1: match on the PostSchema discriminated union only.
// Demonstrates: ts-pattern matches on the `status` discriminant field.
// The `status` field narrows the type — `p.updated` is only available on DraftPostSchema,
// `p.publish` only on PublishedPostSchema.
function describePost(post: PostSchema): string {
  return match(post)
    .with({ status: "DF" }, (p) => `Draft: ${p.title}, last updated ${p.updated}`)
    .with({ status: "PB" }, (p) => `Published: ${p.title} on ${p.publish ?? "TBD"}`)
    .exhaustive();
}

// Example 2: match on errors only.
// Demonstrates: multi-error matching — each error variant has its own `type` discriminant.
// `.exhaustive()` ensures all three error types are handled.
function describeError(error: ApiError): string {
  return match(error)
    .with({ type: "post_not_found" }, (e) => `Post ${e.id} not found: ${e.detail}`)
    .with({ type: "auth_error" }, (e) => `Auth error: ${e.message}`)
    .with({ type: "validation_error" }, (e) => `Validation error on ${e.field}: ${e.message}`)
    .exhaustive();
}

// Example 3: combined success + error match in one exhaustive chain.
// Demonstrates: the realistic usage pattern — handle all success variants and all error
// variants together. ts-pattern narrows each branch precisely.
// Remove a `.with(...)` arm to see the TypeScript compile error from `.exhaustive()`.
function handlePostResult(result: PostSchema | ApiError): string {
  return match(result)
    .with({ status: "DF" }, (p) => `Draft: ${p.title}`)
    .with({ status: "PB" }, (p) => `Published: ${p.title}`)
    .with({ type: "post_not_found" }, (e) => `Not found: post ${e.id} — ${e.detail}`)
    .with({ type: "auth_error" }, (e) => `Unauthorized: ${e.message}`)
    .with({ type: "validation_error" }, (e) => `Bad input on ${e.field}`)
    .exhaustive();
}
```

- [ ] **Step 2: Type-check**

```bash
cd client && node_modules/.bin/tsc --noEmit
```

Expected: no errors, no output.

If you see errors, the most likely causes:
- `ts-pattern` not installed — run `bun install` again
- Import path wrong — `../types.gen` resolves from `src/ts-pattern/` to `src/types.gen.ts` ✓
- `tsconfig.json` `include`/`exclude` misconfiguration — the default (no `include`) covers all `.ts` files under `client/`

- [ ] **Step 3: Commit**

```bash
git add client/src/ts-pattern/posts.ts
git commit -m "feat: add ts-pattern discriminated union examples"
```
