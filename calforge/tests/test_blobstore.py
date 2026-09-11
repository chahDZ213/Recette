from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from calforge.data.blobstore import BlobIntegrityError, BlobStore


def test_store_and_read_roundtrip(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "blobs")
    source = tmp_path / "file.bin"
    payload = b"\x01\x02\x03calibration"
    source.write_bytes(payload)

    stored = store.store_file(source)

    assert stored.sha256 == hashlib.sha256(payload).hexdigest()
    assert stored.size_bytes == len(payload)
    assert not stored.already_existed
    assert store.read_bytes(stored.sha256, verify=True) == payload


def test_store_deduplicates(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "blobs")
    source = tmp_path / "file.bin"
    source.write_bytes(b"same content")

    first = store.store_file(source)
    second = store.store_file(source)

    assert first.sha256 == second.sha256
    assert not first.already_existed
    assert second.already_existed


def test_missing_blob_raises(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "blobs")
    with pytest.raises(FileNotFoundError):
        store.open_path("0" * 64)


def test_corruption_detected(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "blobs")
    source = tmp_path / "file.bin"
    source.write_bytes(b"original")
    stored = store.store_file(source)

    blob_path = store.open_path(stored.sha256)
    blob_path.chmod(0o644)
    blob_path.write_bytes(b"tampered")

    with pytest.raises(BlobIntegrityError):
        store.read_bytes(stored.sha256, verify=True)
