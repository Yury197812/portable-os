"""bha_gates: BHA codec gate registry.

Replaces the 242-line if/elif chain in bha_parallel.worker_gate with a
declarative registry. Each gate is a dict with three functions:

  check(src_path, data) -> bool          # gate eligibility
  encode(data) -> bytes                  # data -> preprocessed blob
  build_archive(blob) -> bytes          # blob -> BHA file archive

Plus auto-round-trip verification via ssp.decode_data(arc).

The pattern: every BHA gate does the same 4 steps
  (check → encode → lzma2 via ssp → archive → verify round-trip).
This module makes the pattern explicit and reduces 14 gates to
14 dict entries of 4-5 lines each.

Why this is better than the if/elif chain:
  1. Adding a new gate = one register() call, no need to touch
     the orchestrator
  2. Each gate's 3 functions are isolated, easier to test in isolation
  3. The 4-step pipeline is in one place (run), not duplicated 14×
  4. The registry IS the documentation: listing = inspecting

Public API:
  register(name, check, encode, build_archive) -> None
  run(name, data, src_path, ssp) -> (size, archive_bytes) | None
  has(name) -> bool
  names() -> list[str]
"""
from __future__ import annotations
from typing import Callable, Optional, Tuple

GateResult = Tuple[int, bytes]  # (output_size, archive_bytes)
CheckFn = Callable[[object, bytes], bool]
EncodeFn = Callable[[bytes], bytes]
ArchiveFn = Callable[[bytes], bytes]


class GateRegistry:
    """Registry of BHA codec gates keyed by name."""

    def __init__(self):
        self._gates: dict[str, dict] = {}

    def register(self, name: str, check: CheckFn, encode: EncodeFn,
                 build_archive: ArchiveFn) -> None:
        """Register a gate.

        Args:
            name: gate identifier (e.g. 'quoted_csv', 'pp_bcj_x86')
            check: (src_path, data) -> bool, returns True if gate applies
            encode: data -> blob (preprocessed bytes)
            build_archive: blob -> BHA file archive bytes

        The 4-step pipeline (encode → lzma2 → archive → verify) is
        applied uniformly by run() — no need for each gate to
        duplicate that logic.
        """
        self._gates[name] = {
            'check': check,
            'encode': encode,
            'build_archive': build_archive,
        }

    def has(self, name: str) -> bool:
        return name in self._gates

    def names(self) -> list[str]:
        return list(self._gates.keys())

    def run(self, name: str, data: bytes, src_path,
            ssp_module) -> Optional[GateResult]:
        """Execute a single gate. Returns (size, archive) or None.

        Skips the gate (returns None) if:
        - Gate not in registry
        - check() returns False
        - encode fails (exception)
        - LZMA2 encode/decode fails
        - round-trip check fails (decoded != original)
        - build_archive fails
        """
        if name not in self._gates:
            return None
        g = self._gates[name]

        # Step 1: gate-specific check
        try:
            if not g['check'](src_path, data):
                return None
        except Exception:
            return None

        # Step 2: encode data -> blob
        try:
            blob = g['encode'](data)
        except Exception:
            return None

        # Step 3: LZMA2 compress via ssp runtime
        try:
            arc, _ = ssp_module.encode_data(
                blob, None, 1, r=1, block_bits=32, allow_ssp=False
            )
            decoded = ssp_module.decode_data(arc, None)
        except Exception:
            return None

        # Step 4: round-trip verification
        if decoded != data:
            return None

        # Step 5: build final BHA file archive
        try:
            final_arc = g['build_archive'](arc)
            return (len(final_arc), final_arc)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Default BHA gate registry (14 BHA codec gates)
# ---------------------------------------------------------------------------
DEFAULT_REGISTRY = GateRegistry()


