# ADR-0001 — Technology stack

Date: 2026-07-18 · Status: accepted

## Context

CalForge is a professional Windows-first desktop application that must handle
multi-megabyte binaries, hundreds of thousands of files, background work and a
rich dockable UI, and remain maintainable by a large team for years.

## Decision

- **Python 3.13** — mandated; excellent ecosystem for binary analysis and AI.
- **PySide6 (Qt 6, Fusion + QSS dark theme)** — the only Python UI stack with
  professional-grade docking, model/view virtualisation for huge tables, and
  first-class threading primitives (`QThreadPool`, queued signals). LGPL.
- **SQLAlchemy 2 (typed ORM) + SQLite (WAL)** — zero-administration embedded
  database, safe concurrent reads, online backup API. The ORM keeps a future
  PostgreSQL migration a configuration change, not a rewrite.
- **Alembic** — schema migrations from day one; user databases survive every
  upgrade.
- **Pydantic v2** — validated configuration and immutable DTOs at the
  service boundary.
- **NumPy** — vectorised byte-level analysis (diff, statistics); pure-Python
  loops are 100× too slow for 8+ MiB dumps.
- **pytest + ruff** — test and lint gates; CI-ready.

## Consequences

- The UI layer is Qt-specific; everything below it is headless and reusable
  (CLI, server, tests run without a display).
- PySide6-Essentials only (no Addons) keeps the install small; revisit when
  3D views (v0.3) may need `QtDataVisualization` or a custom OpenGL widget.
