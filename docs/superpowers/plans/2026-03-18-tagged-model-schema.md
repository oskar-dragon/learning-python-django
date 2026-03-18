# TaggedModelSchema — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `TaggedModelSchema` base class for model-backed discriminated unions, migrate product and blog schemas to it, rename classes (drop `Schema` suffix), and switch blog from `status` discriminator to `tag` discriminator with semantic values.

**Architecture:** `TaggedModelSchema(ModelSchema)` duplicates `TaggedSchema`'s `__init_subclass__` auto-tag mechanism, adding a `tag_field` keyword that wires up `validation_alias` for ORM field → tag mapping. Blog model status values change from `"DF"`/`"PB"` to `"draft"`/`"published"`. Blog schemas extract to `blog/schemas.py`.

**Tech Stack:** Python 3.13, Django 6, Django Ninja, Pydantic v2, Hey API (TypeScript client generation), ts-pattern

**Spec:** `docs/superpowers/specs/2026-03-18-tagged-model-schema-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `core/schemas.py` | Modify | Add `TaggedModelSchema` class |
| `core/tests.py` | Modify | Add `TaggedModelSchema` unit tests |
| `blog/models.py` | Modify | Change `Status` choices + `max_length` |
| `blog/migrations/0002_*.py` | Create (auto) | Alter `status` field length + choices |
| `blog/migrations/0003_*.py` | Create | Data migration: `"DF"` → `"draft"`, `"PB"` → `"published"` |
| `blog/schemas.py` | Create | `DraftPost`, `PublishedPost`, `PostResponse`, `PostNotFoundError` |
| `blog/api.py` | Modify | Remove inline schemas, import from `blog/schemas.py` |
| `blog/tests.py` | Modify | Add blog API tests |
| `products/schemas.py` | Modify | Migrate to `TaggedModelSchema`, rename classes |
| `products/api.py` | Modify | Update imports for renamed classes |
| `products/tests.py` | No changes | Tag values unchanged, no schema names referenced |
| `client/openapi.json` | Regenerate | Export fresh OpenAPI schema |
| `client/src/generated/` | Regenerate | Regenerate TypeScript types |
| `client/src/ts-pattern/posts.ts` | Modify | Rewrite for `tag`-based discrimination |
| `client/src/ts-pattern/products.ts` | Modify | Update type names |

---

### Task 1: Add `TaggedModelSchema` to `core/schemas.py` (TDD)

**Files:**
- Modify: `core/tests.py`
- Modify: `core/schemas.py`

- [ ] **Step 1: Write failing tests for `TaggedModelSchema`**

Add a new test class to `core/tests.py`. These tests mirror the existing `TaggedSchemaAutoTagTest` pattern but test `TaggedModelSchema` specifically, including the `tag_field` keyword.

Note: `TaggedModelSchema` requires a `Meta` inner class on concrete subclasses (because it extends `ModelSchema`). Use `blog.Post` as the model since it's a simple model available in the test DB.

```python
from core.schemas import AppError, TaggedModelSchema, TaggedSchema


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

        data = MyModel(id=1, title="Test", tag="MyModel").model_dump()
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
        instance = AliasedModel.model_validate(
            {"id": 1, "title": "Test", "status": "draft"}
        )
        self.assertEqual(instance.tag, "draft")

    def test_tag_field_default_still_works(self) -> None:
        """Even with tag_field, constructing without the alias should use the default."""

        class AliasedModel(TaggedModelSchema, tag="draft", tag_field="status"):
            class Meta:
                model = Post
                fields = ["id", "title"]

        instance = AliasedModel(id=1, title="Test")
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
```

Add `from blog.models import Post` to the imports at the top of the file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run manage.py test core -v2`

Expected: FAIL — `TaggedModelSchema` does not exist yet.

- [ ] **Step 3: Implement `TaggedModelSchema` in `core/schemas.py`**

Add after the `AppError` class:

