/**
 * Typed validation error utilities.
 *
 * Transforms Django Ninja's flat validation error array into a field-keyed
 * object grouped by param source (query/body/path), inspired by Zod's .flatten().
 *
 * Usage:
 *   import type { OrdersApiListOrdersData } from "../generated/types.gen";
 *
 *   const fields = flattenValidationErrors<ExtractFields<OrdersApiListOrdersData>>(e.detail);
 *   fields.query?.status?.msg  // autocomplete on field names
 */

export type ValidationErrorItem = {
  type: string;
  loc: (string | number)[];
  msg: string;
};

type FieldError = { msg: string };

export type FieldErrors<T> = { [K in keyof T]?: FieldError };

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
  const result: Record<string, Record<string, FieldError>> = {};
  for (const error of errors) {
    const [source, field] = error.loc;
    if (typeof source === "string" && field !== undefined) {
      const key = String(field);
      const sourceErrors = (result[source] ??= {});
      sourceErrors[key] ??= { msg: error.msg };
    }
  }
  return result as { [S in keyof T]?: FieldErrors<T[S]> };
}
