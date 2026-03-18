# TaggedModelSchema for Model-Backed Discriminated Unions

## Problem

`ModelSchema`-extending schemas (`AvailableProductSchema`, `OutOfStockProductSchema`, `DraftPostSchema`, `PublishedPostSchema`) don't benefit from the auto-tag infrastructure built for `TaggedSchema`. They use manual `Literal` type annotations, hand-wired `validation_alias` fields, and inconsistent naming (still carry `Schema` suffix). The blog schemas also discriminate on `status` directly, leaking internal Django choice codes (`"DF"` / `"PB"`) to the API.

## Design

### Approach: Duplicate `__init_subclass__` on a new `TaggedModelSchema` base

A new `TaggedModelSchema(ModelSchema)` class in `core/schemas.py` with the same `__init_subclass__` and `__get_pydantic_json_schema__` logic as `TaggedSchema`, plus an additional `tag_field` keyword for ORM field aliasing.

The logic is duplicated (~15 lines) rather than extracted into a mixin — clarity over DRY at this scale, avoids MRO complexity with Django Ninja's metaclass and Pydantic's model machinery.

### Core mechanism (`core/schemas.py`)

```python
from ninja import ModelSchema
from pydantic import ConfigDict, Field

class TaggedModelSchema(ModelSchema):
    """Base for discriminated union schemas backed by a Django model."""

    model_config = ConfigDict(populate_by_name=True)
    tag: str = ""

    @override
    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        # Same as TaggedSchema — ensures tag is required in OpenAPI
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        required = json_schema.setdefault("required", [])
        if "tag" in json_schema.get("properties", {}) and "tag" not in required:
            required.append("tag")
        return json_schema

    def __init_subclass__(cls, tag: str | None = None, tag_field: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        resolved_tag = tag or cls.__name__
        cls.__annotations__["tag"] = Literal[resolved_tag]
        if tag_field:
            cls.tag = Field(default=resolved_tag, validation_alias=tag_field)
        else:
            cls.tag = resolved_tag
        cls.model_rebuild()
```

The `tag_field` keyword wires up `validation_alias` automatically — when Django Ninja serializes a model instance, Pydantic reads the ORM field (e.g. `status`) and maps it to `tag`. The `Literal` type ensures only the expected value is accepted, and the discriminator on `tag` picks the correct union variant.

### Usage

```python
# Auto-derived tag "MySchema", no ORM aliasing
class MySchema(TaggedModelSchema):
    class Meta:
        model = MyModel
        fields = ["id", "name"]

# Explicit tag with ORM field aliasing
class AvailableProduct(TaggedModelSchema, tag="available", tag_field="status"):
    class Meta:
        model = Product
        exclude = ["status", "created", "updated"]
```

### Products (`products/schemas.py`)

Rename classes and migrate to `TaggedModelSchema`:

```python
from core.schemas import AppError, TaggedModelSchema
from products.models import Product

class AvailableProduct(TaggedModelSchema, tag="available", tag_field="status"):
    class Meta:
        model = Product
        exclude = ["status", "created", "updated"]

class OutOfStockProduct(TaggedModelSchema, tag="out_of_stock", tag_field="status"):
    class Meta:
        model = Product
        exclude = ["status", "stock_count", "created", "updated"]

class ProductResponse(RootModel[AvailableProduct | OutOfStockProduct]):
    pass
```

Changes from current:
- `AvailableProductSchema` → `AvailableProduct` (drop suffix)
- `OutOfStockProductSchema` → `OutOfStockProduct` (drop suffix)
- Remove `model_config = ConfigDict(populate_by_name=True)` (inherited from base)
- Remove manual `tag: Literal[...] = Field(validation_alias="status")` (handled by `tag_field` keyword)
- Tag values unchanged: `"available"`, `"out_of_stock"`

### Blog model change (`blog/models.py`)

Change `Status` choices from abbreviated codes to semantic values, and increase `max_length` to accommodate the longer values:

```python
class Status(models.TextChoices):
    DRAFT = "draft", "Draft"          # was "DF", "Draft"
    PUBLISHED = "published", "Published"  # was "PB", "Published"

status = models.CharField(max_length=20, choices=Status, default=Status.DRAFT)
# max_length was 2 — must increase to fit "published" (9 chars); 20 matches products
```

