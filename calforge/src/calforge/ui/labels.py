"""Backward-compatible re-export of the shared label maps.

The canonical definitions live in :mod:`calforge.labels` (a presentation-neutral
leaf module) so non-UI layers may use them without importing the UI package.
UI modules keep importing from here.
"""

from __future__ import annotations

from calforge.labels import (
    CANDIDATE_STATUS_LABELS,
    CATEGORY_LABELS,
    ENTRY_TYPE_LABELS,
    KIND_LABELS,
    STATUS_LABELS,
)

__all__ = [
    "CANDIDATE_STATUS_LABELS",
    "CATEGORY_LABELS",
    "ENTRY_TYPE_LABELS",
    "KIND_LABELS",
    "STATUS_LABELS",
]
