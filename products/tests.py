from django.test import TestCase

from products.models import Product


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
