from django.http import HttpRequest
from ninja import Router
from ninja_jwt.authentication import JWTAuth

from core.decorators import raises
from products.exceptions import ProductHiddenError, ProductNotFoundError
from products.models import Product
from products.schemas import ProductResponse

router = Router(auth=JWTAuth())


@router.get("/", response=list[ProductResponse])
def list_products(request: HttpRequest) -> list[Product]:
    return list(Product.objects.exclude(status=Product.Status.HIDDEN))


@router.get("/{product_id}/", response=ProductResponse)
@raises(ProductNotFoundError, ProductHiddenError)
def get_product(request: HttpRequest, product_id: int) -> Product:
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        raise ProductNotFoundError(id=product_id, detail=f"Product {product_id} not found")

    if product.status == Product.Status.HIDDEN:
        raise ProductHiddenError(id=product_id, detail=f"Product {product_id} is not available")

    return product
