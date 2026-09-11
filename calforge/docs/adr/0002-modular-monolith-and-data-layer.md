# ADR-0002 — Modular monolith, service boundary and data layer

Date: 2026-07-18 · Status: accepted

## Context

The product must evolve for years (plugins, AI assistants, cloud sync,
multi-user) without large rewrites, yet ship as a simple desktop app today.

## Decision

1. **Modular monolith with strict layering** (`core → data/analysis/formats →
   services → ui`). Lower layers never import higher ones. Composition happens
   only in `ApplicationContext`.
2. **Service boundary with DTOs**: SQLAlchemy models never cross the services
   layer; Pydantic DTOs (immutable) are the public contract. This is what
   later allows exposing the same services over an API without touching
   business logic.
3. **Explicit dependency injection** via a typed `ServiceRegistry` rather than
   a DI framework: wiring stays greppable and debuggable.
4. **Thread-safe services**: one short session per call
   (`Database.session()` context manager, commit/rollback automatic). The UI
   may call services from any worker thread.
5. **Event bus** (typed pub/sub) for cross-module notification; the UI
   marshals events to the GUI thread through a Qt bridge. The bus is
   synchronous and policy-free so it also works headless.
6. **SQLite in WAL mode** with `foreign_keys=ON`, busy timeout, scheduled
   online backups (SQLite backup API) with retention pruning.

## Consequences

- No hidden magic: a new engineer can follow every dependency by reading
  `app.py`.
- A future client/server split follows existing seams (services → API,
  bus → broker) instead of cutting through code.
