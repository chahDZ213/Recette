from __future__ import annotations

from calforge.analysis.diff import diff_bytes


def test_identical_files() -> None:
    data = bytes(range(256)) * 10
    result = diff_bytes(data, data)
    assert result.identical
    assert result.total_changed_bytes == 0
    assert result.regions == ()


def test_single_byte_change() -> None:
    a = bytes(1000)
    b = bytearray(a)
    b[500] = 0xFF
    result = diff_bytes(a, bytes(b))
    assert result.total_changed_bytes == 1
    assert len(result.regions) == 1
    region = result.regions[0]
    assert region.offset == 500
    assert region.length == 1


def test_nearby_changes_are_merged_without_inflating_count() -> None:
    a = bytes(1000)
    b = bytearray(a)
    b[100] = 1
    b[105] = 2  # 4 identical bytes between changes, <= merge_gap
    result = diff_bytes(a, bytes(b), merge_gap=8)
    assert len(result.regions) == 1
    assert result.regions[0].offset == 100
    assert result.regions[0].end == 106
    assert result.regions[0].changed_bytes == 2
    assert result.total_changed_bytes == 2


def test_distant_changes_stay_separate() -> None:
    a = bytes(1000)
    b = bytearray(a)
    b[10] = 1
    b[900] = 2
    result = diff_bytes(a, bytes(b), merge_gap=8)
    assert len(result.regions) == 2


def test_different_sizes_report_tail_region() -> None:
    a = bytes(100)
    b = bytes(100) + b"\xff" * 28
    result = diff_bytes(a, b)
    assert not result.identical
    tail = result.regions[-1]
    assert tail.offset == 100
    assert tail.length == 28
    assert result.total_changed_bytes == 28
