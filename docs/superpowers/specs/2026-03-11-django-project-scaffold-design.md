# Django Project Scaffold Design

## Goal

Set up a modern Django development environment for learning, with proper tooling, Docker-managed PostgreSQL, and a guided workflow. The scaffold should be minimal but production-shaped — no features beyond what's needed to start building.

## Project Structure

```
learning-python-django/
├── .git/
├── .venv/                    # managed by uv
├── .python-version           # 3.13.12
├── .gitignore
├── .pre-commit-config.yaml
├── .env                      # local dev secrets (git-ignored)
├── .env.example              # template (committed)
├── pyproject.toml            # dependencies, ruff config, ty config
├── uv.lock
├── manage.py                 # Django entry point (moved to repo root)
├── docker-compose.yml        # PostgreSQL
├── Taskfile.yml              # task runner
├── project/                  # Django config package
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── README.md
```

Key decisions:
- `manage.py` at repo root (not nested under `project/`)
- Django apps created later live as sibling directories to `project/` at the repo root
- All tooling config in `pyproject.toml` where possible

## Python Version

Python 3.13.12 via uv. The `.python-version` file is read by uv automatically.

## Dependencies

### Runtime
- `django` (6.0.x)
- `django-ninja` (1.5.x)
- `psycopg[binary]` — PostgreSQL driver
- `python-dotenv` — loads `.env` into environment
- `dj-database-url` — parses `DATABASE_URL` env var into Django's `DATABASES` config

### Dev
- `ruff` — linting and formatting
- `ty` — type checking
- `pre-commit` — git hook framework

## Tooling Configuration

All in `pyproject.toml`:

### Ruff
- Linting with Django-relevant rules (DJ rule set)
- Formatting (replaces black + isort)

### ty
- Type checking configured in `pyproject.toml`

### Pre-commit (`.pre-commit-config.yaml`)
Runs on every commit:
1. `ruff check --fix` — lint with auto-fix
2. `ruff format` — formatting
3. `ty check` — type checking

## Database

PostgreSQL 17 in Docker Compose.

### `docker-compose.yml`
- PostgreSQL 17 image
- Persistent named volume for data
- Exposed on port 5432
- Credentials via environment variables in the compose file

### Environment Variables
- `.env` file at repo root (git-ignored) with:
  - `DATABASE_URL=postgres://postgres:postgres@localhost:5432/learning_django`
  - `SECRET_KEY=<generated-dev-key>`
  - `DEBUG=True`
- `.env.example` committed as a template with placeholder values
- `python-dotenv` loads `.env` in `settings.py`
- `dj-database-url` parses `DATABASE_URL` into Django's `DATABASES` dict

## Taskfile

| Task | Command | Description |
|------|---------|-------------|
| `task dev` | Starts db container + Django dev server | Single command to go from zero to working |
| `task db:start` | `docker compose up -d` | Start PostgreSQL |
| `task db:stop` | `docker compose down` | Stop PostgreSQL |
| `task db:migrate` | `uv run manage.py migrate` | Run migrations |
| `task db:makemigrations` | `uv run manage.py makemigrations` | Create new migrations |
| `task lint` | `uv run ruff check . && uv run ruff format --check .` | Check linting + formatting |
| `task lint:fix` | `uv run ruff check --fix . && uv run ruff format .` | Fix linting + format code |
| `task typecheck` | `uv run ty check` | Run type checker |
| `task test` | `uv run manage.py test` | Run Django tests |
| `task setup` | Install deps, copy .env.example, start db, migrate | One-time project setup |

All commands use `uv run` so the virtualenv is handled automatically.

## Django Ninja

Minimal wiring:
- `NinjaAPI` instance registered in `project/urls.py`
- One `GET /api/health` endpoint returning `{"status": "ok"}`
- No routers, apps, or schemas — added when needed

## .gitignore

- `__pycache__/`, `*.pyc` — Python bytecode
- `.venv/` — virtual environment
- `.env` — local secrets
- `staticfiles/`, `media/` — Django collected/uploaded files
