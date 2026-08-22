"""bha_core_rs: Rust acceleration for bha_core hot paths.

Replaces Python loops in:
- bha_delta._adaptive_encode_int (37% of total codec time)
- bha_v10_pp_safe.pp_dedup_substring_safe (8% of total time)

This module is optional — bha_core falls back to pure Python if the
Rust extension fails to import (e.g. on unsupported platforms).
"""
from .bha_core_rs import (
    delta_encode_plain,
    delta_encode_dod,
    xor_encode_i32,
    xor_encode_i64,
    adaptive_encode_int,
    pp_dedup_substring_scan,
    choose_mode,
)

__version__ = "0.1.0"
__all__ = [
    "delta_encode_plain",
    "delta_encode_dod",
    "xor_encode_i32",
    "xor_encode_i64",
    "adaptive_encode_int",
    "pp_dedup_substring_scan",
    "choose_mode",
]