```python
from ninja import ModelSchema, Schema
from pydantic import ConfigDict, Field, GetJsonSchemaHandler


class TaggedModelSchema(ModelSchema):
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

    def __init_subclass__(cls, tag: str | None = None, tag_field: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        resolved_tag = tag or cls.__name__
        cls.__annotations__["tag"] = Literal[resolved_tag]
        if tag_field:
            cls.tag = Field(default=resolved_tag, validation_alias=tag_field)
        else:
            cls.tag = resolved_tag
        _ = cls.model_rebuild()
```

Update the imports at the top of `core/schemas.py` — add `ModelSchema` to the `from ninja import` line, add `Field` to the `from pydantic import` line.

**Important:** `TaggedModelSchema` extends `ModelSchema`, which requires a `Meta` inner class on concrete subclasses. The base class itself does not need `Meta` — Django Ninja's metaclass handles this. If this causes issues at import time, we'll need to add a dummy `Meta` class. The spike will tell us.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run manage.py test core -v2`

Expected: All tests pass (both existing `TaggedSchemaAutoTagTest` and new `TaggedModelSchemaAutoTagTest`).

- [ ] **Step 5: Commit**

```bash
git add core/schemas.py core/tests.py
git commit -m "feat: add TaggedModelSchema with tag_field keyword for ORM aliasing"
```

---

### Task 2: Migrate products to `TaggedModelSchema` (rename classes)

**Files:**
- Modify: `products/schemas.py`
- Modify: `products/api.py`
- Modify: `products/tests.py`

- [ ] **Step 1: Run existing product tests to establish baseline**

Run: `uv run manage.py test products -v2`

Expected: All pass.

- [ ] **Step 2: Update `products/schemas.py`**

Replace the entire file with:

```python
from pydantic import RootModel

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


class ProductNotFoundError(AppError):
    id: int


class ProductHiddenError(AppError):
    id: int
```

Changes from current:
- `AvailableProductSchema` → `AvailableProduct`
- `OutOfStockProductSchema` → `OutOfStockProduct`
- Now extends `TaggedModelSchema` instead of `ModelSchema`
- Manual `model_config`, `tag: Literal[...] = Field(validation_alias="status")` removed — handled by `tag_field` keyword
- Removed imports: `Literal`, `ModelSchema`, `ConfigDict`, `Field`

- [ ] **Step 3: Update `products/api.py`**

Update the import on line 6. The only name that changed in the import is the schema — `ProductResponse` is unchanged, error classes are unchanged:

```python
from products.schemas import ProductHiddenError, ProductNotFoundError, ProductResponse
```

No other changes needed — the API file doesn't reference `AvailableProductSchema` or `OutOfStockProductSchema` directly.

- [ ] **Step 4: Run product tests**

Run: `uv run manage.py test products -v2`

Expected: All tests pass. Tag values are unchanged (`"available"`, `"out_of_stock"`), so no test assertion updates needed.

- [ ] **Step 5: Commit**

```bash
git add products/schemas.py products/api.py
git commit -m "refactor(products): migrate to TaggedModelSchema, rename classes (drop Schema suffix)"
```

---

### Task 3: Change blog model status values + migration

**Files:**
- Modify: `blog/models.py`
- Create: `blog/migrations/0002_*.py` (auto-generated)
- Create: `blog/migrations/0003_*.py` (data migration)

- [ ] **Step 1: Update `blog/models.py`**

Change the `Status` choices and field `max_length`:

In the `Status` class, change:
```python
DRAFT = "DF", "Draft"
PUBLISHED = "PB", "Published"
```
to:
```python
DRAFT = "draft", "Draft"
PUBLISHED = "published", "Published"
```

Change the `status` field's `max_length` from `2` to `20`:
```python
status = models.CharField(max_length=20, choices=Status, default=Status.DRAFT)
```

- [ ] **Step 2: Create the schema migration**

Run: `uv run manage.py makemigrations blog -n alter_status_field`

Expected: Creates `blog/migrations/0002_alter_status_field.py` with `AlterField` for `status`.

- [ ] **Step 3: Create the data migration**

Run: `uv run manage.py makemigrations blog --empty -n migrate_status_values`

This creates an empty migration file. Edit it to contain:

```python
from django.db import migrations


