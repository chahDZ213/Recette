# ADR-0012 — Automatic Map Pack generation from evidence

Date: 2026-07-20 · Status: accepted

## Context

Users cannot always find a Map Pack / DAMOS / A2L online for a given ECU.
Research (and industry practice) is clear: no tool auto-generates a full pack
from a single original file. Humans build packs two ways — deep DAMOS/A2L
reverse engineering, or **comparing an original to a known-tuned file** and
recording the regions that changed. CalForge automates the second, honest,
evidence-based method.

## Decision

1. **Differential discovery** (``analysis.packbuilder``): given an original and
   one or more modified files, compute the changed byte ranges (real evidence
   an editor altered them) and intersect them with the heuristic detector's
   map geometries. A region backed by **both** signals — it changed AND looks
   like a map — is a strong candidate; a changed region with no matching
   geometry is still reported best-effort, clearly flagged, never as certain
   (ADR-0004).

2. **Two builders on the definition service**:
   - ``build_pack_from_comparison(original, [modified…])`` — learns from tuned
     files. Emits a pack matching the original by SHA-256 + size.
   - ``build_pack_from_validated(file)`` — captures the user's own validated
     maps into a reusable pack (the app learning from its operator).

3. **Same trust pipeline**: a generated pack is a normal ``DefinitionSource``.
   Applying it re-proposes maps as *candidates* that still require human
   validation — generation never bypasses ADR-0004. Packs export losslessly to
   the open ``calforge-pack/1`` format (ADR-0008) so they are shareable.

## Consequences

- CalForge can bootstrap its own Map Packs from the files a shop already has
  (an ori + any tuned version), instead of depending on paid packs.
- Accuracy scales with evidence: more tuned files for the same ECU → more
  changed regions confirmed → a richer, more reliable pack.
- The honesty contract holds end to end: discovery, generation and application
  all keep the human in the validation loop.
