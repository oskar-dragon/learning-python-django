import { match } from "ts-pattern";
import type {
  AvailableProductSchema,
  OutOfStockProductSchema,
  ProductHiddenError,
  ProductNotFoundError,
} from "../types.gen";

// Local alias for the product response union.
// The Hey API generator expresses this inline in response types;
// we define it here for readability.
type ProductSchema = AvailableProductSchema | OutOfStockProductSchema;

// Both error types extend AppError (type: string, detail: string).
type ProductApiError = ProductNotFoundError | ProductHiddenError;

// Example 1: match on the ProductSchema discriminated union only.
// Demonstrates: ts-pattern matches on the `status` discriminant field.
// `stock_count` is only accessible when status is "available" — TypeScript
// narrows the type per branch, so accessing it on the "out_of_stock" branch
// would be a compile error.
function describeProduct(product: ProductSchema): string {
  return match(product)
    .with(
      { status: "available" },
      (p) => `Available: ${p.name} — ${p.stock_count} in stock at $${p.price}`,
    )
    .with(
      { status: "out_of_stock" },
      (p) => `Out of stock: ${p.name} at $${p.price}`,
    )
    .exhaustive();
}

// Example 2: match on errors only.
// Demonstrates: each error variant carries different fields.
// `product_not_found` and `product_hidden` both have `id: number`,
// but represent distinct failure modes.
function describeError(error: ProductApiError): string {
  return match(error)
    .with(
      { type: "product_not_found" },
      (e) => `Product ${e.id} not found: ${e.detail}`,
    )
    .with(
      { type: "product_hidden" },
      (e) => `Product ${e.id} is restricted: ${e.detail}`,
    )
    .exhaustive();
}

// Example 3: combined success + error match in one exhaustive chain.
// Demonstrates: the realistic usage pattern after calling productsApiGetProduct().
// Remove any `.with(...)` arm to see the TypeScript compile error from `.exhaustive()`.
function handleProductResult(result: ProductSchema | ProductApiError): string {
  return match(result)
    .with({ status: "available" }, (p) => `Available: ${p.name} (${p.stock_count} left)`)
    .with({ status: "out_of_stock" }, (p) => `Sold out: ${p.name}`)
    .with({ type: "product_not_found" }, (e) => `Not found: product ${e.id}`)
    .with({ type: "product_hidden" }, (e) => `Restricted: product ${e.id}`)
    .exhaustive();
}

// Auth setup example: configure the hey-api client with a Bearer token
// before making authenticated requests to the products endpoints.
//
// import { client } from '../client.gen';
//
// function configureAuth(accessToken: string): void {
//   client.setConfig({
//     headers: { Authorization: `Bearer ${accessToken}` },
//   });
// }
//
// After calling configureAuth(), all SDK calls (productsApiListProducts,
// productsApiGetProduct, etc.) will include the Authorization header automatically.
