# ADR-0010 — Reporting: HTML source of truth, Qt-native PDF, no new deps

Date: 2026-07-19 · Status: accepted

## Context

The product must produce professional client deliverables (vehicle folder
report, comparison report) as PDF, plus data exports (CSV/JSON), without
bloating dependencies or breaking the honest facts-vs-hypotheses rule.

## Decision

1. **HTML is the single source of truth** (``reporting.documents``): pure
   functions from DTOs to a self-contained HTML string, Qt-free and fully
   unit-testable headless. The markup is restricted to a Qt-rich-text-safe
   subset (tables, headings, inline styles) so one template renders correctly
   both in a browser and as PDF.
2. **PDF via Qt only** (``reporting.pdf``): ``QTextDocument`` +
   ``QPdfWriter`` — already in PySide6-Essentials — instead of adding
   ReportLab or WeasyPrint. Zero new dependency, works offscreen, output is a
   real ``%PDF``.
3. **Honesty carried into deliverables**: every report lists *validated* maps
   as facts and flags difference regions overlapping known maps; a standing
   disclaimer states that hypotheses are not certainties. Reports never invent
   data — they render what the services already hold.
4. **Exports are lossless-ish snapshots**: JSON mirrors the vehicle folder
   structure; CSV targets spreadsheets. Both are pure-Python and testable.

## Consequences

- Reports stay testable without a display; only the thin PDF step needs Qt.
- Richer future templates (charts, logos) must stay within Qt rich text, or
  grow a second renderer — an explicit, contained trade-off recorded here.
