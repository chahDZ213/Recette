# ADR-0006 — Unified vehicle history timeline

Date: 2026-07-18 · Status: accepted

## Context

A vehicle accumulates heterogeneous events: mechanical interventions,
diagnostics, road tests, datalogs, calibration steps, free notes. The
product requirement is a single chronological view ("what happened to this
car, in order"), fast to query even with years of records.

## Decision

One table, ``history_entries``, with a typed ``entry_type`` discriminator,
rather than one table per event kind. All kinds share the same shape
(when / what / details / optional project link); kind-specific structure, if
it ever appears (e.g. parsed datalog channels), will link *to* a timeline
entry instead of replacing it.

Indexed on ``(vehicle_id, occurred_at)`` — the only query pattern the UI
uses — so the timeline stays O(log n) regardless of volume.

## Consequences

- Adding a new event kind is one enum member + one label, no migration.
- The timeline query is a single indexed scan; no UNION over N tables.
- Rich per-kind payloads must be modelled as satellite tables later, which
  is deliberate: the timeline stays lean.
