import functools
from typing import Annotated

from ninja import Schema
from pydantic import ConfigDict, Field


class TaggedSchema(Schema):
    """Base for all discriminated union schemas. All variants must declare tag: Literal[...]."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str


class AppError(TaggedSchema):
    """Base for all API error responses. Subclasses narrow tag to a Literal."""

    detail: str


def tagged_union(*schemas: type[TaggedSchema]):
    """Build a Pydantic discriminated union keyed on `tag`. Usage: tagged_union(A, B, C)."""
    union = functools.reduce(lambda a, b: a | b, schemas)  # type: ignore
    return Annotated[union, Field(discriminator="tag")]
