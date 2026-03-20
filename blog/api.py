from django.http import HttpRequest
from ninja import Router

from blog.exceptions import PostNotFoundError
from blog.models import Post
from blog.schemas import PostResponse
from core.decorators import raises

router = Router()


@router.get("/posts/", response=list[PostResponse])
def get_posts(request: HttpRequest):
    return Post.objects.all()


@router.get("/post/{post_id}", response=PostResponse)
@raises(PostNotFoundError)
def get_post(request: HttpRequest, post_id: int):
    try:
        return Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        raise PostNotFoundError(id=post_id, detail=f"Post with id {post_id} not found")
