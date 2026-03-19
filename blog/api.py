from django.http import HttpRequest
from ninja import Router

from blog.models import Post
from blog.schemas import PostNotFoundError, PostResponse

router = Router()


@router.get("/posts/", response=list[PostResponse])
def get_posts(request: HttpRequest):
    return Post.objects.all()


@router.get("/post/{post_id}", response={200: PostResponse, 404: PostNotFoundError})
def get_post(request: HttpRequest, post_id: int):
    try:
        return 200, Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return 404, {
            "tag": "PostNotFoundError",
            "detail": f"Post with id {post_id} not found",
            "id": post_id,
        }
