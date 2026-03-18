from typing import Literal, get_type_hints

from django.test import TestCase
from pydantic import RootModel

from core.exceptions import AppException
from core.schemas import AppError, TaggedSchema


class TaggedSchemaAutoTagTest(TestCase):
    """Tests for TaggedSchema's __init_subclass__ auto-tag mechanism."""

    def test_subclass_gets_class_name_as_tag(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        instance = MySchema(value=1)  # pyright: ignore[reportCallIssue]
        self.assertEqual(instance.tag, "MySchema")

    def test_tag_has_literal_type(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        hints = get_type_hints(MySchema, include_extras=True)
        self.assertEqual(hints["tag"], Literal["MySchema"])

    def test_explicit_tag_override(self) -> None:
        class CustomSchema(TaggedSchema, tag="custom"):
            value: int

        instance = CustomSchema(value=1)  # pyright: ignore[reportCallIssue]
        self.assertEqual(instance.tag, "custom")

    def test_explicit_tag_override_has_literal_type(self) -> None:
        class CustomSchema(TaggedSchema, tag="custom"):
            value: int

        hints = get_type_hints(CustomSchema, include_extras=True)
        self.assertEqual(hints["tag"], Literal["custom"])

    def test_tag_included_in_model_dump(self) -> None:
        class MySchema(TaggedSchema):
            value: int

        data = MySchema(value=1).model_dump()  # pyright: ignore[reportCallIssue]
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
        error = AppError(detail="test")  # pyright: ignore[reportCallIssue]
        self.assertEqual(error.tag, "AppError")

    def test_intermediate_class_does_not_break_subclass_tags(self) -> None:
        class ConcreteError(AppError):
            code: int

        error = ConcreteError(detail="test", code=42)  # pyright: ignore[reportCallIssue]
        self.assertEqual(error.tag, "ConcreteError")
        self.assertNotEqual(error.tag, "AppError")


class AppExceptionTest(TestCase):
    def test_stores_status_code_and_error(self) -> None:
        class TestError(AppError):
            pass

        error = TestError(detail="something went wrong")  # pyright: ignore[reportCallIssue]
        exc = AppException(404, error)
        self.assertEqual(exc.status_code, 404)
        self.assertIs(exc.error, error)
        self.assertEqual(error.tag, "TestError")

    def test_is_exception_subclass(self) -> None:
        class TestError(AppError):
            pass

        error = TestError(detail="something went wrong")  # pyright: ignore[reportCallIssue]
        exc = AppException(500, error)
        self.assertIsInstance(exc, Exception)
