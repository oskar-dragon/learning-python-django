from typing import Any, ClassVar, dataclass_transform

from core.schemas import TaggedSchema


@dataclass_transform()
class AppException(Exception):
    """Base for all domain errors. Subclass to define typed, raisable errors."""

    tag: ClassVar[str] = ""
    status: ClassVar[int] = 400
    Schema: ClassVar[type[TaggedSchema]]

    detail: str = ""

    def __init_subclass__(cls, status: int = 400, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.tag = cls.__name__
        cls.status = status

        own_annotations: dict[str, type] = {}
        for name, ann in cls.__annotations__.items():
            if name in ("tag", "detail", "status", "Schema"):
                continue
            own_annotations[name] = ann

        schema_namespace: dict[str, Any] = {
            "__annotations__": {"detail": str, **own_annotations},
        }
        for name in own_annotations:
            if hasattr(cls, name):
                schema_namespace[name] = getattr(cls, name)

        cls.Schema = type(cls.__name__, (TaggedSchema,), schema_namespace)

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)
        Exception.__init__(self, getattr(self, "detail", ""))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"tag": self.tag, "detail": self.detail}
        own_annotations = {
            k for k in type(self).__annotations__ if k not in ("tag", "detail", "status", "Schema")
        }
        for field in own_annotations:
            if hasattr(self, field):
                result[field] = getattr(self, field)
        return result