def _register_default_gates() -> None:
    """Populate DEFAULT_REGISTRY with all 14 BHA codec gates.

    Imports the BHA runtime at call-time (not module-load) so this
    module can be imported even when BHA runtime is missing.
    """
    from black_hole_archiver import (
        _build_runtime_lzma_archive, _build_file_lzma_fallback_archive,
        _quoted_csv_safety_risk, _quoted_csv_delimiter, _quoted_csv_gate,
        _encode_quoted_csv, _decode_quoted_csv, _build_file_quoted_csv_archive,
        _telemetry_csv_gate, _encode_telemetry_csv, _decode_telemetry_csv,
        _build_file_telemetry_csv_archive,
        _sparse_pattern_delimiter, _encode_sparse_pattern, _decode_sparse_pattern,
        _build_file_sparse_pattern_archive,
        _dense_sparse_delimiter, _encode_dense_sparse, _decode_dense_sparse,
        _build_file_dense_sparse_archive,
        _mixed_formula_gate, _encode_mixed_formula, _decode_mixed_formula,
        _build_file_mixed_formula_archive,
        _sparse_col_gate, _encode_sparse_col, _decode_sparse_col,
        _build_file_sparse_col_archive,
        _tabular_col_gate, _encode_tabular_col, _decode_tabular_col,
        _build_file_tabular_col_archive,
        _record_transpose_gate, _encode_record_transpose, _decode_record_transpose,
        _build_file_record_transpose_archive,
        _vartrans_gate, _encode_vartrans, _decode_vartrans, _build_file_vartrans_archive,
        _line_norm_gate, _encode_line_norm, _decode_line_norm,
        _build_file_line_norm_archive,
        _json_array_gate, _encode_json_array, _decode_json_array, _build_file_json_array_archive,
        _markdown_table_gate, _encode_markdown_table, _decode_markdown_table,
        _build_file_markdown_table_archive,
        _css_struct_gate, _encode_css_struct, _decode_css_struct,
        _build_file_css_struct_archive,
    )

    # 14 BHA codec gates, each: (check_fn, encode_fn, archive_fn)

    DEFAULT_REGISTRY.register(
        'quoted_csv',
        check=lambda sp, d: (not _quoted_csv_safety_risk(sp, d))
                            and _quoted_csv_delimiter(sp) is not None
                            and _quoted_csv_gate(sp, d),
        encode=_encode_quoted_csv,
        build_archive=_build_file_quoted_csv_archive,
    )

    DEFAULT_REGISTRY.register(
        'telemetry_csv',
        check=lambda sp, d: _telemetry_csv_gate(d),
        encode=_encode_telemetry_csv,
        build_archive=_build_file_telemetry_csv_archive,
    )

    DEFAULT_REGISTRY.register(
        'sparse_pattern',
        check=lambda sp, d: _sparse_pattern_delimiter(sp, d) is not None,
        encode=_encode_sparse_pattern,
        build_archive=_build_file_sparse_pattern_archive,
    )

    DEFAULT_REGISTRY.register(
        'dense_sparse',
        check=lambda sp, d: _dense_sparse_delimiter(sp, d) is not None,
        encode=_encode_dense_sparse,
        build_archive=_build_file_dense_sparse_archive,
    )

    DEFAULT_REGISTRY.register(
        'mixed_formula',
        check=lambda sp, d: _mixed_formula_gate(sp, d),
        encode=_encode_mixed_formula,
        build_archive=_build_file_mixed_formula_archive,
    )

    DEFAULT_REGISTRY.register(
        'sparse_col',
        check=lambda sp, d: _sparse_col_gate(d) is not None,
        encode=_encode_sparse_col,
        build_archive=_build_file_sparse_col_archive,
    )

    DEFAULT_REGISTRY.register(
        'tabular_col',
        check=lambda sp, d: _tabular_col_gate(d) is not None,
        encode=_encode_tabular_col,
        build_archive=_build_file_tabular_col_archive,
    )

    DEFAULT_REGISTRY.register(
        'record_transpose',
        check=lambda sp, d: _record_transpose_gate(d) is not None,
        encode=_encode_record_transpose,
        build_archive=_build_file_record_transpose_archive,
    )

    DEFAULT_REGISTRY.register(
        'vartrans',
        check=lambda sp, d: _vartrans_gate(d) is not None,
        encode=_encode_vartrans,
        build_archive=_build_file_vartrans_archive,
    )

    DEFAULT_REGISTRY.register(
        'line_norm',
        check=lambda sp, d: sp is not None and _line_norm_gate(sp, d),
        encode=_encode_line_norm,
        build_archive=_build_file_line_norm_archive,
    )

    DEFAULT_REGISTRY.register(
        'json_array',
        check=lambda sp, d: sp is not None and _json_array_gate(sp, d),
        encode=_encode_json_array,
        build_archive=_build_file_json_array_archive,
    )

    DEFAULT_REGISTRY.register(
        'markdown_table',
        check=lambda sp, d: sp is not None and _markdown_table_gate(sp, d),
        encode=_encode_markdown_table,
        build_archive=_build_file_markdown_table_archive,
    )

    DEFAULT_REGISTRY.register(
        'css_struct',
        check=lambda sp, d: sp is not None and _css_struct_gate(sp, d),
        encode=_encode_css_struct,
        build_archive=_build_file_css_struct_archive,
    )


# Priority order (most-likely-wins first) — used by bha_parallel
# orchestrator. Note: 'delta_pp' and 'structured' and v10 pp gates
# ('pp_dedup_substring', 'pp_bcj_x86', 'pp_zero_extend') are handled
# separately by the orchestrator because they have custom sidecar
# logic not captured by the simple 3-function gate interface.
GATE_NAMES = [
    'lzma_fallback',
    'quoted_csv', 'telemetry_csv', 'sparse_pattern', 'dense_sparse',
    'mixed_formula', 'sparse_col', 'tabular_col', 'record_transpose',
    'vartrans', 'line_norm', 'json_array', 'markdown_table', 'css_struct',
]


def list_gates() -> list[str]:
    """Return priority-ordered list of standard gate names."""
    return list(GATE_NAMES)


# ---------------------------------------------------------------------------
# Auto-register on import (lazy — BHA runtime must be available)
# ---------------------------------------------------------------------------
def ensure_registered() -> None:
    """Idempotent: register defaults if not already done."""
    if not DEFAULT_REGISTRY.names():
        try:
            _register_default_gates()
        except ImportError:
            pass  # BHA runtime not available; gates won't work


ensure_registered()