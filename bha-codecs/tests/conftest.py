"""pytest configuration for bha_core tests.

Adds custom markers and sets up BHA runtime availability detection.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Detect BHA runtime availability
# ---------------------------------------------------------------------------
# Tests that require the BHA runtime (bha_parallel, bha_compress) are
# automatically skipped if black_hole_archiver cannot be imported.
BHA_RUNTIME_AVAILABLE = False
try:
    import black_hole_archiver  # noqa: F401
    BHA_RUNTIME_AVAILABLE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------
def pytest_configure(config):
    """Register custom markers so --strict-markers works."""
    config.addinivalue_line(
        "markers",
        "requires_bha: Tests that need the BHA runtime at "
        "D:\\PROJECT UNIVERSE\\01Compression\\BHA (auto-skipped otherwise)",
    )
    config.addinivalue_line(
        "markers",
        "slow: Tests that take >1 second to run",
    )
    config.addinivalue_line(
        "markers",
        "integration: End-to-end integration tests",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests marked requires_bha when BHA runtime missing."""
    if BHA_RUNTIME_AVAILABLE:
        return
    skip_marker = pytest.mark.skip(reason="BHA runtime not on PYTHONPATH")
    for item in items:
        if "requires_bha" in item.keywords:
            item.add_marker(skip_marker)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def small_csv() -> bytes:
    """Sample CSV with int columns — used by bha_delta / v11 tests."""
    return (
        b"idx,value,score\n"
        + b"".join(f"{i},{i*2},{i*3}\n".encode() for i in range(100))
    )


@pytest.fixture
def quadratic_series() -> list[int]:
    """i*i — best case for delta-of-delta encoding."""
    return [i * i for i in range(1000)]


@pytest.fixture
def linear_series() -> list[int]:
    """Linear with constant step — also good for delta-of-delta."""
    return [100 + 7 * i for i in range(1000)]


@pytest.fixture
def random_walk() -> list[int]:
    """Random walk — best for plain delta (small deltas but no dod)."""
    import random
    rnd = random.Random(42)
    return [0] + [rnd.randint(-3, 3) for _ in range(999)]


@pytest.fixture
def repeated_data() -> bytes:
    """Data with known repeated substrings — for pp_dedup_substring test."""
    return b"hello world " * 100


@pytest.fixture
def x86_like_data() -> bytes:
    """Data with E8/E9 patterns — for pp_bcj_x86 test."""
    # Mix of E8/E9 calls and zeros — typical for an x86 binary header
    chunks = [
        bytes([0xE8, 0x10, 0x00, 0x00, 0x00, 0xE9, 0x20, 0x00, 0x00, 0x00]),
        bytes([0x90] * 20),  # NOPs
        bytes([0xE8, 0x30, 0x00, 0x00, 0x00, 0xE9, 0x40, 0x00, 0x00, 0x00]),
    ]
    return b"".join(chunks) * 50