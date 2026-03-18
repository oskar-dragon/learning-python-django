from typing import Any, Literal

from ninja import Schema
from pydantic import ConfigDict


class TaggedSchema(Schema):
    """Base for all discriminated union schemas. Subclasses auto-derive tag from class name."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str

    def __init_subclass__(cls, tag: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        resolved_tag = tag or cls.__name__
        cls.__annotations__["tag"] = Literal[resolved_tag]
        cls.tag = resolved_tag
        _ = cls.model_rebuild()


class AppError(TaggedSchema):
    """Base for all API error responses. Subclasses narrow tag to a Literal."""

    detail: str
