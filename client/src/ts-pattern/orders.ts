import { match } from "ts-pattern";
import type {
  CancelledOrder,
  OrdersApiGetOrderData,
  OrdersApiGetOrderError,
  OrderResponse,
} from "../generated/types.gen";
import { flattenValidationErrors, type ExtractFields } from "./errors.ts";

function describeOrder(order: OrderResponse): string {
  return match(order)
    .with(
      { tag: "PendingOrder" },
      (o) => `Order for ${o.customer_name} is pending`,
    )
    .with(
      { tag: "ShippedOrder" },
      (o) =>
        `Order for ${o.customer_name} shipped — tracking: ${o.tracking_number}`,
    )
    .with(
      { tag: "CancelledOrder" },
      (o) =>
        `Order for ${o.customer_name} cancelled — reason: ${o.cancellation_reason}`,
    )
    .exhaustive();
}

// All errors — domain and framework — discriminated by tag.
function describeError(error: OrdersApiGetOrderError): string {
  return match(error)
    .with({ tag: "OrderNotFoundError" }, (e) => `Order ${e.id} not found`)
    .with(
      { tag: "OrderNotAccessibleError" },
      (e) => `Order ${e.id} is not accessible`,
    )
    .with({ tag: "AuthenticationError" }, () => "Please log in")
    .with({ tag: "AuthorizationError" }, () => "Access denied")
    .with({ tag: "ValidationError" }, (e) => {
      const fields = flattenValidationErrors<
        ExtractFields<OrdersApiGetOrderData>
      >(e.detail);
      // Field-level access with autocomplete: fields.path?.order_id?.msg
      fields.path?.order_id?.msg;
      return fields.path?.order_id?.msg ?? "Validation error";
    })
    .with({ tag: "InternalError" }, () => "Something went wrong")
    .exhaustive();
}

export { describeError, describeOrder };
