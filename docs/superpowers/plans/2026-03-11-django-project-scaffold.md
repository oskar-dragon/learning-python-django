# Django Project Scaffold Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a modern Django development environment with uv, ruff, ty, Django Ninja, pre-commit hooks, Docker PostgreSQL, and Taskfile.

**Architecture:** Flat repo structure with `manage.py` at root, `project/` as the Django config package, and apps as sibling directories. All tooling config in `pyproject.toml`. PostgreSQL runs in Docker Compose, managed via Taskfile tasks. Environment variables loaded from `.env` via `python-dotenv`.

**Tech Stack:** Python 3.13.12, Django 6.0.x, Django Ninja 1.5.x, PostgreSQL 17 (Docker), uv, ruff, ty, pre-commit, Taskfile, python-dotenv, dj-database-url

**Spec:** `docs/superpowers/specs/2026-03-11-django-project-scaffold-design.md`

---

## Chunk 1: Project Restructure and Foundation

### Task 1: Move manage.py and config package to repo root

Currently the project has `project/manage.py` and `project/project/` (config package). We need `manage.py` at the repo root and `project/` as a top-level config package.

**Why:** Having `manage.py` at the repo root means you run `uv run manage.py <command>` directly. The `project/project/` nesting goes away — `project/` becomes the Django config package (holds settings, urls, wsgi, asgi).

**Files:**
- Move: `project/manage.py` -> `manage.py`
- Move: `project/project/__init__.py` -> `project/__init__.py`
- Move: `project/project/settings.py` -> `project/settings.py`
- Move: `project/project/urls.py` -> `project/urls.py`
- Move: `project/project/wsgi.py` -> `project/wsgi.py`
- Move: `project/project/asgi.py` -> `project/asgi.py`
- Delete: `project/project/` (empty directory after moves)
- Delete: `main.py` (uv scaffold boilerplate, not needed)

- [ ] **Step 1: Move the config package files up one level**

```bash
mv project/project/__init__.py project/__init__.py
mv project/project/settings.py project/settings.py
mv project/project/urls.py project/urls.py
mv project/project/wsgi.py project/wsgi.py
mv project/project/asgi.py project/asgi.py
rm -r project/project/
```

No naming conflicts here — nothing exists at the destination paths yet.

- [ ] **Step 2: Move manage.py to repo root**

```bash
mv project/manage.py manage.py
```

- [ ] **Step 3: Delete main.py**

```bash
rm main.py
```

- [ ] **Step 4: Verify the structure looks right**

```bash
ls -la
ls -la project/
```

Expected structure:
```
.
├── manage.py
├── project/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── pyproject.toml
├── ...
```

- [ ] **Step 5: Verify Django still starts (will fail on DB but should load settings)**

```bash
uv run manage.py check
```

Expected: System check output (may warn about unapplied migrations, but no import errors).

- [ ] **Step 6: Commit**

```bash
git rm main.py
git rm -r project/project/
git add manage.py project/
git status
git commit -m "refactor: move manage.py to repo root and flatten config package"
```

Note: `git rm` stages the deletion. `git add` stages the new/moved files. Check `git status` before committing to make sure it looks right.

### Task 2: Update Python version to 3.13.12

**Why:** We decided on 3.13.12 (latest stable 3.13) instead of the current 3.13 (which may resolve to an older patch).

**Files:**
- Modify: `.python-version`
- Modify: `pyproject.toml` (verify `requires-python` is correct)

- [ ] **Step 1: Update .python-version**

Write `3.13` to `.python-version` (uv resolves this to the latest 3.13.x installed).

Note: uv reads this file and uses it to select the Python interpreter. Writing `3.13` lets uv pick the latest 3.13 patch you have installed (3.13.12).

- [ ] **Step 2: Recreate virtualenv with the correct Python**

```bash
uv sync
```

- [ ] **Step 3: Verify Python version**

```bash
uv run python --version
```

Expected: `Python 3.13.12` (or whichever latest 3.13 patch is installed).