This requires a Django migration (field length change + data migration for existing rows: `"DF"` → `"draft"`, `"PB"` → `"published"`). The `tag_field="status"` aliasing then works directly — the ORM's `status` value (`"draft"` / `"published"`) matches the `tag` Literal.

### Blog schemas (new `blog/schemas.py`)

Extract from `blog/api.py` into a dedicated file, matching the pattern in orders and products:

```python
from core.schemas import AppError, TaggedModelSchema
from blog.models import Post

class DraftPost(TaggedModelSchema, tag="draft", tag_field="status"):
    class Meta:
        model = Post
        fields = ["id", "title", "slug", "updated"]

class PublishedPost(TaggedModelSchema, tag="published", tag_field="status"):
    class Meta:
        model = Post
        fields = ["id", "title", "slug", "body", "publish"]

class PostResponse(RootModel[DraftPost | PublishedPost]):
    pass

class PostNotFoundError(AppError):
    id: int
```

Changes from current:
- `DraftPostSchema` → `DraftPost` (drop suffix)
- `PublishedPostSchema` → `PublishedPost` (drop suffix)
- `status` field dropped from API response — `tag` replaces it as variant indicator
- `PostSchema` (Annotated union) → `PostResponse` (RootModel) — consistent with orders/products
- Discriminator changes from `status` to `tag`

### Blog API (`blog/api.py`)

Updated to import from `blog/schemas.py` and use `PostResponse`:

```python
from blog.schemas import PostNotFoundError, PostResponse

@router.get("/posts/", response=list[PostResponse])
def get_posts(request):
    return Post.objects.all()

@router.get("/post/{post_id}", response={200: PostResponse, 404: PostNotFoundError})
def get_post(request, post_id):
    ...
```

### Client

- Regenerate TypeScript types via hey-api
- Update `ts-pattern` files for new type/tag names

## Affected files

1. **`core/schemas.py`** — Add `TaggedModelSchema` class
2. **`core/tests.py`** — Add `TaggedModelSchema` unit tests
3. **`blog/models.py`** — Change `Status` choices to `"draft"` / `"published"`
4. **`blog/migrations/`** — New migration for status value change
5. **`blog/schemas.py`** — New file: `DraftPost`, `PublishedPost`, `PostResponse`, `PostNotFoundError`
6. **`blog/api.py`** — Remove inline schemas, import from `blog/schemas.py`, use `PostResponse`
7. **`blog/tests.py`** — Update for new class names, tag values, response structure
8. **`products/schemas.py`** — Migrate to `TaggedModelSchema`, rename classes
9. **`products/api.py`** — Update imports for renamed classes
10. **`products/tests.py`** — Update for new class names
11. **`client/`** — Regenerate TypeScript types
12. **`client/src/ts-pattern/posts.ts`** — Update for new tag/type names
13. **`client/src/ts-pattern/products.ts`** — Update for new type names

## Tag value changes

| Class (old → new) | Old tag | New tag | Source |
|---|---|---|---|
| `AvailableProductSchema` → `AvailableProduct` | `"available"` | `"available"` | explicit override |
| `OutOfStockProductSchema` → `OutOfStockProduct` | `"out_of_stock"` | `"out_of_stock"` | explicit override |
| `DraftPostSchema` → `DraftPost` | N/A (used `status: "DF"`) | `"draft"` | explicit override |
| `PublishedPostSchema` → `PublishedPost` | N/A (used `status: "PB"`) | `"published"` | explicit override |

Product tag values are unchanged. Blog switches from `status` discriminator to `tag` discriminator with human-readable values.

## Testing strategy

1. **`TaggedModelSchema` unit tests:**
   - Subclass without explicit tag gets `cls.__name__` as tag value and `Literal` type
   - Subclass with `tag="custom"` override gets the custom value
   - `tag_field` parameter correctly sets `validation_alias`
   - Tag value appears in serialized output (`.model_dump()` / `.model_json_schema()`)
   - Discriminated unions via `RootModel` work with auto-derived and explicit tags

2. **Products tests** — Update class names in imports and assertions

3. **Blog tests** — Update for new schema structure, tag-based discrimination, and `"draft"` / `"published"` values

4. **Integration** — Verify OpenAPI schema generates correct `tag` discriminator and named `PostResponse` / `ProductResponse` types
