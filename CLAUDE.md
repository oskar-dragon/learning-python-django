# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django Ninja API project exploring **typed discriminated union responses** with automatic OpenAPI schema generation. Python 3.13, Django 6.0, Django Ninja 1.5, PostgreSQL 17.

## Commands

```bash
task dev              # Start dev server (starts DB + runs migrations first)
task test             # Run all tests: uv run manage.py test
task lint             # Check ruff linting + formatting
task lint:fix         # Auto-fix ruff issues
task typecheck        # Run basedpyright
task setup            # Full setup: uv sync, pre-commit, DB, migrations
task generate:client  # Export OpenAPI schema + generate TypeScript client
```

Run a single test class or method:
```bash
uv run manage.py test core.tests.TaggedSchemaAutoTagTest
uv run manage.py test blog.tests.PostListApiTest.test_list_posts
```

Database: PostgreSQL via `docker-compose.yml` on port 5433.

## Architecture

### App Structure

Each Django app follows the same pattern:
- `models.py` — Django ORM models
- `api.py` — Django Ninja `Router` with endpoint definitions
- `schemas.py` — Pydantic response schemas (tagged discriminated unions)
- `exceptions.py` — Domain errors inheriting from `AppException`
- `tests.py` — Tests covering models, API, schemas, and exceptions
- `service.py` — (where needed) Business logic separated from endpoints

Routers are registered in `project/api.py` on the main `TaggedErrorAPI` instance.

### Tagged Discriminated Union System (`core/`)

The central pattern of this codebase. All API responses and errors use a `tag` field as a discriminator for Pydantic unions.

**`core/schemas.py`** — Two base classes:
- `TaggedSchema` — Plain Pydantic schemas with auto-assigned `tag: Literal["ClassName"]`
- `TaggedModelSchema` — ORM-backed schemas; supports `tag_field="status"` to alias the model's status field as the discriminator

**`core/exceptions.py`** — `AppException` base class:
- Domain errors are dataclass-like (support custom fields via annotations)
- Auto-generates Pydantic schemas for OpenAPI
- HTTP status configurable: `class MyError(AppException, status=404)`

**`core/decorators.py`** — `@raises(*exceptions)` decorator:
- Pure metadata (no runtime effect) — marks which domain errors an endpoint can raise
- Read during OpenAPI schema generation by `TaggedErrorAPI`

### TaggedErrorAPI (`project/api.py`)

Custom `NinjaExtraAPI` subclass that:
- Auto-injects framework error schemas (ValidationError, AuthenticationError, etc.) into every endpoint's OpenAPI spec
- Merges domain errors from `@raises()` into the schema
- Converts all `AppException` instances to tagged JSON responses

### Response Pattern

```python
# schemas.py — tagged variants per status
class DraftPost(TaggedModelSchema, tag="draft", tag_field="status"):
    class Meta:
        model = Post
        fields = [...]

class PublishedPost(TaggedModelSchema, tag="published", tag_field="status"):
    class Meta:
        model = Post
        fields = [...]

# Union type for the endpoint response
class PostResponse(RootModel[DraftPost | PublishedPost]):
    pass
```

### JWT Auth

Per-router: `Router(auth=JWTAuth())` for protected routes, plain `Router()` for public. OpenAPI reflects this (401/403 only on protected endpoints).

### Client (`client/`)

Bun-based TypeScript client. Generated from the OpenAPI schema via `task generate:client`. Has its own `CLAUDE.md` with Bun conventions.
