# ts-pattern Discriminated Unions Examples — Design Spec

**Date:** 2026-03-11

## Goal

Add type-level usage examples in `client/src/ts-pattern/posts.ts` showing how to use `ts-pattern` with the discriminated union types produced by the Hey API client generator.

## Context

The Django Ninja backend exposes two post schemas — `DraftPostSchema` (status `'DF'`) and `PublishedPostSchema` (status `'PB'`) — and a `PostNotFoundError`. The Hey API generator produces these as named types in `client/src/types.gen.ts`. The generated response types express the union inline as `DraftPostSchema | PublishedPostSchema`; the examples define a local alias `type PostSchema = DraftPostSchema | PublishedPostSchema` for readability.

The backend will eventually have richer error types (auth, validation, etc.). Placeholder types fill that gap for now and will be replaced when the backend is built.

## Approach

Option B: existing generated types + inline placeholder types. No separate fixtures file — everything visible in one place.

## Files

- `client/src/ts-pattern/posts.ts` — the examples
- `client/tsconfig.json` — already created by `bun init`; covers all `.ts` files under `client/` with `strict: true` and bundler module resolution

## Dependency

Add `ts-pattern` to `client/package.json` dependencies. Use `"latest"` as the version specifier, consistent with the rest of `package.json`.

## Example Progression

Three examples, building in complexity. Each example imports what it uses:

```ts
import { match } from 'ts-pattern';
import type { DraftPostSchema, PublishedPostSchema, PostNotFoundError } from '../types.gen';
```

### Local alias

```ts
type PostSchema = DraftPostSchema | PublishedPostSchema;
```

### 1. Match on `PostSchema` only

Demonstrates discriminated union pattern matching on the `status` field.

```ts
function describePost(post: PostSchema): string {
  return match(post)
    .with({ status: 'DF' }, (p) => `Draft: ${p.title}, last updated ${p.updated}`)
    .with({ status: 'PB' }, (p) => `Published: ${p.title} on ${p.publish ?? 'TBD'}`)
    .exhaustive();
}
```

### 2. Match on errors only

Demonstrates multi-error matching using placeholder types alongside the real `PostNotFoundError`.

```ts
// TODO: replace AuthError/ValidationError with generated types once backend is built
type AuthError = { type: 'auth_error'; message: string };
type ValidationError = { type: 'validation_error'; field: string; message: string };
type ApiError = PostNotFoundError | AuthError | ValidationError;

function describeError(error: ApiError): string {
  return match(error)
    .with({ type: 'post_not_found' }, (e) => `Post ${e.id} not found: ${e.detail}`)
    .with({ type: 'auth_error' }, (e) => `Auth error: ${e.message}`)
    .with({ type: 'validation_error' }, (e) => `Validation error on ${e.field}: ${e.message}`)
    .exhaustive();
}
```

### 3. Combined success + error match

Demonstrates handling all success variants and all error variants in one exhaustive chain — the realistic usage pattern.

```ts
function handlePostResult(result: PostSchema | ApiError): string {
  return match(result)
    .with({ status: 'DF' }, (p) => `Draft: ${p.title}`)
    .with({ status: 'PB' }, (p) => `Published: ${p.title}`)
    .with({ type: 'post_not_found' }, (e) => `Not found: post ${e.id} — ${e.detail}`)
    .with({ type: 'auth_error' }, (e) => `Unauthorized: ${e.message}`)
    .with({ type: 'validation_error' }, (e) => `Bad input on ${e.field}`)
    .exhaustive();
}
```

`.exhaustive()` causes a TypeScript compile error if any case is unhandled — this is the key safety property being demonstrated.

## Out of Scope

- Runnable scripts or actual API calls
- Tests
- Other pattern-matching libraries (separate `src/<library-name>/` directories when needed)
- Backend changes (separate sub-project)
