from typing import override

from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja_jwt.tokens import AccessToken

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


def _create_order(
    customer_name: str,
    status: Order.Status,
    total_price: str = "100.00",
    items_count: int = 2,
    tracking_number: str | None = None,
    shipped_at: str | None = None,
    cancellation_reason: str | None = None,
    cancelled_at: str | None = None,
) -> Order:
    return Order.objects.create(
        customer_name=customer_name,
        status=status,
        total_price=total_price,
        items_count=items_count,
        tracking_number=tracking_number,
        shipped_at=shipped_at,
        cancellation_reason=cancellation_reason,
        cancelled_at=cancelled_at,
    )


class OrdersListAPITest(TestCase):
    token: str  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        user = User.objects.create_user(username="listuser", password="pass123!")
        self.token = f"Bearer {AccessToken.for_user(user)}"

        _ = _create_order("Alice", Order.Status.PENDING, total_price="50.00")
        _ = _create_order(
            "Bob",
            Order.Status.SHIPPED,
            total_price="200.00",
            tracking_number="TRACK123",
            shipped_at="2026-01-01T10:00:00Z",
        )
        _ = _create_order(
            "Charlie",
            Order.Status.CANCELLED,
            total_price="150.00",
            cancellation_reason="Changed mind",
            cancelled_at="2026-01-02T10:00:00Z",
        )
        _ = _create_order("DraftUser", Order.Status.DRAFT, total_price="999.00")

    def test_list_requires_auth(self) -> None:
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 401)

    def test_list_returns_non_draft_orders(self) -> None:
        response = self.client.get("/api/orders/", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 3)
        names = {o["customer_name"] for o in data}
        self.assertEqual(names, {"Alice", "Bob", "Charlie"})

    def test_list_pending_order_has_correct_tag(self) -> None:
        response = self.client.get("/api/orders/", HTTP_AUTHORIZATION=self.token)
        pending = next(o for o in response.json() if o["customer_name"] == "Alice")
        self.assertEqual(pending["tag"], "pending")
        self.assertNotIn("tracking_number", pending)
        self.assertNotIn("cancellation_reason", pending)

    def test_list_shipped_order_has_tracking_number(self) -> None:
        response = self.client.get("/api/orders/", HTTP_AUTHORIZATION=self.token)
        shipped = next(o for o in response.json() if o["customer_name"] == "Bob")
        self.assertEqual(shipped["tag"], "shipped")
        self.assertEqual(shipped["tracking_number"], "TRACK123")

    def test_list_cancelled_order_has_cancellation_reason(self) -> None:
        response = self.client.get("/api/orders/", HTTP_AUTHORIZATION=self.token)
        cancelled = next(o for o in response.json() if o["customer_name"] == "Charlie")
        self.assertEqual(cancelled["tag"], "cancelled")
        self.assertEqual(cancelled["cancellation_reason"], "Changed mind")

    def test_filter_by_status(self) -> None:
        response = self.client.get("/api/orders/?status=pending", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer_name"], "Alice")

    def test_filter_by_q_customer_name(self) -> None:
        response = self.client.get("/api/orders/?q=bob", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer_name"], "Bob")

    def test_filter_by_min_total(self) -> None:
        response = self.client.get("/api/orders/?min_total=100", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        names = {o["customer_name"] for o in response.json()}
        # DraftUser (999.00) is excluded because drafts are always filtered out
        self.assertEqual(names, {"Bob", "Charlie"})

    def test_filter_by_max_total(self) -> None:
        response = self.client.get("/api/orders/?max_total=60", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        names = {o["customer_name"] for o in response.json()}
        self.assertEqual(names, {"Alice"})

    def test_invalid_status_returns_422(self) -> None:
        response = self.client.get("/api/orders/?status=bogus", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 422)


class OrdersDetailAPITest(TestCase):
    token: str  # pyright: ignore[reportUninitializedInstanceVariable]
    pending: Order  # pyright: ignore[reportUninitializedInstanceVariable]
    shipped: Order  # pyright: ignore[reportUninitializedInstanceVariable]
    cancelled: Order  # pyright: ignore[reportUninitializedInstanceVariable]
    draft: Order  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        user = User.objects.create_user(username="detailuser", password="pass123!")
        self.token = f"Bearer {AccessToken.for_user(user)}"

        self.pending = _create_order("Alice", Order.Status.PENDING, total_price="50.00")
        self.shipped = _create_order(
            "Bob",
            Order.Status.SHIPPED,
            total_price="200.00",
            tracking_number="TRACK123",
            shipped_at="2026-01-01T10:00:00Z",
        )
        self.cancelled = _create_order(
            "Charlie",
            Order.Status.CANCELLED,
            total_price="75.00",
            cancellation_reason="Changed mind",
            cancelled_at="2026-01-02T10:00:00Z",
        )
        self.draft = _create_order("DraftUser", Order.Status.DRAFT, total_price="999.00")

    def test_detail_requires_auth(self) -> None:
        response = self.client.get(f"/api/orders/{self.pending.pk}/")
        self.assertEqual(response.status_code, 401)

    def test_get_pending_order(self) -> None:
        response = self.client.get(f"/api/orders/{self.pending.pk}/", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "pending")
        self.assertEqual(data["customer_name"], "Alice")
        self.assertNotIn("tracking_number", data)
        self.assertNotIn("cancellation_reason", data)

    def test_get_shipped_order(self) -> None:
        response = self.client.get(f"/api/orders/{self.shipped.pk}/", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "shipped")
        self.assertEqual(data["tracking_number"], "TRACK123")
        self.assertIn("shipped_at", data)

    def test_get_cancelled_order(self) -> None:
        response = self.client.get(
            f"/api/orders/{self.cancelled.pk}/", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "cancelled")
        self.assertEqual(data["cancellation_reason"], "Changed mind")
        self.assertIn("cancelled_at", data)

    def test_get_nonexistent_order_returns_404(self) -> None:
        response = self.client.get("/api/orders/99999/", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["tag"], "order_not_found")
        self.assertEqual(data["id"], 99999)

    def test_get_draft_order_returns_403(self) -> None:
        response = self.client.get(f"/api/orders/{self.draft.pk}/", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["tag"], "order_not_accessible")
        self.assertEqual(data["id"], self.draft.pk)
