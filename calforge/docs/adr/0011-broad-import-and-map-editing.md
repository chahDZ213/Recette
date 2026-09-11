# ADR-0011 — Universal import and non-destructive map editing

Date: 2026-07-20 · Status: accepted

## Context

Professional calibrators work with files from every ECU, make, year and read
tool — `.ori`, `.bin`, full BDM/boot dumps, and dozens of proprietary
extensions. They cannot afford an import that silently rejects a file. They
also need to *modify* a calibration when a definition pack is unavailable, and
to do so without any risk to the original read.

## Decision

1. **Universal import**: the import accepts *any* file. The file dialog
   defaults to "Tous les fichiers"; a long known-extension list is a
   convenience shortcut only, never a filter. The pipeline never rejects by
   extension, size or content — the generic identifier always matches
   (ADR-0005), so an unknown format is imported and described by measured
   facts, not refused.

2. **Non-destructive editing**: a map edit never mutates the source blob
   (ADR-0003). ``encode_block`` returns a *new* byte string with the block
   overwritten (values clamped to the storage type's range); the analysis
   service stores it as a **new** content-addressed blob and creates a
   MODIFIED ``EcuFile`` derivative linked to its parent. The original read is
   byte-for-byte preserved and always recoverable.

3. **Raw-value editing**: cells are edited as raw stored values — exactly what
   is written to the binary — so an edit is unambiguous. When a definition
   supplies a factor/offset, the physical value is shown in the tooltip; the
   binary is the single source of truth.

4. **Percentage tooling + export**: bulk "+X %" on a selection or the whole
   map covers the most common tuning operation; the edited file can be
   exported to disk in any name/extension the user chooses.

## Consequences

- CalForge opens on any car's dump without configuration friction.
- Editing is safe by construction: the original can never be corrupted, and
  every modification is a traceable, versioned derivative.
- Detection still governs *what* is editable and stays a validated hypothesis
  (ADR-0004/0007) — editing does not bypass human validation.
