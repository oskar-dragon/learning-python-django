import { match } from "ts-pattern";
import type {
  ProductResponse,
  ProductsApiGetProductError,
} from "../generated/types.gen";

// Example 1: match on success variants only.
// stock_count is only accessible when tag is "available" — TypeScript
// narrows the type per branch, so accessing it on the "out_of_stock" branch
// would be a compile error.
function describeProduct(product: ProductResponse): string {
  return match(product)
    .with(
      { tag: "available" },
      (p) => `Available: ${p.name} — ${p.stock_count} in stock at $${p.price}`,
    )
    .with(
      { tag: "out_of_stock" },
      (p) => `Out of stock: ${p.name} at $${p.price}`,
    )
    .exhaustive();
}

// Example 2: match on errors only.
// Uses the generated error union type — domain and framework errors discriminated by tag.
function describeError(error: ProductsApiGetProductError): string {
  return match(error)
    .with(
      { tag: "ProductNotFoundError" },
      (e) => `Product ${e.id} not found: ${e.detail}`,
    )
    .with(
      { tag: "ProductHiddenError" },
      (e) => `Product ${e.id} is restricted: ${e.detail}`,
    )
    .with({ tag: "AuthenticationError" }, () => "Please log in")
    .with({ tag: "AuthorizationError" }, () => "Access denied")
    .with({ tag: "ValidationError" }, () => "Invalid request")
    .with({ tag: "InternalError" }, () => "Something went wrong")
    .exhaustive();
}

// Example 3: combined success + error match in one exhaustive chain.
// Demonstrates the realistic usage pattern after calling productsApiGetProduct().
function handleProductResponse(
  result: ProductResponse | ProductsApiGetProductError,
): string {
  return match(result)
    .with(
      { tag: "available" },
      (p) => `Available: ${p.name} (${p.stock_count} left)`,
    )
    .with({ tag: "out_of_stock" }, (p) => `Sold out: ${p.name}`)
    .with({ tag: "ProductNotFoundError" }, (e) => `Not found: product ${e.id}`)
    .with({ tag: "ProductHiddenError" }, (e) => `Restricted: product ${e.id}`)
    .with({ tag: "AuthenticationError" }, () => "Please log in")
    .with({ tag: "AuthorizationError" }, () => "Access denied")
    .with({ tag: "ValidationError" }, () => "Invalid request")
    .with({ tag: "InternalError" }, () => "Something went wrong")
    .exhaustive();
}

// Auth setup: configure the hey-api client with a Bearer token
// before making authenticated requests to the products endpoints.
//
// import { client } from "../generated";
// client.setConfig({ headers: { Authorization: `Bearer ${token}` } });
