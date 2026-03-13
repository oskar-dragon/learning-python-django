# Plan: Django Ninja Obsidian Presentation

## Context

Oskar wants a pitch deck to convince his team to adopt Django Ninja over vanilla Django. The core argument is that Django Ninja solves a specific set of pain points: API boilerplate, manual schema/DTO definition that duplicates model data, lack of type safety across the stack, and messy error handling scattered across views.

The presentation should be a slide-deck-style Obsidian markdown file using `---` slide separators (Obsidian core Slides plugin). Each slide must be minimal — one concept, brief bullets, short code snippets — because the font is too large and content overflows the screen.

---

## Structure (12 slides)

1. **Title** — "Django Ninja: The Missing Layer"
2. **The Problem** — what vanilla Django forces you to do
3. **Enter Django Ninja** — what it is and what it gives you
4. **ModelSchema** — auto-derive schemas from models, no duplication
5. **Polymorphic Responses** — discriminated unions, typed by status
6. **Typed Errors** — per-status-code response schemas, no generic 400s
7. **FilterSchema** — declarative query param filters, no manual Q() wiring
8. **Global Exception Handling** — one handler, no try/except in endpoints
9. **OpenAPI → TypeScript** — free type-safe client generation
10. **Architecture** — api → service → model, clean layers
11. **What We Built** — summary of what exists in this repo
12. **Verdict** — recommendation slide

---

## Output File

`/Users/oskardragon-work/workspaces/oskar-dragon/learning-python-django/docs/presentations/django-ninja-pitch.md`

---

## Key Content Sources

- `products/schemas.py` — ModelSchema + RootModel pattern
- `products/api.py` — router auth, multi-status response dict
- `core/schemas.py` — TaggedSchema, AppError base classes
- `core/exceptions.py` — AppException base
- `orders/schemas.py` (planned) — FilterSchema, full discriminated union
- `orders/api.py` (planned) — thin endpoints, global exception flow
- `docs/superpowers/specs/2026-03-12-orders-app-design.md` — architecture diagram

---

## Slide Design Rules

- Max ~5 bullet points per slide
- Code snippets: max 8–10 lines
- One callout block per slide max (for emphasis)
- Use `---` between slides (Obsidian Slides separator)
- Use `> [!tip]` / `> [!warning]` callouts for contrast
- No prose paragraphs — bullets only
