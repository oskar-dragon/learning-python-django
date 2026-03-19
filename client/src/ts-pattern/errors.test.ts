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
