# Typed Validation Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a typed frontend utility that transforms flat validation error arrays into field-keyed objects with autocomplete, inspired by Zod's `.flatten()`.

**Architecture:** One new TypeScript file with type definitions and a utility function. No backend changes. The utility is generic — the type parameter is derived from the already-generated request `Data` types, which carry field names grouped by param source (query/body/path).

**Tech Stack:** TypeScript, bun (test runner), ts-pattern (usage examples)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `client/src/ts-pattern/errors.ts` | `flattenValidationErrors` utility, `FieldErrors<T>`, `ExtractFields<T>`, `ValidationErrorItem` type (internal: `ExcludeNever<T>`) |
| Create | `client/src/ts-pattern/errors.test.ts` | Tests for `flattenValidationErrors` |
| Modify | `client/src/ts-pattern/orders.ts` | Update `describeError` to demonstrate `flattenValidationErrors` usage |

---

### Task 1: Create `flattenValidationErrors` utility with tests

**Files:**
- Create: `client/src/ts-pattern/errors.test.ts`
- Create: `client/src/ts-pattern/errors.ts`

- [ ] **Step 1: Write the tests**

```typescript
// client/src/ts-pattern/errors.test.ts

import { test, expect } from "bun:test";
import { flattenValidationErrors, type ValidationErrorItem } from "./errors.ts";

// Simulate the generated Data types
type QueryOnlyData = {
  query?: { status?: string; q?: string };
  path?: never;
  body?: never;
  url: "/api/orders/";
};

type PathOnlyData = {
  path: { order_id: number };
  query?: never;
  body?: never;
  url: "/api/orders/{order_id}/";
};

type AllParamsData = {
  body: { customer_name: string; items_count: number };
  path: { order_id: number };
  query?: { notify?: boolean };
  url: "/api/orders/{order_id}/";
};

test("groups errors by param source and field name", () => {
  const errors: ValidationErrorItem[] = [
    { type: "enum", loc: ["query", "status"], msg: "Invalid status" },
    { type: "string_type", loc: ["query", "q"], msg: "Must be string" },
  ];

  const fields = flattenValidationErrors<{ query: { status: string; q: string } }>(errors);
  expect(fields.query?.status?.msg).toBe("Invalid status");
  expect(fields.query?.q?.msg).toBe("Must be string");
});

test("first error per field wins", () => {
  const errors: ValidationErrorItem[] = [
    { type: "string_too_short", loc: ["query", "q"], msg: "Too short" },
    { type: "string_type", loc: ["query", "q"], msg: "Must be string" },
  ];

  const fields = flattenValidationErrors<{ query: { q: string } }>(errors);
  expect(fields.query?.q?.msg).toBe("Too short");
});

test("handles path params", () => {
  const errors: ValidationErrorItem[] = [
    { type: "int_parsing", loc: ["path", "order_id"], msg: "Must be integer" },
  ];

  const fields = flattenValidationErrors<{ path: { order_id: number } }>(errors);
  expect(fields.path?.order_id?.msg).toBe("Must be integer");
});

test("handles mixed param sources", () => {
  const errors: ValidationErrorItem[] = [
    { type: "int_parsing", loc: ["path", "order_id"], msg: "Must be integer" },
    { type: "enum", loc: ["query", "notify"], msg: "Must be boolean" },
    { type: "missing", loc: ["body", "customer_name"], msg: "Required" },
  ];

  const fields = flattenValidationErrors<{
    path: { order_id: number };
    query: { notify: boolean };
    body: { customer_name: string };
  }>(errors);

  expect(fields.path?.order_id?.msg).toBe("Must be integer");
  expect(fields.query?.notify?.msg).toBe("Must be boolean");
  expect(fields.body?.customer_name?.msg).toBe("Required");
});

test("returns empty object for no errors", () => {
  const fields = flattenValidationErrors<{ query: { status: string } }>([]);
  expect(fields.query).toBeUndefined();
});

test("ignores errors with only a source and no field name", () => {
  const errors: ValidationErrorItem[] = [
    { type: "missing", loc: ["body"], msg: "Body required" },
  ];

  const fields = flattenValidationErrors<{ body: { name: string } }>(errors);
  expect(fields.body).toBeUndefined();
});

test("handles list field errors by keying on field name", () => {
  const errors: ValidationErrorItem[] = [
    { type: "int_parsing", loc: ["query", "ids", "0"], msg: "Must be integer" },
  ];

  const fields = flattenValidationErrors<{ query: { ids: number[] } }>(errors);
  expect(fields.query?.ids?.msg).toBe("Must be integer");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd client && bun test src/ts-pattern/errors.test.ts`
