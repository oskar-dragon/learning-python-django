from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController

from blog.api import router as blog_router
from products.api import router as products_router

api = NinjaExtraAPI()
api.register_controllers(NinjaJWTDefaultController)  # pyright: ignore[reportUnknownMemberType]

api.add_router("/blog", blog_router)
api.add_router("/products", products_router)
