from typing import Any, Literal, override

from ninja import Schema
from pydantic import ConfigDict, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema


class TaggedSchema(Schema):
    """Base for all discriminated union schemas. Subclasses auto-derive tag from class name."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str = ""

    @override
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        # Ensure 'tag' appears in 'required' so the generated TypeScript type is non-optional.
        # The field has a default for Python instantiation, but consumers must treat it as present.
        required: list[str] = json_schema.setdefault("required", [])
        if "tag" in json_schema.get("properties", {}) and "tag" not in required:
            required.append("tag")
        return json_schema

    def __init_subclass__(cls, tag: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        resolved_tag = tag or cls.__name__
        cls.__annotations__["tag"] = Literal[resolved_tag]
        cls.tag = resolved_tag
        _ = cls.model_rebuild()


class AppError(TaggedSchema):
    """Base for all API error responses. Subclasses narrow tag to a Literal."""

    detail: str
