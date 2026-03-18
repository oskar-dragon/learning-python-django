import { match } from "ts-pattern";
import type {
  CancelledOrderSchema,
  OrderNotAccessibleError,
  OrderNotFoundError,
  OrderResult,
  PendingOrderSchema,
  ShippedOrderSchema,
} from "../generated/types.gen";

function describeOrder(order: OrderResult): string {
  return match(order)
    .with(
      { tag: "PendingOrderSchema" },
      (o: PendingOrderSchema) => `Order for ${o.customer_name} is pending`,
    )
    .with(
      { tag: "ShippedOrderSchema" },
      (o: ShippedOrderSchema) =>
        `Order for ${o.customer_name} shipped — tracking: ${o.tracking_number}`,
    )
    .with(
      { tag: "CancelledOrderSchema" },
      (o: CancelledOrderSchema) =>
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
