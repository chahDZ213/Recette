# ADR-0004 — Facts vs hypotheses: no invented data, ever

Date: 2026-07-18 · Status: accepted

## Context

Calibration work is safety-relevant. A tool that guesses an ECU type, a map
location or a checksum scheme and presents the guess as truth is worse than
no tool. This is also the founding rule for every future AI feature.

## Decision

Every piece of derived information in CalForge is one of exactly two kinds:

- **Fact** — proven from file content alone (size, hashes, measured
  statistics). Stored in `identified_facts`.
- **Hypothesis** — a guess carrying a `confidence` ∈ [0, 1] **and** a
  human-readable `rationale`. Stored separately in `hypotheses`. Downstream
  features must never treat a hypothesis as true without explicit human
  validation.

The types (`IdentificationReport`, `Hypothesis`) enforce the split at the
API level; `Hypothesis` rejects out-of-range confidences at construction.

## Consequences

- Format identifiers, map detection (v0.3) and AI assistants (v0.5) all
  inherit this contract instead of re-inventing trust semantics.
- UI work: hypotheses must always render with confidence + rationale and a
  validation affordance. Facts render plainly.
