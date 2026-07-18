from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Must be set before any Qt import for headless test environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from calforge.app import ApplicationContext  # noqa: E402
from calforge.core.config import AppConfig  # noqa: E402


@pytest.fixture
def app_config(tmp_path: Path) -> AppConfig:
    return AppConfig(data_dir=tmp_path / "data", log_dir=tmp_path / "logs")


@pytest.fixture
def context(app_config: AppConfig) -> Iterator[ApplicationContext]:
    ctx = ApplicationContext(config=app_config)
    yield ctx
    ctx.database.dispose()


@pytest.fixture
def sample_bin(tmp_path: Path) -> Path:
    path = tmp_path / "sample.bin"
    path.write_bytes(bytes(range(256)) * 64)  # 16 KiB deterministic content
    return path
