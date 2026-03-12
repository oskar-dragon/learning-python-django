import { match } from "ts-pattern";
import type {
  ProductResult,
  ProductHiddenError,
  ProductNotFoundError,
  ProductsApiGetProductError,
} from "../generated/types.gen";

// Example 1: match on success variants only.
// stock_count is only accessible when tag is "available" — TypeScript
// narrows the type per branch, so accessing it on the "out_of_stock" branch
// would be a compile error.
function describeProduct(product: ProductResult): string {
  return match(product)
    .with({ tag: "available" }, (p) => `Available: ${p.name} — ${p.stock_count} in stock at $${p.price}`)
    .with({ tag: "out_of_stock" }, (p) => `Out of stock: ${p.name} at $${p.price}`)
    .exhaustive();
}

// Example 2: match on errors only.
// Uses the generated error union type — no manual assembly.
function describeError(error: ProductsApiGetProductError): string {
  return match(error)
    .with({ tag: "product_not_found" }, (e) => `Product ${e.id} not found: ${e.detail}`)
    .with({ tag: "product_hidden" }, (e) => `Product ${e.id} is restricted: ${e.detail}`)
    .exhaustive();
}

// Example 3: combined success + error match in one exhaustive chain.
// Demonstrates the realistic usage pattern after calling productsApiGetProduct().
function handleProductResult(
  result: ProductResult | ProductsApiGetProductError
): string {
  return match(result)
    .with({ tag: "available" }, (p) => `Available: ${p.name} (${p.stock_count} left)`)
    .with({ tag: "out_of_stock" }, (p) => `Sold out: ${p.name}`)
    .with({ tag: "product_not_found" }, (e) => `Not found: product ${e.id}`)
    .with({ tag: "product_hidden" }, (e) => `Restricted: product ${e.id}`)
    .exhaustive();
}

// Auth setup: configure the hey-api client with a Bearer token
// before making authenticated requests to the products endpoints.
//
// import { client } from "../generated";
// client.setConfig({ headers: { Authorization: `Bearer ${token}` } });
