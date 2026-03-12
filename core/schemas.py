from ninja import Schema
from pydantic import ConfigDict


class TaggedSchema(Schema):
    """Base for all discriminated union schemas. All variants must declare tag: Literal[...]."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str


class AppError(TaggedSchema):
    """Base for all API error responses. Subclasses narrow tag to a Literal."""

    detail: str
