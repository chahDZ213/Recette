"""Automatic Map Pack catalogue (ADR-0013).

Fetches matching packs on the app's own initiative — but only from sources the
user configured and is entitled to use: local folders / NAS / synced drives,
and base URLs the user owns or subscribes to. It never scrapes the open web
for copyrighted ECU files.

A pack "matches" a file when one of its matchers matches (exact SHA-256 >
signature > size), reusing the same trust ordering as manual application. URL
sources use a hash convention (``<url>/<sha256>.calpack.json``), so an online
match is by construction the exact file.

Network access is fully injectable (``fetcher``) so the whole feature is tested
without a network, and disabled by default (no sources ⇒ no calls).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from calforge.core.config import PacksConfig
from calforge.packs import Pack, SignatureMatcher
from calforge.services.definitions import DefinitionService, PackImportError
from calforge.services.dto import DefinitionSourceDto, EcuFileDto
from calforge.services.ecufiles import EcuFileService

logger = logging.getLogger(__name__)

#: A fetcher returns the bytes at a URL, or None if not found / unreachable.
Fetcher = Callable[[str, float], bytes | None]


def http_fetch(url: str, timeout_s: float) -> bytes | None:
    """Default fetcher: GET ``url`` (honouring proxy env vars), None on any
    error or non-200. Never raises — a missing pack is a normal outcome."""
    try:
        with urlopen(Request(url, headers={"User-Agent": "CalForge"}), timeout=timeout_s) as resp:
            if resp.status != 200:
                return None
            return resp.read()
    except (URLError, TimeoutError, OSError, ValueError):
        return None


class CatalogueService:
    def __init__(
        self,
        definitions: DefinitionService,
        ecu_files: EcuFileService,
        config: PacksConfig,
        *,
        fetcher: Fetcher = http_fetch,
    ) -> None:
        self._definitions = definitions
        self._files = ecu_files
        self._config = config
        self._fetcher = fetcher

    @property
    def enabled(self) -> bool:
        return bool(self._config.catalogue_dirs or self._config.catalogue_urls)

    def fetch_for_file(self, file_id: int) -> list[DefinitionSourceDto]:
        """Find, import and return packs matching a file from all configured
        sources. Already-present packs (same name) are skipped silently."""
        file = self._files.get(file_id)
        data: bytes | None = None  # read lazily, only for signature matching
        imported: list[DefinitionSourceDto] = []

        for directory in self._config.catalogue_dirs:
            for path in sorted(Path(directory).glob("*.calpack.json")) if Path(directory).is_dir() else []:
                pack = self._load_pack(path.read_bytes(), source=str(path))
                if pack is None:
                    continue
                if data is None and self._pack_needs_content(pack):
                    data = self._files.read_content(file_id)
                if self._pack_matches(pack, file, data):
                    self._import(pack, imported, origin=str(path))

        for base_url in self._config.catalogue_urls:
            url = f"{base_url.rstrip('/')}/{file.sha256}.calpack.json"
            raw = self._fetcher(url, self._config.request_timeout_s)
            if raw is None:
                continue
            pack = self._load_pack(raw, source=url)
            if pack is not None:
                # URL keyed by exact hash ⇒ the match is by construction.
                self._import(pack, imported, origin=url)

        logger.info("Catalogue: %d pack(s) fetched for file #%d", len(imported), file_id)
        return imported

    # ------------------------------------------------------------ helpers --

    def _import(self, pack: Pack, into: list[DefinitionSourceDto], *, origin: str) -> None:
        try:
            into.append(self._definitions.import_pack_model(pack))
            logger.info("Catalogue imported pack %r from %s", pack.name, origin)
        except PackImportError:
            # Duplicate name (already imported) — not an error worth surfacing.
            logger.debug("Catalogue skipped already-present pack %r", pack.name)

    @staticmethod
    def _load_pack(raw: bytes, *, source: str) -> Pack | None:
        try:
            return Pack.model_validate(json.loads(raw.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Catalogue: invalid pack at %s (%s)", source, exc)
            return None

    @staticmethod
    def _pack_needs_content(pack: Pack) -> bool:
        return any(m.kind == "signature" for m in pack.matchers)

    @staticmethod
    def _pack_matches(pack: Pack, file: EcuFileDto, data: bytes | None) -> bool:
        for matcher in pack.matchers:
            if matcher.kind == "sha256" and matcher.sha256.lower() == file.sha256.lower():
                return True
            if matcher.kind == "size" and matcher.size == file.size_bytes:
                return True
            if matcher.kind == "signature" and data is not None:
                assert isinstance(matcher, SignatureMatcher)
                end = matcher.offset + len(matcher.pattern)
                if data[matcher.offset : end] == matcher.pattern:
                    return True
        return False
