from ninja import NinjaAPI

from blog.api import router as blog_router

api = NinjaAPI()

api.add_router("/blog", blog_router)
