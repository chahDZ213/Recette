# ADR-0013 — Automatic Map Pack catalogue (fetch from entitled sources)

Date: 2026-07-20 · Status: accepted

## Context

Finding the right Map Pack / DAMOS by hand for every imported file is slow.
Users asked the app to locate and load a matching pack on its own — "aille sur
internet le trouve et le prenne tout seul" — to save time.

There is a hard line here. A tool that crawls the open web to download
copyrighted ECU calibration files (map packs, DAMOS, tuned binaries) facilitates
piracy, is legally hazardous, and no legitimate universal catalogue API exists
to make it honest. CalForge will not do that.

What *is* legitimate — and what shops actually want — is for the app to reach
into sources **the user already owns or is entitled to use**: the folder of
packs they built, a NAS share their team maintains, or a subscription URL they
pay for. Automating retrieval from those sources is pure time-saving with no
ethical or legal compromise.

## Decision

1. **Configured sources only** (``core.config.PacksConfig``). Two kinds:
   - ``catalogue_dirs``: local folders / mounted NAS / synced cloud drives
     holding ``*.calpack.json`` files, scanned and matched by file fingerprint.
   - ``catalogue_urls``: base URLs the user owns or subscribes to; the app
     requests ``<url>/<sha256>.calpack.json`` for the imported file's **exact**
     hash — so an online hit is, by construction, a pack for precisely that file.

2. **Off by default.** With no configured source and ``auto_fetch`` false, the
   app makes **zero** network calls. The catalogue does nothing until the user
   deliberately adds a source and opts in — surfaced in the Map Packs panel
   ("Catalogue automatique": add folder / add URL, an entitlement hint, and an
   "auto-fetch on import" checkbox).

3. **Injectable network** (``services.catalogue.CatalogueService``). The URL
   fetcher is a parameter (``Fetcher = (url, timeout) -> bytes | None``); the
   default ``http_fetch`` never raises and returns ``None`` on any error — a
   missing pack is a normal outcome, not a failure. Tests drive the whole
   feature with a fake fetcher and never touch the network.

4. **Same trust pipeline as manual import.** A fetched pack matches by the
   established ordering (exact SHA-256 > signature > size), is imported as a
   normal ``DefinitionSource``, and — when applied — re-proposes maps as
   *candidates* that still require human validation (ADR-0004, ADR-0008). The
   catalogue changes *where a pack comes from*, never *how much it is trusted*.

5. **Automatic on import, quietly.** When ``auto_fetch`` is on and a
   non-deduplicated file is imported, the main window fetches matching packs on
   a background thread and, on success, refreshes the views and reports the
   count in the status bar. A miss is silent.

## Consequences

- The app loads the right pack on its own for files a shop already has coverage
  for, with no manual hunting — the requested time-saving, delivered honestly.
- The honesty and legality lines hold: no open-web scraping of copyrighted
  files; every byte comes from a source the user configured and is entitled to.
- Because retrieval is entitlement-gated and off by default, privacy is the
  default: a user who never configures a source is never contacted over the
  network by this feature.
- The feature is fully testable offline, so it can evolve (more source kinds,
  richer matching) without ever depending on a live network in CI.
