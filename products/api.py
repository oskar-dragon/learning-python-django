from typing import Annotated, Literal

from django.http import HttpRequest
from ninja import ModelSchema, Router
from ninja_jwt.authentication import JWTAuth
from pydantic import Field

from core.schemas import AppError
from products.models import Product

router = Router(auth=JWTAuth())


class ProductNotFoundError(AppError):
    type: Literal["product_not_found"]
    id: int


class ProductHiddenError(AppError):
    type: Literal["product_hidden"]
    id: int


class AvailableProductSchema(ModelSchema):
    status: Literal["available"]

    class Meta:
        model = Product
        fields = ["id", "name", "description", "price", "stock_count", "status"]


class OutOfStockProductSchema(ModelSchema):
    status: Literal["out_of_stock"]

    class Meta:
        model = Product
        fields = ["id", "name", "description", "price", "status"]


ProductSchema = Annotated[
    AvailableProductSchema | OutOfStockProductSchema,
    Field(discriminator="status"),
]


@router.get("/", response=list[ProductSchema])
def list_products(request: HttpRequest) -> list[Product]:
    return list(Product.objects.exclude(status=Product.Status.HIDDEN))


@router.get(
    "/{product_id}/",
    response={200: ProductSchema, 404: ProductNotFoundError, 403: ProductHiddenError},
)
def get_product(request: HttpRequest, product_id: int) -> tuple[int, Product | dict[str, object]]:
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return 404, {
            "type": "product_not_found",
            "detail": f"Product {product_id} not found",
            "id": product_id,
        }

    match product.status:
        case "available":
            return 200, product
        case "out_of_stock":
            return 200, product
        case "hidden":
            return 403, {
                "type": "product_hidden",
                "detail": f"Product {product_id} is not available",
                "id": product_id,
            }
        case _:
            return 404, {
                "type": "product_not_found",
                "detail": f"Product {product_id} not found",
                "id": product_id,
            }
