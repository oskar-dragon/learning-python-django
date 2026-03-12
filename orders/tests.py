from django.contrib.auth import get_user_model
from django.test import TestCase

from orders.models import Order

User = get_user_model()


class OrderModelTest(TestCase):
    def test_default_status_is_pending(self) -> None:
        order = Order(customer_name="Alice", total_price="50.00", items_count=2)
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_str_representation(self) -> None:
        order = Order(
            pk=1,
            customer_name="Alice",
            total_price="50.00",
            items_count=2,
            status=Order.Status.PENDING,
        )
        self.assertEqual(str(order), "Order 1 (pending)")

    def test_status_choices_are_complete(self) -> None:
        statuses = {s.value for s in Order.Status}
        self.assertEqual(statuses, {"draft", "pending", "shipped", "cancelled"})