- [ ] **Step 4: Commit**

```bash
git add .python-version
git commit -m "chore: pin Python to 3.13"
```

### Task 3: Add .gitignore

**Why:** Prevents committing generated files, virtual environments, and secrets.

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Write .gitignore**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo

# Virtual environment
.venv/

# Environment secrets
.env

# Django
staticfiles/
media/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
```

---

## Chunk 2: Dependencies and Environment Configuration

### Task 4: Add runtime dependencies

**Why:** We need the PostgreSQL driver (`psycopg`), env file loading (`python-dotenv`), and database URL parsing (`dj-database-url`). Django and django-ninja are already installed.

**Files:**
- Modify: `pyproject.toml` (via `uv add`)

- [ ] **Step 1: Add runtime dependencies**

```bash
uv add "psycopg[binary]" python-dotenv dj-database-url
```

**What these do:**
- `psycopg[binary]`: PostgreSQL database driver. The `[binary]` extra includes pre-compiled C extensions so you don't need PostgreSQL dev headers installed.
- `python-dotenv`: Reads `.env` files and loads key-value pairs into `os.environ`.
- `dj-database-url`: Parses a `DATABASE_URL` string (like `postgres://user:pass@host:port/dbname`) into the dictionary format Django's `DATABASES` setting expects.

- [ ] **Step 2: Add dev dependencies**

```bash
uv add --dev ruff ty pre-commit
```

**What these do:**
- `ruff`: An extremely fast Python linter and formatter (written in Rust). Replaces flake8, black, isort, and many other tools.
- `ty`: A type checker for Python (from the same team as ruff). Still early but works.
- `pre-commit`: A framework for managing git pre-commit hooks. Runs checks automatically before each commit.

- [ ] **Step 3: Verify everything installed**

```bash
uv run python -c "import psycopg; import dotenv; import dj_database_url; print('All imports OK')"
uv run ruff --version
uv run ty --version
uv run pre-commit --version
```

