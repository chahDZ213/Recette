"""Measured binary statistics (facts, never guesses): entropy, histograms."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np


def shannon_entropy(data: bytes) -> float:
    """Shannon entropy in bits/byte (0.0 = constant, 8.0 = uniform random)."""
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


@dataclass(frozen=True, slots=True)
class BlockEntropy:
    offset: int
    length: int
    entropy: float


def block_entropy(data: bytes, block_size: int = 4096) -> list[BlockEntropy]:
    """Entropy per fixed-size block — locates code vs. tables vs. erased flash."""
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    blocks: list[BlockEntropy] = []
    for offset in range(0, len(data), block_size):
        chunk = data[offset : offset + block_size]
        blocks.append(BlockEntropy(offset=offset, length=len(chunk), entropy=shannon_entropy(chunk)))
    return blocks


def byte_histogram(data: bytes) -> np.ndarray:
    """256-bin histogram of byte values."""
    return np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256)
