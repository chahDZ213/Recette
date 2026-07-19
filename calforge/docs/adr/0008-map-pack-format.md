# ADR-0008 — Open map pack format and definition matching

Date: 2026-07-19 · Status: accepted

## Context

Calibrators accumulate map definitions from many provenances (their own
work, community packs, commercial packs) and need them tied to the right
calibration files automatically. Proprietary formats lock users in; the
product requirement is several definition sources per ECU.

## Decision

1. **Open format**: ``calforge-pack/1`` — versioned JSON (``*.calpack.json``),
   validated by Pydantic models in ``calforge.packs``. Human-readable,
   diff-friendly, hand-editable; offsets accept ints or ``0x…`` strings;
   signature bytes accept hex or ``ascii:`` prefixed text. Import and export
   are lossless roundtrips, so CalForge can never hold definitions hostage.
2. **Sources are provenances**: one imported pack = one ``DefinitionSource``
   with its own matchers and maps. Multiple sources may cover the same ECU.
3. **Matching by strength**: a source applies to a file when ANY matcher
   matches; the strongest kind wins — exact SHA-256 (0.95) > byte signature
   (0.85) > file size (0.60). File content is only read when a signature
   matcher exists.
4. **Definitions feed the candidate store** (per ADR-0007): applying a pack
   creates *proposed* ``MapCandidateRecord`` rows carrying the match-derived
   confidence, a rationale naming the pack and match kind, and a
   ``definition_id`` link. Even a matched definition can be wrong for a
   file, so human validation stays in the loop; validated/rejected regions
   are never overridden or duplicated.
5. **Physical conversion lives in the definition**
   (``physical = raw × factor + value_offset``, plus ``unit``): the 2D view
   shows converted values with raw values in tooltips.

## Consequences

- One review UI (the candidate table) covers heuristics and definitions.
- Third parties can generate packs from any tooling that emits JSON.
- Future formats (Damos/A2L/ECM) become importers that translate into this
  model — no schema change required.
