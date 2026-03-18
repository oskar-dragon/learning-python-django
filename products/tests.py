from typing import override

from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja_jwt.tokens import AccessToken

from products.models import Product

User = get_user_model()


class ProductModelTest(TestCase):
    def test_create_available_product(self) -> None:
        product = Product.objects.create(
            name="Widget",
            description="A fine widget",
            price="9.99",
            stock_count=100,
            status=Product.Status.AVAILABLE,
        )
        self.assertEqual(product.name, "Widget")
        self.assertEqual(product.status, "available")
        self.assertEqual(product.stock_count, 100)

    def test_create_out_of_stock_product(self) -> None:
        product = Product.objects.create(
            name="Gadget",
            description="A fine gadget",
            price="19.99",
            stock_count=0,
            status=Product.Status.OUT_OF_STOCK,
        )
        self.assertEqual(product.status, "out_of_stock")

    def test_str_returns_name(self) -> None:
        product = Product(name="Widget")
        self.assertEqual(str(product), "Widget")


class ProductsListAPITest(TestCase):
    token: str  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        user = User.objects.create_user(username="testuser", password="pass123!")
        self.token = f"Bearer {AccessToken.for_user(user)}"

        _ = Product.objects.create(
            name="Widget",
            description="A widget",
            price="9.99",
            stock_count=10,
            status=Product.Status.AVAILABLE,
        )
        _ = Product.objects.create(
            name="Gadget",
            description="A gadget",
            price="19.99",
            stock_count=0,
            status=Product.Status.OUT_OF_STOCK,
        )
        _ = Product.objects.create(
            name="Secret",
            description="Hidden product",
            price="99.99",
            stock_count=5,
            status=Product.Status.HIDDEN,
        )

    def test_list_requires_auth(self) -> None:
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, 401)

    def test_list_returns_visible_products(self) -> None:
        response = self.client.get("/api/products/", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        names = {p["name"] for p in data}
        self.assertEqual(names, {"Widget", "Gadget"})

    def test_list_excludes_hidden_products(self) -> None:
        response = self.client.get("/api/products/", HTTP_AUTHORIZATION=self.token)
        names = [p["name"] for p in response.json()]
        self.assertNotIn("Secret", names)

    def test_available_product_includes_stock_count(self) -> None:
        response = self.client.get("/api/products/", HTTP_AUTHORIZATION=self.token)
        available = next(p for p in response.json() if p["tag"] == "available")
        self.assertIn("stock_count", available)
        self.assertEqual(available["stock_count"], 10)

    def test_out_of_stock_product_excludes_stock_count(self) -> None:
        response = self.client.get("/api/products/", HTTP_AUTHORIZATION=self.token)
        oos = next(p for p in response.json() if p["tag"] == "out_of_stock")
        self.assertNotIn("stock_count", oos)


class ProductsDetailAPITest(TestCase):
    token: str  # pyright: ignore[reportUninitializedInstanceVariable]
    available: Product  # pyright: ignore[reportUninitializedInstanceVariable]
    oos: Product  # pyright: ignore[reportUninitializedInstanceVariable]
    hidden: Product  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        user = User.objects.create_user(username="detailuser", password="pass123!")
        self.token = f"Bearer {AccessToken.for_user(user)}"

        self.available = Product.objects.create(
            name="Widget",
            description="A widget",
            price="9.99",
            stock_count=10,
            status=Product.Status.AVAILABLE,
        )
        self.oos = Product.objects.create(
            name="Gadget",
            description="A gadget",
            price="19.99",
            stock_count=0,
            status=Product.Status.OUT_OF_STOCK,
        )
        self.hidden = Product.objects.create(
            name="Secret",
            description="Hidden",
            price="99.99",
            stock_count=5,
            status=Product.Status.HIDDEN,
        )

    def test_detail_requires_auth(self) -> None:
        response = self.client.get(f"/api/products/{self.available.pk}/")
        self.assertEqual(response.status_code, 401)

    def test_get_available_product(self) -> None:
        response = self.client.get(
            f"/api/products/{self.available.pk}/", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "available")
        self.assertIn("stock_count", data)

    def test_get_out_of_stock_product(self) -> None:
        response = self.client.get(f"/api/products/{self.oos.pk}/", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "out_of_stock")
        self.assertNotIn("stock_count", data)

    def test_get_hidden_product_returns_403(self) -> None:
        response = self.client.get(
            f"/api/products/{self.hidden.pk}/", HTTP_AUTHORIZATION=self.token
        )
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["tag"], "ProductHiddenError")
        self.assertEqual(data["id"], self.hidden.pk)

    def test_get_nonexistent_product_returns_404(self) -> None:
        response = self.client.get("/api/products/99999/", HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["tag"], "ProductNotFoundError")
        self.assertEqual(data["id"], 99999)