Expected: FAIL — `errors.ts` doesn't exist yet

- [ ] **Step 3: Write the implementation**

```typescript
// client/src/ts-pattern/errors.ts

/**
 * Typed validation error utilities.
 *
 * Transforms Django Ninja's flat validation error array into a field-keyed
 * object grouped by param source (query/body/path), inspired by Zod's .flatten().
 *
 * Usage:
 *   import type { OrdersApiListOrdersData } from "../generated/types.gen";
 *
 *   const fields = flattenValidationErrors<ExtractFields<OrdersApiListOrdersData>>(e.errors);
 *   fields.query?.status?.msg  // autocomplete on field names
 */

export type ValidationErrorItem = {
  type: string;
  loc: (string | number)[];
  msg: string;
};

export type FieldErrors<T> = { [K in keyof T]?: ValidationErrorItem };

type ExcludeNever<T> = {
  [K in keyof T as [T[K]] extends [never] ? never : K]: T[K];
};

export type ExtractFields<T> = ExcludeNever<{
  query: T extends { query?: infer Q } ? NonNullable<Q> : never;
  body: T extends { body?: infer B } ? NonNullable<B> : never;
  path: T extends { path?: infer P } ? NonNullable<P> : never;
}>;

export function flattenValidationErrors<
  T extends Record<string, Record<string, unknown>>,
>(errors: ValidationErrorItem[]): { [S in keyof T]?: FieldErrors<T[S]> } {
  const result: Record<string, Record<string, ValidationErrorItem>> = {};
  for (const error of errors) {
    const [source, field] = error.loc;
    if (typeof source === "string" && field !== undefined) {
      const key = String(field);
      const sourceErrors = (result[source] ??= {});
      sourceErrors[key] ??= error;
    }
  }
  return result as { [S in keyof T]?: FieldErrors<T[S]> };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd client && bun test src/ts-pattern/errors.test.ts`
Expected: ALL PASS (7 tests)

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd client && bun run tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add client/src/ts-pattern/errors.ts client/src/ts-pattern/errors.test.ts
git commit -m "feat(client): add flattenValidationErrors utility with typed field access"
```

---

### Task 2: Update orders ts-pattern example to demonstrate usage

**Files:**
- Modify: `client/src/ts-pattern/orders.ts`

- [ ] **Step 1: Update `orders.ts` to use `flattenValidationErrors`**

In `client/src/ts-pattern/orders.ts`, update the `describeError` function. Replace the simple `ValidationError` branch with one that demonstrates `flattenValidationErrors`:

Change:
```typescript
    .with({ tag: "ValidationError" }, () => "Invalid request")
```

To:
```typescript
    .with({ tag: "ValidationError" }, (e) => {
      const fields = flattenValidationErrors<ExtractFields<OrdersApiGetOrderData>>(e.errors);
      // Field-level access with autocomplete: fields.path?.order_id?.msg
      return fields.path?.order_id?.msg ?? "Validation error";
    })
```

Add the necessary imports at the top:
```typescript
import { flattenValidationErrors, type ExtractFields } from "./errors.ts";
import type { OrdersApiGetOrderData } from "../generated/types.gen";
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd client && bun run tsc --noEmit`
Expected: No errors — `fields.path?.order_id?.msg` autocompletes and type-checks

- [ ] **Step 3: Commit**

```bash
git add client/src/ts-pattern/orders.ts
git commit -m "refactor(client): demonstrate flattenValidationErrors in orders example"
```

---

### Task 3: Final verification

- [ ] **Step 1: Run all client tests**

Run: `cd client && bun test`
Expected: ALL PASS

- [ ] **Step 2: Run TypeScript type checker**

Run: `cd client && bun run tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Run backend tests to verify nothing broken**

Run: `.venv/bin/python manage.py test -v2`
Expected: ALL PASS (no backend changes, but verify anyway)
