from typing import Literal, get_type_hints

from django.test import TestCase
from pydantic import RootModel

from blog.models import Post
from core.exceptions import AppException
from core.schemas import TaggedModelSchema, TaggedSchema


class TaggedSchemaAutoTagTest(TestCase):
    """Tests for TaggedSchema's __init_subclass__ auto-tag mechanism."""

    def test_subclass_gets_class_name_as_tag(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        instance = MySchema(value=1)
        self.assertEqual(instance.tag, "MySchema")

    def test_tag_has_literal_type(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        hints = get_type_hints(MySchema, include_extras=True)
        self.assertEqual(hints["tag"], Literal["MySchema"])

    def test_explicit_tag_override(self) -> None:
        class CustomSchema(TaggedSchema, tag="custom"):
            value: int

        instance = CustomSchema(value=1)
        self.assertEqual(instance.tag, "custom")

    def test_explicit_tag_override_has_literal_type(self) -> None:
        class CustomSchema(TaggedSchema, tag="custom"):
            value: int

        hints = get_type_hints(CustomSchema, include_extras=True)
        self.assertEqual(hints["tag"], Literal["custom"])

    def test_tag_included_in_model_dump(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        data = MySchema(value=1).model_dump()
        self.assertEqual(data["tag"], "MySchema")

    def test_tag_in_json_schema(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        schema = MySchema.model_json_schema()
        tag_prop = schema["properties"]["tag"]
        self.assertEqual(tag_prop["const"], "MySchema")

    def test_discriminated_union_with_root_model(self) -> None:
        class AlphaSchema(TaggedSchema):
            a: int

        class BetaSchema(TaggedSchema):
            b: str

        Union = RootModel[AlphaSchema | BetaSchema]

        alpha = Union.model_validate({"tag": "AlphaSchema", "a": 42})
        self.assertIsInstance(alpha.root, AlphaSchema)

        beta = Union.model_validate({"tag": "BetaSchema", "b": "hello"})
        self.assertIsInstance(beta.root, BetaSchema)


class TaggedModelSchemaAutoTagTest(TestCase):
    """Tests for TaggedModelSchema's __init_subclass__ auto-tag mechanism."""

    def test_subclass_gets_class_name_as_tag(self) -> None:
        class MyModel(TaggedModelSchema):
            class Meta:
                model = Post
                fields = ["id", "title"]

        self.assertEqual(MyModel.tag, "MyModel")

    def test_tag_has_literal_type(self) -> None:
        class MyModel(TaggedModelSchema):
            class Meta:
                model = Post
                fields = ["id", "title"]

        hints = get_type_hints(MyModel, include_extras=True)
        self.assertEqual(hints["tag"], Literal["MyModel"])

    def test_explicit_tag_override(self) -> None:
        class CustomModel(TaggedModelSchema, tag="custom"):
            class Meta:
                model = Post
                fields = ["id", "title"]

        self.assertEqual(CustomModel.tag, "custom")

    def test_explicit_tag_override_has_literal_type(self) -> None:
        class CustomModel(TaggedModelSchema, tag="custom"):
            class Meta:
                model = Post
                fields = ["id", "title"]

        hints = get_type_hints(CustomModel, include_extras=True)
        self.assertEqual(hints["tag"], Literal["custom"])

    def test_tag_included_in_model_dump(self) -> None:
        class MyModel(TaggedModelSchema):
            class Meta:
                model = Post
                fields = ["id", "title"]

        data = MyModel.model_validate({"id": 1, "title": "Test", "tag": "MyModel"}).model_dump()
        self.assertEqual(data["tag"], "MyModel")

    def test_tag_in_json_schema(self) -> None:
        class MyModel(TaggedModelSchema):
            class Meta:
                model = Post
                fields = ["id", "title"]

        schema = MyModel.model_json_schema()
        tag_prop = schema["properties"]["tag"]
        self.assertEqual(tag_prop["const"], "MyModel")

    def test_tag_field_sets_validation_alias(self) -> None:
        """tag_field keyword should allow populating tag from a different field name."""

        class AliasedModel(TaggedModelSchema, tag="draft", tag_field="status"):
            class Meta:
                model = Post
                fields = ["id", "title"]

        # Construct using the aliased field name (as Pydantic would receive from ORM)
        instance = AliasedModel.model_validate({"id": 1, "title": "Test", "status": "draft"})
        self.assertEqual(instance.tag, "draft")

    def test_tag_field_default_still_works(self) -> None:
        """Even with tag_field, constructing without the alias should use the default."""

        class AliasedModel(TaggedModelSchema, tag="draft", tag_field="status"):
            class Meta:
                model = Post
                fields = ["id", "title"]

        instance = AliasedModel.model_validate({"id": 1, "title": "Test"})
        self.assertEqual(instance.tag, "draft")

    def test_discriminated_union_with_root_model(self) -> None:
        class AlphaModel(TaggedModelSchema, tag="alpha"):
            class Meta:
                model = Post
                fields = ["id", "title"]

        class BetaModel(TaggedModelSchema, tag="beta"):
            class Meta:
                model = Post
                fields = ["id", "title"]

        Union = RootModel[AlphaModel | BetaModel]

        alpha = Union.model_validate({"tag": "alpha", "id": 1, "title": "A"})
        self.assertIsInstance(alpha.root, AlphaModel)

        beta = Union.model_validate({"tag": "beta", "id": 2, "title": "B"})
        self.assertIsInstance(beta.root, BetaModel)


class AppExceptionTest(TestCase):
    def test_subclass_gets_class_name_as_tag(self) -> None:
        class TestError(AppException):
            code: int

        self.assertEqual(TestError.tag, "TestError")

    def test_stores_fields_from_kwargs(self) -> None:
        class TestError(AppException):
            code: int

        exc = TestError(code=42, detail="something went wrong")
        self.assertEqual(exc.detail, "something went wrong")
        self.assertEqual(exc.code, 42)

    def test_to_dict_includes_tag_detail_and_fields(self) -> None:
        class TestError(AppException):
            code: int

        exc = TestError(code=42, detail="something went wrong")
        self.assertEqual(
            exc.to_dict(),
            {"tag": "TestError", "detail": "something went wrong", "code": 42},
        )

    def test_is_exception_subclass(self) -> None:
        class TestError(AppException):
            code: int

        exc = TestError(code=42, detail="test")
        self.assertIsInstance(exc, Exception)

    def test_raise_and_catch(self) -> None:
        class TestError(AppException):
            code: int

        with self.assertRaises(AppException) as ctx:
            raise TestError(code=42, detail="test")
        self.assertEqual(ctx.exception.tag, "TestError")

    def test_default_status_is_400(self) -> None:
        class TestError(AppException):
            code: int

        self.assertEqual(TestError.status, 400)

    def test_custom_status(self) -> None:
        class TestError(AppException, status=404):
            code: int

        self.assertEqual(TestError.status, 404)

    def test_auto_generates_schema(self) -> None:
        class TestError(AppException):
            code: int

        schema = TestError.Schema
        instance = schema(code=42, detail="test")
        dump = instance.model_dump()
        self.assertEqual(dump["tag"], "TestError")
        self.assertEqual(dump["code"], 42)
        self.assertEqual(dump["detail"], "test")

    def test_schema_json_schema_has_const_tag(self) -> None:
        class TestError(AppException):
            code: int

        json_schema = TestError.Schema.model_json_schema()
        self.assertEqual(json_schema["properties"]["tag"]["const"], "TestError")

    def test_detail_defaults_to_empty_string(self) -> None:
        class TestError(AppException):
            pass

        exc = TestError()
        self.assertEqual(exc.detail, "")

    def test_detail_uses_subclass_default(self) -> None:
        class TestError(AppException):
            detail: str = "Custom default"

        exc = TestError()
        self.assertEqual(exc.detail, "Custom default")
