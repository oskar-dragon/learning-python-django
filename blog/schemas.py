from pydantic import RootModel

from blog.models import Post
from core.schemas import AppError, TaggedModelSchema


class DraftPost(TaggedModelSchema, tag="draft", tag_field="status"):
    class Meta:
        model = Post
        fields = ["id", "title", "slug", "updated"]


class PublishedPost(TaggedModelSchema, tag="published", tag_field="status"):
    class Meta:
        model = Post
        fields = ["id", "title", "slug", "body", "publish"]


class PostResponse(RootModel[DraftPost | PublishedPost]):
    pass


class PostNotFoundError(AppError):
    id: int
