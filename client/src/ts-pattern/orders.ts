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
    .with({ tag: "pending" }, (o: PendingOrderSchema) => `Order for ${o.customer_name} is pending`)
    .with(
      { tag: "shipped" },
      (o: ShippedOrderSchema) =>
        `Order for ${o.customer_name} shipped — tracking: ${o.tracking_number}`
    )
    .with(
      { tag: "cancelled" },
      (o: CancelledOrderSchema) =>
        `Order for ${o.customer_name} cancelled — reason: ${o.cancellation_reason}`
    )
    .exhaustive();
}

function describeError(error: OrderNotFoundError | OrderNotAccessibleError): string {
  return match(error)
    .with({ tag: "order_not_found" }, (e: OrderNotFoundError) => `Order ${e.id} not found`)
    .with(
      { tag: "order_not_accessible" },
      (e: OrderNotAccessibleError) => `Order ${e.id} is not accessible`
    )
    .exhaustive();
}

export { describeError, describeOrder };
