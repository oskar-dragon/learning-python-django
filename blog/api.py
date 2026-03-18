from typing import Annotated, Literal

from django.http import HttpRequest
from ninja import ModelSchema, Router
from pydantic import Field

from blog.models import Post
from core.schemas import AppError

router = Router()


class PostNotFoundError(AppError):
    tag: Literal["post_not_found"] = "post_not_found"
    id: int


class DraftPostSchema(ModelSchema):
    status: Literal["DF"]

    class Meta:
        model = Post
        fields = ["id", "title", "slug", "updated", "status"]


class PublishedPostSchema(ModelSchema):
    status: Literal["PB"]

    class Meta:
        model = Post
        fields = ["id", "title", "slug", "body", "publish", "status"]


PostSchema = Annotated[DraftPostSchema | PublishedPostSchema, Field(discriminator="status")]


@router.get("/posts/", response=list[PostSchema])
def get_posts(request: HttpRequest):
    return Post.objects.all()


@router.get("/post/{post_id}", response={200: PostSchema, 404: PostNotFoundError})
def get_post(request: HttpRequest, post_id: int):
    try:
        return 200, Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return 404, {
            "tag": "post_not_found",
            "detail": f"Post with id {post_id} not found",
            "id": post_id,
        }
