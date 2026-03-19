import { match } from "ts-pattern";
import type {
  CancelledOrder,
  OrderNotAccessibleError,
  OrderNotFoundError,
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

function describeError(
  error: OrderNotFoundError | OrderNotAccessibleError,
): string {
  return match(error)
    .with(
      { tag: "OrderNotFoundError" },
      (e: OrderNotFoundError) => `Order ${e.id} not found`,
    )
    .with(
      { tag: "OrderNotAccessibleError" },
      (e: OrderNotAccessibleError) => `Order ${e.id} is not accessible`,
    )
    .exhaustive();
}

export { describeError, describeOrder };