def migrate_status_values(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    Post.objects.filter(status="DF").update(status="draft")
    Post.objects.filter(status="PB").update(status="published")


def reverse_status_values(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    Post.objects.filter(status="draft").update(status="DF")
    Post.objects.filter(status="published").update(status="PB")


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0002_alter_status_field"),
    ]

    operations = [
        migrations.RunPython(migrate_status_values, reverse_status_values),
    ]
```

**Note:** The dependency name must match the actual filename generated in Step 2.

- [ ] **Step 4: Run migrations**

Run: `uv run manage.py migrate blog`

Expected: Both migrations apply successfully.

- [ ] **Step 5: Verify data migration**

Run: `uv run manage.py shell -c "from blog.models import Post; print(list(Post.objects.values_list('status', flat=True)))"`

Expected: All values are `"draft"` or `"published"` (no `"DF"` or `"PB"`). If the DB is empty, the output is `[]` — that's fine.

- [ ] **Step 6: Commit**

```bash
git add blog/models.py blog/migrations/
git commit -m "refactor(blog): change status values to semantic names (draft/published)"
```

---

### Task 4: Create `blog/schemas.py` and update `blog/api.py`

**Files:**
- Create: `blog/schemas.py`
- Modify: `blog/api.py`

- [ ] **Step 1: Create `blog/schemas.py`**

```python
from pydantic import RootModel

from blog.models import Post
from core.schemas import AppError, TaggedModelSchema


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

- [ ] **Step 2: Update `blog/api.py`**

Replace the entire file with:

```python
from django.http import HttpRequest
from ninja import Router

from blog.models import Post
from blog.schemas import PostNotFoundError, PostResponse

router = Router()


@router.get("/posts/", response=list[PostResponse])
def get_posts(request: HttpRequest):
    return Post.objects.all()


@router.get("/post/{post_id}", response={200: PostResponse, 404: PostNotFoundError})
def get_post(request: HttpRequest, post_id: int):
    try:
        return 200, Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return 404, {
            "tag": "PostNotFoundError",
            "detail": f"Post with id {post_id} not found",
            "id": post_id,
        }
```

Changes from current:
- Removed inline schema classes (`DraftPostSchema`, `PublishedPostSchema`, `PostNotFoundError`)
- Removed `PostSchema` Annotated union
- Removed unused imports (`Annotated`, `Literal`, `ModelSchema`, `Field`, `AppError`)
- Added imports from `blog.schemas`
- Response types changed: `PostSchema` → `PostResponse`

- [ ] **Step 3: Run blog tests (smoke check)**

Run: `uv run manage.py test blog -v2`

Expected: Passes (blog/tests.py is empty, but this catches import errors).

- [ ] **Step 4: Commit**

```bash
git add blog/schemas.py blog/api.py
git commit -m "refactor(blog): extract schemas to blog/schemas.py, use TaggedModelSchema"
```

---

### Task 5: Add blog API tests (TDD)

**Files:**
- Modify: `blog/tests.py`

Blog currently has no API tests. Add comprehensive tests that verify the new `tag`-based discrimination and `PostResponse` structure.

- [ ] **Step 1: Write blog API tests**

Replace `blog/tests.py` with:

```python
from typing import override

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from blog.models import Post

User = get_user_model()


class PostModelTest(TestCase):
    def test_create_draft_post(self) -> None:
        user = User.objects.create_user(username="author", password="pass123!")
        post = Post.objects.create(
            title="Draft Post",
            slug="draft-post",
            author=user,
            body="Content",
            status=Post.Status.DRAFT,
        )
        self.assertEqual(post.status, "draft")

    def test_create_published_post(self) -> None:
        user = User.objects.create_user(username="author", password="pass123!")
        post = Post.objects.create(
            title="Published Post",
            slug="published-post",
            author=user,
            body="Content",
            status=Post.Status.PUBLISHED,
        )
        self.assertEqual(post.status, "published")

    def test_published_manager_filters_correctly(self) -> None:
        user = User.objects.create_user(username="author", password="pass123!")
        _ = Post.objects.create(
            title="Draft",
            slug="draft",
            author=user,
            body="Content",
            status=Post.Status.DRAFT,
        )
        pub = Post.objects.create(
            title="Published",
            slug="published",
            author=user,
            body="Content",
            status=Post.Status.PUBLISHED,
        )
        self.assertEqual(list(Post.published.all()), [pub])

    def test_str_returns_title(self) -> None:
        post = Post(title="My Post")
        self.assertEqual(str(post), "My Post")


class BlogListAPITest(TestCase):
    @override
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="author", password="pass123!")
        self.draft = Post.objects.create(
            title="Draft Post",
            slug="draft-post",
            author=self.user,
            body="Draft body",
            status=Post.Status.DRAFT,
        )
        self.published = Post.objects.create(
            title="Published Post",
            slug="published-post",
            author=self.user,
            body="Published body",
            status=Post.Status.PUBLISHED,
            publish=timezone.now(),
        )

    def test_list_returns_all_posts(self) -> None:
        response = self.client.get("/api/blog/posts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)

    def test_draft_post_has_tag_draft(self) -> None:
        response = self.client.get("/api/blog/posts/")
        draft = next(p for p in response.json() if p["title"] == "Draft Post")
        self.assertEqual(draft["tag"], "draft")

    def test_published_post_has_tag_published(self) -> None:
        response = self.client.get("/api/blog/posts/")
        pub = next(p for p in response.json() if p["title"] == "Published Post")
        self.assertEqual(pub["tag"], "published")

    def test_draft_post_includes_updated(self) -> None:
        response = self.client.get("/api/blog/posts/")
        draft = next(p for p in response.json() if p["tag"] == "draft")
        self.assertIn("updated", draft)

    def test_published_post_includes_body_and_publish(self) -> None:
        response = self.client.get("/api/blog/posts/")
        pub = next(p for p in response.json() if p["tag"] == "published")
        self.assertIn("body", pub)
        self.assertIn("publish", pub)

    def test_draft_post_excludes_body(self) -> None:
        response = self.client.get("/api/blog/posts/")
        draft = next(p for p in response.json() if p["tag"] == "draft")
        self.assertNotIn("body", draft)

    def test_status_not_in_response(self) -> None:
        """status field should not be exposed — tag replaces it."""
        response = self.client.get("/api/blog/posts/")
        for post in response.json():
            self.assertNotIn("status", post)


class BlogDetailAPITest(TestCase):
    @override
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="author", password="pass123!")
        self.draft = Post.objects.create(
            title="Draft Post",
            slug="draft-post",
            author=self.user,
            body="Draft body",
            status=Post.Status.DRAFT,
        )
        self.published = Post.objects.create(
            title="Published Post",
            slug="published-post",
            author=self.user,
            body="Published body",
            status=Post.Status.PUBLISHED,
            publish=timezone.now(),
        )

    def test_get_draft_post(self) -> None:
        response = self.client.get(f"/api/blog/post/{self.draft.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "draft")
        self.assertEqual(data["title"], "Draft Post")

    def test_get_published_post(self) -> None:
        response = self.client.get(f"/api/blog/post/{self.published.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "published")
        self.assertEqual(data["title"], "Published Post")

    def test_get_nonexistent_post_returns_404(self) -> None:
        response = self.client.get("/api/blog/post/99999")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["tag"], "PostNotFoundError")
        self.assertEqual(data["id"], 99999)
```

- [ ] **Step 2: Run blog tests**

Run: `uv run manage.py test blog -v2`

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add blog/tests.py
git commit -m "test(blog): add comprehensive blog API tests for tag-based discrimination"
```

---

### Task 6: Run full test suite and type checker

- [ ] **Step 1: Run all tests**

Run: `uv run manage.py test -v2`

Expected: All tests pass across core, orders, products, blog.

- [ ] **Step 2: Run type checker**

Run: `uv run basedpyright`

Expected: No new errors. Note any existing errors but ensure none are introduced by this change.

- [ ] **Step 3: Commit (if any fixups were needed)**

Only commit if type checker revealed issues that needed fixing.

---

### Task 7: Regenerate TypeScript client and update ts-pattern files

**Files:**
- Regenerate: `client/openapi.json`
- Regenerate: `client/src/generated/`
- Modify: `client/src/ts-pattern/posts.ts`
- Modify: `client/src/ts-pattern/products.ts`

- [ ] **Step 1: Start the dev server (needed for OpenAPI export)**

Run: `task db:start` (ensure DB is running for schema export).

- [ ] **Step 2: Export OpenAPI schema and regenerate client**

Run from project root:

```bash
task generate:client
```

This runs `uv run manage.py export_openapi_schema > client/openapi.json`, then `bun install` and `bunx @hey-api/openapi-ts` in the client directory.

- [ ] **Step 3: Verify generated types**

Check that the generated types reflect the changes:

1. `DraftPostSchema` → `DraftPost` with `tag: 'draft'` (not `status: 'DF'`)
2. `PublishedPostSchema` → `PublishedPost` with `tag: 'published'` (not `status: 'PB'`)
3. `PostResponse = DraftPost | PublishedPost` (named union, not inlined)
4. `AvailableProductSchema` → `AvailableProduct` (name change in generated types)
5. `OutOfStockProductSchema` → `OutOfStockProduct` (name change in generated types)
6. `ProductResponse = AvailableProduct | OutOfStockProduct`

Run: `grep -n "DraftPost\|PublishedPost\|AvailableProduct\|OutOfStockProduct\|PostResponse\b" client/src/generated/types.gen.ts`

- [ ] **Step 4: Update `client/src/ts-pattern/posts.ts`**

Rewrite to use `tag`-based discrimination instead of `status`. Replace the entire file with:

```typescript
import { match } from "ts-pattern";
import type {
  DraftPost,
  PublishedPost,
  PostNotFoundError,
  PostResponse,
} from "../generated/types.gen";

// Example 1: match on the PostResponse discriminated union.
// Demonstrates: ts-pattern matches on the `tag` discriminant field.
// The `tag` field narrows the type — `p.updated` is only available on DraftPost,
// `p.body` and `p.publish` only on PublishedPost.
function describePost(post: PostResponse): string {
  return match(post)
    .with(
      { tag: "draft" },
      (p) => `Draft: ${p.title}, last updated ${p.updated}`,
    )
    .with(
      { tag: "published" },
      (p) => `Published: ${p.title} on ${p.publish ?? "TBD"}`,
    )
    .exhaustive();
}

// Example 2: match on errors only.
function describeError(error: PostNotFoundError): string {
  return match(error)
    .with(
      { tag: "PostNotFoundError" },
      (e) => `Post ${e.id} not found: ${e.detail}`,
    )
    .exhaustive();
}

// Example 3: combined success + error match in one exhaustive chain.
function handlePostResult(result: PostResponse | PostNotFoundError): string {
  return match(result)
    .with({ tag: "draft" }, (p) => `Draft: ${p.title}`)
    .with({ tag: "published" }, (p) => `Published: ${p.title}`)
    .with(
      { tag: "PostNotFoundError" },
      (e) => `Not found: post ${e.id} — ${e.detail}`,
    )
    .exhaustive();
}
```

Key changes:
- Import `PostResponse` and `DraftPost`/`PublishedPost` (new names)
- All discrimination on `tag` instead of `status`
- Removed placeholder `AuthError`/`ValidationError` types — they were TODOs
- Simplified error example to just `PostNotFoundError`

- [ ] **Step 5: Update `client/src/ts-pattern/products.ts`**

Update the type import names. Tag values are unchanged (`"available"`, `"out_of_stock"`). Replace the imports:

```typescript
import type {
  ProductResponse,
  ProductsApiGetProductError,
} from "../generated/types.gen";
```

The import names may have changed in the generated types — verify after Step 3. The body of the file should not need changes since tag values and the `ProductResponse` name are unchanged. If hey-api still generates `AvailableProductSchema` as the type name (despite the Python class rename), no changes needed. If it generates `AvailableProduct`, update the comments only.

- [ ] **Step 6: Type-check TypeScript**

Run from `client/`:

```bash
bun run tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 7: Commit**

```bash
git add client/
git commit -m "refactor(client): regenerate types for TaggedModelSchema migration, update ts-pattern"
```