Expected: All imports succeed, all tools print their version.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add runtime and dev dependencies"
```

### Task 5: Create .env.example and .env

**Why:** `.env.example` is a committed template showing what environment variables the project needs. `.env` is the actual secrets file (git-ignored) that each developer creates locally.

**Files:**
- Create: `.env.example`
- Create: `.env`

- [ ] **Step 1: Create .env.example**

```env
# Django
SECRET_KEY=change-me-to-a-real-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://postgres:postgres@localhost:5432/learning_django
```

- [ ] **Step 2: Generate a SECRET_KEY and create .env**

```bash
SECRET_KEY=$(uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
```

Then create `.env`:

```env
# Django
SECRET_KEY=<the generated key>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://postgres:postgres@localhost:5432/learning_django
```

**What is SECRET_KEY?** Django uses it for cryptographic signing (sessions, CSRF tokens, etc.). Each developer should have their own. In production this would be a real secret — for local dev it just needs to be unique.

- [ ] **Step 3: Verify .env is git-ignored**

```bash
git check-ignore .env
```

Expected: `.env` is printed (meaning it's ignored).

- [ ] **Step 4: Commit .env.example**

```bash
git add .env.example
git commit -m "chore: add .env.example template"
```

### Task 6: Update settings.py for environment variables and PostgreSQL

**Why:** Replace hardcoded settings with values from `.env`. Switch database from SQLite to PostgreSQL via `DATABASE_URL`.

**Files:**
- Modify: `project/settings.py`

- [ ] **Step 1: Add dotenv and dj-database-url to settings.py**

Replace everything in `project/settings.py` from the opening docstring through `ALLOWED_HOSTS = []` (lines 1-28) with:

```python
"""
Django settings for project.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ["SECRET_KEY"]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
```

**What's happening here:**
- `load_dotenv(BASE_DIR / ".env")` reads the `.env` file and puts its values into `os.environ`.
- `os.environ["SECRET_KEY"]` reads SECRET_KEY — if it's missing, Python raises `KeyError` immediately (fail loudly).
- `DEBUG` defaults to `False` if not set (safe default).
- `ALLOWED_HOSTS` is parsed from a comma-separated string.

- [ ] **Step 2: Replace the DATABASES setting**

Replace the existing `DATABASES` block:

```python
# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": dj_database_url.parse(
        os.environ["DATABASE_URL"],
        conn_max_age=600,
        conn_health_checks=True,
    ),
}
```

**What's happening:**
- `os.environ["DATABASE_URL"]` fails loudly if not set.
- `dj_database_url.parse()` converts the URL string into the dict Django expects.
- `conn_max_age=600` keeps database connections open for 10 minutes (performance).
- `conn_health_checks=True` verifies a reused connection is still alive before using it.

- [ ] **Step 3: Verify settings load correctly**

```bash
uv run manage.py check
```

Expected: May fail if PostgreSQL isn't running yet — but it should NOT fail on import errors or missing env vars. If you see `KeyError`, your `.env` file is missing or not being loaded.

- [ ] **Step 4: Commit**

```bash
git add project/settings.py
git commit -m "feat: configure settings for env vars and PostgreSQL"
```

---

## Chunk 3: Docker and Database

### Task 7: Add docker-compose.yml for PostgreSQL

**Why:** Run PostgreSQL in a container so you don't need to install it on your Mac. The data persists in a Docker volume across container restarts.

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:17
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: learning_django
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

**What's happening:**
- `image: postgres:17` — pulls the official PostgreSQL 17 image.
- `ports: "5432:5432"` — maps container port 5432 to your Mac's port 5432, so Django can connect via `localhost:5432`.
- `environment` — sets up the database user, password, and database name. These match what's in your `.env` file's `DATABASE_URL`.
- `volumes: pgdata` — a named volume that persists your data even if you `docker compose down`. Delete it with `docker volume rm` if you want a fresh database.

- [ ] **Step 2: Start PostgreSQL**

```bash
docker compose up -d
```

Expected: Container starts. Verify with `docker compose ps` — should show the `db` service as "running".

- [ ] **Step 3: Verify Django can connect**

```bash
uv run manage.py check
```

Expected: "System check identified no issues." (Or warnings about unapplied migrations, which is fine.)

- [ ] **Step 4: Run initial migrations**

```bash
uv run manage.py migrate
```

Expected: A list of migrations being applied (auth, admin, sessions, etc.). This creates the default Django tables in PostgreSQL.

**What are migrations?** Django tracks database schema changes in migration files. `migrate` applies any unapplied migrations to bring your database up to date. The default Django apps (auth, admin, sessions, etc.) come with their own migrations.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add Docker Compose for PostgreSQL"
```

---

## Chunk 4: Tooling Configuration

### Task 8: Configure ruff and ty in pyproject.toml

**Why:** Ruff handles linting (finding bugs and style issues) and formatting (consistent code style). ty handles type checking. Both are configured in `pyproject.toml` so there are no extra config files.

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add ruff configuration**

Add to the end of `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "DJ"]
```

**What these rules mean:**
- `E` — pycodestyle errors (basic Python style issues like whitespace, line length)
- `F` — pyflakes (likely bugs like unused imports, undefined names)
- `I` — isort (import ordering — keeps your imports sorted and grouped)
- `DJ` — Django-specific rules (common Django mistakes)

- [ ] **Step 2: Add ty configuration**

Add to `pyproject.toml`:

```toml
[tool.ty]
```

This is an empty section for now. ty works with sensible defaults. We're leaving it here as a placeholder so you know where to configure it later.

- [ ] **Step 3: Test ruff on existing code**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: May find issues in the generated Django code. If it does, fix them:

```bash
uv run ruff check --fix .
uv run ruff format .
```

- [ ] **Step 4: Test ty on existing code**

```bash
uv run ty check
```

Expected: May produce some diagnostics. Note them — ty is still early and can be noisy on Django code.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml project/
git commit -m "chore: configure ruff and ty"
```

Note: `git add project/` stages any formatting fixes ruff made to Django files.

### Task 9: Set up pre-commit hooks

**Why:** Pre-commit hooks run automatically before each `git commit`, catching issues before they get into the codebase. We use local hooks with `uv run` so the same tool versions from your project are used.

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Create .pre-commit-config.yaml**

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run --no-sync ruff check --fix
        language: system
        types: [python]
      - id: ruff-format
        name: ruff format
        entry: uv run --no-sync ruff format
        language: system
        types: [python]
      - id: ty-check
        name: ty check
        entry: uv run --no-sync ty check
        language: system
        types: [python]
        pass_filenames: false
```

**What's happening:**
- `repo: local` — hooks run from your local environment (not downloaded from a remote repo).
- `entry: uv run --no-sync ...` — runs the tool via uv. `--no-sync` prevents uv from checking/installing deps on every commit (faster).
- `language: system` — tells pre-commit the command is already available on the system.
- `types: [python]` — only runs on `.py` files.
- `pass_filenames: false` on ty — ty checks the whole project, not individual files.

- [ ] **Step 2: Install the hooks**

```bash
uv run pre-commit install
```

Expected: "pre-commit installed at .git/hooks/pre-commit"

This installs a git hook that runs `pre-commit` before every commit. You never need to run ruff/ty manually again — they run automatically.

- [ ] **Step 3: Test the hooks**

```bash
uv run pre-commit run --all-files
```

Expected: All three hooks run and (hopefully) pass. If ruff finds issues, it will auto-fix them — you'll need to stage the fixes and re-run.

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit hooks for ruff and ty"
```

---

## Chunk 5: Taskfile

### Task 10: Create Taskfile.yml

**Why:** Wraps common commands so you don't need to remember the exact `uv run manage.py ...` syntax. `task dev` starts everything, `task lint` checks your code, etc.

**Files:**
- Create: `Taskfile.yml`

- [ ] **Step 1: Create Taskfile.yml**

```yaml
version: "3"

tasks:
  dev:
    desc: Start database and Django dev server
    deps: [db:start]
    cmds:
      - uv run manage.py runserver

  db:start:
    desc: Start PostgreSQL container
    cmds:
      - docker compose up -d

  db:stop:
    desc: Stop PostgreSQL container
    cmds:
      - docker compose down

  db:migrate:
    desc: Run Django migrations
    cmds:
      - uv run manage.py migrate

  db:makemigrations:
    desc: Create new Django migrations
    cmds:
      - uv run manage.py makemigrations

  lint:
    desc: Check linting and formatting
    cmds:
      - uv run ruff check .
      - uv run ruff format --check .

  lint:fix:
    desc: Fix linting issues and format code
    cmds:
      - uv run ruff check --fix .
      - uv run ruff format .

  typecheck:
    desc: Run type checker
    cmds:
      - uv run ty check

  test:
    desc: Run Django tests
    cmds:
      - uv run manage.py test

  setup:
    desc: One-time project setup
    cmds:
      - uv sync
      - uv run pre-commit install
      - cmd: cp .env.example .env
        ignore_error: true
      - task: _generate-secret-key
      - task: db:start
      - defer: { task: db:stop }
      - uv run manage.py migrate

  _generate-secret-key:
    desc: Generate SECRET_KEY in .env if it's still the placeholder
    internal: true
    cmds:
      - |
        if grep -q "change-me-to-a-real-secret-key" .env 2>/dev/null; then
          uv run python -c "
          from django.core.management.utils import get_random_secret_key
          key = get_random_secret_key()
          with open('.env', 'r') as f:
              content = f.read()
          content = content.replace('change-me-to-a-real-secret-key', key)
          with open('.env', 'w') as f:
              f.write(content)
          "
          echo "Generated new SECRET_KEY"
        else
          echo "SECRET_KEY already set, skipping"
        fi
```

**What's happening:**
- `task dev` — depends on `db:start` (starts PostgreSQL first), then runs the Django dev server.
- `task setup` — the full first-time setup flow: install deps, install git hooks, create `.env` from template (skips if `.env` already exists via `ignore_error`), generate a real `SECRET_KEY` if it's still the placeholder, start the database, run migrations, then stop the database with `defer`.
- `_generate-secret-key` — `internal: true` means it won't show in `task --list` (it's a helper, not meant to be run directly).

- [ ] **Step 2: Verify task commands work**

```bash
task --list
```

Expected: All tasks listed with their descriptions.

- [ ] **Step 3: Test `task lint`**

```bash
task lint
```

Expected: Ruff runs and reports any issues.

- [ ] **Step 4: Commit**

```bash
git add Taskfile.yml
git commit -m "feat: add Taskfile for common dev commands"
```

---

## Chunk 6: Django Ninja Health Endpoint

### Task 11: Wire up Django Ninja with a health endpoint

**Why:** A health endpoint proves the entire stack works end-to-end: Django loads, Django Ninja routes work, and you can hit the API. It's also useful later for Docker health checks or monitoring.

**Files:**
- Create: `project/api.py`
- Modify: `project/urls.py`

- [ ] **Step 1: Write the failing test**

Create `project/tests.py`:

```python
from django.test import TestCase


class HealthCheckTest(TestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
```

**What's happening:** Django's test `Client` sends an HTTP GET to `/api/health` and checks the response. This test will fail because the endpoint doesn't exist yet.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run manage.py test project.tests
```

Expected: FAIL — `404` because the route doesn't exist yet.

- [ ] **Step 3: Create the API module**

Create `project/api.py`:

```python
from ninja import NinjaAPI

api = NinjaAPI()


@api.get("/health")
def health(request):
    return {"status": "ok"}
```

**What's happening:**
- `NinjaAPI()` creates an API instance. This is the central object that holds all your routes.
- `@api.get("/health")` registers a GET endpoint at `/health` (relative to where the API is mounted in urls.py).
- The function returns a dict — Django Ninja automatically serializes it to JSON.

- [ ] **Step 4: Mount the API in urls.py**

Replace `project/urls.py`:

```python
from django.contrib import admin
from django.urls import path

from project.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
```

**What's happening:**
- `api.urls` generates Django URL patterns from all the routes registered on the `api` object.
- `path("api/", api.urls)` mounts them at `/api/`, so the health endpoint is at `/api/health`.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run manage.py test project.tests
```

Expected: PASS — 1 test, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add project/api.py project/urls.py project/tests.py
git commit -m "feat: add Django Ninja API with health endpoint"
```

---

## Chunk 7: End-to-End Verification

### Task 12: Verify the full stack works

**Why:** Make sure everything works together before calling the scaffold done.

- [ ] **Step 1: Start the database**

```bash
task db:start
```

Expected: PostgreSQL container running.

- [ ] **Step 2: Run migrations**

```bash
task db:migrate
```

Expected: "No migrations to apply." (already migrated in Task 7).

- [ ] **Step 3: Run all tests**

```bash
task test
```

Expected: All tests pass.

- [ ] **Step 4: Run linting and type checking**

```bash
task lint
task typecheck
```

Expected: No errors from ruff. ty may have some diagnostics on Django code — that's expected (ty is still early).

- [ ] **Step 5: Start the dev server**

```bash
task dev
```

Expected: Django dev server starts at `http://127.0.0.1:8000/`.

- [ ] **Step 6: Test the health endpoint**

In another terminal:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected: `{"status": "ok"}`

- [ ] **Step 7: Check the API docs**

Open `http://127.0.0.1:8000/api/docs` in your browser.

Expected: Django Ninja's auto-generated Swagger UI showing the health endpoint. This is one of the nice things about Django Ninja — you get interactive API docs for free.

- [ ] **Step 8: Stop the dev server and database**

Press `Ctrl+C` to stop the dev server, then:

```bash
task db:stop
```

- [ ] **Step 9: Final commit if any files changed**

```bash
git status
```

If anything changed during verification, commit it.
