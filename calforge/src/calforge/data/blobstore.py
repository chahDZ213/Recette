"""Content-addressed blob store for ECU binaries.

Files are stored once under their SHA-256 (``blobs/ab/abcdef…``), which gives
free deduplication, corruption detection and a layout that scales to hundreds
of thousands of files without huge directories. Writes are atomic
(temp file + rename) and blobs are marked read-only: an imported original can
never be silently altered — modified calibrations become *new* blobs.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1024 * 1024


class BlobIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StoredBlob:
    sha256: str
    size_bytes: int
    already_existed: bool


class BlobStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, sha256: str) -> Path:
        return self._root / sha256[:2] / sha256

    @staticmethod
    def hash_file(source: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as fh:
            while chunk := fh.read(_CHUNK_SIZE):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    def store_file(self, source: Path) -> StoredBlob:
        sha256, size = self.hash_file(source)
        target = self._path_for(sha256)
        if target.is_file():
            return StoredBlob(sha256=sha256, size_bytes=size, already_existed=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".import-")
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as out, source.open("rb") as fh:
                shutil.copyfileobj(fh, out, _CHUNK_SIZE)
                out.flush()
                os.fsync(out.fileno())
            os.chmod(tmp, 0o444)
            tmp.replace(target)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        logger.info("Stored blob %s (%d bytes)", sha256, size)
        return StoredBlob(sha256=sha256, size_bytes=size, already_existed=False)

    def store_bytes(self, data: bytes) -> StoredBlob:
        """Store an in-memory buffer (e.g. an edited calibration) as a blob.

        Same atomic, deduplicated, read-only guarantees as ``store_file`` — a
        modified map produces a new blob and never touches the original."""
        sha256 = hashlib.sha256(data).hexdigest()
        size = len(data)
        target = self._path_for(sha256)
        if target.is_file():
            return StoredBlob(sha256=sha256, size_bytes=size, already_existed=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".write-")
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.chmod(tmp, 0o444)
            tmp.replace(target)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        logger.info("Stored blob %s (%d bytes, in-memory)", sha256, size)
        return StoredBlob(sha256=sha256, size_bytes=size, already_existed=False)

    def open_path(self, sha256: str) -> Path:
        """Return the on-disk path of a blob, verifying it exists."""
        path = self._path_for(sha256)
        if not path.is_file():
            raise FileNotFoundError(f"Blob {sha256} missing from store")
        return path

    def read_bytes(self, sha256: str, *, verify: bool = False) -> bytes:
        path = self.open_path(sha256)
        data = path.read_bytes()
        if verify and hashlib.sha256(data).hexdigest() != sha256:
            raise BlobIntegrityError(f"Blob {sha256} is corrupted on disk")
        return data
