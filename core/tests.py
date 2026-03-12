from django.test import TestCase

from core.exceptions import AppException
from core.schemas import AppError


class AppExceptionTest(TestCase):
    def test_stores_status_code_and_error(self) -> None:
        error = AppError(tag="test_error", detail="something went wrong")
        exc = AppException(404, error)
        self.assertEqual(exc.status_code, 404)
        self.assertIs(exc.error, error)

    def test_is_exception_subclass(self) -> None:
        error = AppError(tag="test_error", detail="something went wrong")
        exc = AppException(500, error)
        self.assertIsInstance(exc, Exception)
