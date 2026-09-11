# ADR-0003 — Content-addressed blob store for ECU binaries

Date: 2026-07-18 · Status: accepted

## Context

The application must scale to hundreds of thousands of ECU files, guarantee
that an imported original can never be corrupted or silently altered, and
deduplicate the very frequent case of the same dump being imported repeatedly.

## Decision

Binaries live outside the database in a content-addressed store:
`blobs/<sha256[:2]>/<sha256>`, written atomically (temp file + fsync +
rename) and chmod'ed read-only. Database rows reference blobs by SHA-256;
several records may share one blob. Reads can verify integrity by re-hashing.

Modified calibrations are always *new* blobs — history is append-only.

## Consequences

- Free deduplication and corruption detection; directories stay small
  (256-way fan-out).
- The database stays compact (metadata only), keeping backups fast.
- Garbage collection of unreferenced blobs is deliberately deferred: disk is
  cheap, user data is not. A vacuum tool can be added later.
- The layout maps 1:1 onto object storage (S3 keys) for future cloud sync.
