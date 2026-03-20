from collections.abc import Callable
from typing import TypeVar

from core.exceptions import AppException

RAISED_EXCEPTIONS_ATTR = "_raised_exceptions"

F = TypeVar("F", bound=Callable)


def raises(*exceptions: type[AppException]) -> Callable[[F], F]:
    """Mark an endpoint with the domain errors it can raise.

    Pure metadata — has no runtime effect. TaggedErrorAPI reads this
    during OpenAPI schema generation to inject error response schemas.
    """

    def decorator(func: F) -> F:
        setattr(func, RAISED_EXCEPTIONS_ATTR, exceptions)
        return func

    return decorator
