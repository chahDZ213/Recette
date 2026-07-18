# ADR-0005 — Plugins via Python entry points

Date: 2026-07-18 · Status: accepted

## Context

New ECU formats, tools and assistants must be addable without modifying the
core, by third parties as well as by the core team.

## Decision

Extensions are discovered through the standard `calforge.plugins` entry-point
group. An entry point resolves to a factory returning an object; typed
extension points (e.g. the `FormatIdentifier` protocol) filter loaded objects
by `isinstance` against a runtime-checkable protocol. Built-in extensions
(the generic binary identifier) register through the same mechanism, so the
third-party path is exercised on every application start. A broken plugin is
logged and skipped, never fatal. A source-tree fallback keeps the app working
when entry-point metadata is absent.

## Consequences

- Installing a plugin is `pip install`; no registry files, no core edits.
- Future extension points (map detectors, AI providers, report templates)
  reuse the same manager and conventions.
