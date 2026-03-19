import { match } from "ts-pattern";
import type {
  CancelledOrder,
  OrdersApiGetOrderError,
  OrderResponse,
  PendingOrder,
  ShippedOrder,
} from "../generated/types.gen";

function describeOrder(order: OrderResponse): string {
  return match(order)
    .with(
      { tag: "PendingOrder" },
      (o: PendingOrder) => `Order for ${o.customer_name} is pending`,
    )
    .with(
      { tag: "ShippedOrder" },
      (o: ShippedOrder) =>
        `Order for ${o.customer_name} shipped — tracking: ${o.tracking_number}`,
    )
    .with(
      { tag: "CancelledOrder" },
      (o: CancelledOrder) =>
        `Order for ${o.customer_name} cancelled — reason: ${o.cancellation_reason}`,
    )
    .exhaustive();
}

// All errors — domain and framework — discriminated by tag.
function describeError(error: OrdersApiGetOrderError): string {
  return match(error)
    .with(
      { tag: "OrderNotFoundError" },
      (e) => `Order ${e.id} not found`,
    )
    .with(
      { tag: "OrderNotAccessibleError" },
      (e) => `Order ${e.id} is not accessible`,
    )
    .with({ tag: "AuthenticationError" }, () => "Please log in")
    .with({ tag: "AuthorizationError" }, () => "Access denied")
    .with({ tag: "ValidationError" }, () => "Invalid request")
    .with({ tag: "InternalError" }, () => "Something went wrong")
    .exhaustive();
}

export { describeError, describeOrder };
