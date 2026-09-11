# ADR-0007 — Map detection: honest heuristics, deferred 3D

Date: 2026-07-19 · Status: accepted

## Context

Locating calibration maps without a definition file is inherently guesswork.
The product rule (ADR-0004) forbids presenting guesses as facts, and the
detector must scale to multi-MiB dumps interactively.

## Decision

1. **Pattern**: scan for the canonical layout — a strictly monotonic axis
   (8–32 elements, 8/16-bit, both endiannesses) immediately followed by a
   rectangular block whose rows vary smoothly (bounded second difference
   relative to value range). Constant and erased regions are rejected.
2. **Honesty by construction**: confidence is *capped at 0.85*
   (``MAX_CONFIDENCE``) — a heuristic can never reach certainty — and every
   candidate embeds a rationale ending with the explicit reminder that human
   validation is required.
3. **Human decisions are durable**: re-running detection replaces only
   *proposed* candidates; *validated*/*rejected* ones survive, and new
   proposals overlapping a decided region are dropped.
4. **2D now, 3D later**: validated candidates render as a colour-graded 2D
   table. True 3D surface rendering needs ``QtDataVisualization`` (PySide6
   Addons, +200 MB) or custom OpenGL; deferred until the definition-file
   milestone (v0.4) makes surfaces genuinely useful. Revisit then.

## Consequences

- False positives are expected and cheap to dismiss (one click, remembered
  forever); false negatives shrink as detectors improve without any schema
  change.
- Definition-file-based identification (v0.4) will register as additional
  higher-specificity detectors feeding the same candidate store.
