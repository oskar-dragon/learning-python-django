from django.http import HttpRequest
from ninja import Router
from ninja_jwt.authentication import JWTAuth

from products.models import Product
from products.schemas import ProductHiddenError, ProductNotFoundError, ProductResult

router = Router(auth=JWTAuth())


@router.get("/", response=list[ProductResult])
def list_products(request: HttpRequest) -> list[Product]:
    return list(Product.objects.exclude(status=Product.Status.HIDDEN))


@router.get(
    "/{product_id}/",
    response={200: ProductResult, 404: ProductNotFoundError, 403: ProductHiddenError},
)
def get_product(request: HttpRequest, product_id: int) -> tuple[int, Product | dict[str, object]]:
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return 404, {
            "tag": "product_not_found",
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
                "tag": "product_hidden",
                "detail": f"Product {product_id} is not available",
                "id": product_id,
            }
        case _:
            return 404, {
                "tag": "product_not_found",
                "detail": f"Product {product_id} not found",
                "id": product_id,
            }
