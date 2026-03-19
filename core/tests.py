from typing import Literal, get_type_hints

from django.test import TestCase
from pydantic import RootModel

from blog.models import Post
from core.exceptions import AppException
from core.schemas import AppError, TaggedModelSchema, TaggedSchema


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

    def test_intermediate_class_gets_own_tag(self) -> None:
        """AppError is an intermediate class — it should get tag='AppError'."""
        error = AppError(detail="test")
        self.assertEqual(error.tag, "AppError")

    def test_intermediate_class_does_not_break_subclass_tags(self) -> None:
        class ConcreteError(AppError):
            code: int

        error = ConcreteError(detail="test", code=42)
        self.assertEqual(error.tag, "ConcreteError")
        self.assertNotEqual(error.tag, "AppError")


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
    def test_stores_error(self) -> None:
        class TestError(AppError):
            pass

        error = TestError(detail="something went wrong")
        exc = AppException(error)
        self.assertIs(exc.error, error)
        self.assertEqual(error.tag, "TestError")

    def test_is_exception_subclass(self) -> None:
        class TestError(AppError):
            pass

        error = TestError(detail="something went wrong")
        exc = AppException(error)
        self.assertIsInstance(exc, Exception)
