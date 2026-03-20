from pydantic import RootModel

from core.schemas import TaggedModelSchema
from products.models import Product


class AvailableProduct(TaggedModelSchema, tag="available", tag_field="status"):
    class Meta:
        model = Product
        exclude = ["status", "created", "updated"]


class OutOfStockProduct(TaggedModelSchema, tag="out_of_stock", tag_field="status"):
    class Meta:
        model = Product
        exclude = ["status", "stock_count", "created", "updated"]


class ProductResponse(RootModel[AvailableProduct | OutOfStockProduct]):
    pass


from products.exceptions import ProductHiddenError, ProductNotFoundError


class ProductErrors(RootModel[ProductNotFoundError.Schema | ProductHiddenError.Schema]):
    pass
