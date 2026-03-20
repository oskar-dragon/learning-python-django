from typing import Any, Literal, no_type_check, override

from ninja import Schema
from ninja.orm.factory import create_schema
from ninja.orm.metaclass import MetaConf, ModelSchemaMetaclass
from pydantic import ConfigDict, Field, GetJsonSchemaHandler
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


_is_tagged_model_schema_defined = False


class _TaggedModelSchemaMetaclass(ModelSchemaMetaclass):
    """Extends ModelSchemaMetaclass to process Meta on TaggedModelSchema subclasses.

    Tag logic lives here (not in __init_subclass__) because ninja's create_schema
    returns a dynamically-built class — __init_subclass__ would apply the tag to an
    intermediate class that gets thrown away.
    """

    @no_type_check
    def __new__(mcs, name, bases, namespace, **kwargs):
        tag = kwargs.pop("tag", None)
        tag_field = kwargs.pop("tag_field", None)

        # For the TaggedModelSchema base class itself, skip Meta processing.
        if not _is_tagged_model_schema_defined:
            return super(ModelSchemaMetaclass, mcs).__new__(mcs, name, bases, namespace, **kwargs)

        # Guard: only process classes that declare a Meta (user-defined subclasses).
        # create_schema calls pydantic.create_model which re-enters this metaclass
        # for the dynamic child — that child has no Meta, so we skip it here.
        has_tagged_base = any(issubclass(b, TaggedModelSchema) for b in bases)

        if has_tagged_base and "Meta" in namespace:
            meta_conf = MetaConf.from_schema_class(name, namespace)

            # Build the tag field so create_schema includes it in the Pydantic model.
            resolved_tag = tag or name
            tag_type = Literal[resolved_tag]
            if tag_field:
                tag_default = Field(default=resolved_tag, validation_alias=tag_field)
            else:
                tag_default = resolved_tag

            custom_fields = [("tag", tag_type, tag_default)]
            annotations = namespace.get("__annotations__", {})
            for attr_name, attr_type in annotations.items():
                if attr_name.startswith("_"):
                    continue
                default = namespace.get(attr_name, ...)
                custom_fields.append((attr_name, attr_type, default))

            cls = super(ModelSchemaMetaclass, mcs).__new__(mcs, name, bases, namespace, **kwargs)

            model_schema = create_schema(
                meta_conf.model,
                name=name,
                fields=meta_conf.fields,
                exclude=meta_conf.exclude,
                optional_fields=meta_conf.fields_optional,
                custom_fields=custom_fields,
                base_class=cls,
            )
            model_schema.__doc__ = cls.__doc__
            # Set the tag as a class attribute so it's accessible via MyModel.tag.
            # Pydantic field defaults aren't exposed as class attributes by default.
            model_schema.tag = resolved_tag
            return model_schema

        return super(ModelSchemaMetaclass, mcs).__new__(mcs, name, bases, namespace, **kwargs)


class TaggedModelSchema(Schema, metaclass=_TaggedModelSchemaMetaclass):
    """Base for discriminated union schemas backed by a Django model."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str = ""

    @override
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        required: list[str] = json_schema.setdefault("required", [])
        if "tag" in json_schema.get("properties", {}) and "tag" not in required:
            required.append("tag")
        return json_schema


_is_tagged_model_schema_defined = True
