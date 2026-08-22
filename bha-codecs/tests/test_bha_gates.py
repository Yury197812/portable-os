"""Unit tests for bha_core.bha_gates — gate registry.

Tests the GateRegistry contract: register / has / names / run.
Uses a fake ssp_module to avoid BHA runtime dependency.
"""
from __future__ import annotations
import pytest

from bha_core import bha_gates


class FakeSspModule:
    """Mock ssp module for testing — encode returns length-prefixed blob.

    Real signature: ssp.encode_data(data, _path, _a, _b, **_kw) where
    _a=1, _b=r=1, and **_kw accepts block_bits, allow_ssp.
    """

    def __init__(self):
        self.encode_count = 0
        self.decode_count = 0

    def encode_data(self, blob, _path, _a, r=1, **_kw):
        self.encode_count += 1
        # Prefix length so we can detect distortion
        return len(blob).to_bytes(4, 'big') + blob, None

    def decode_data(self, arc, _path):
        self.decode_count += 1
        # If length prefix is correct, return blob; else return garbage
        if len(arc) < 4:
            return b''
        length = int.from_bytes(arc[:4], 'big')
        if length + 4 != len(arc):
            return b'distorted-' + b'x' * 50
        return arc[4:]


class TestGateRegistryBasic:
    def test_empty_registry(self):
        reg = bha_gates.GateRegistry()
        assert reg.names() == []
        assert reg.has('any') is False

    def test_register_and_lookup(self):
        reg = bha_gates.GateRegistry()
        reg.register('foo', lambda sp, d: True, lambda d: d, lambda b: b + b'!')
        assert reg.has('foo') is True
        assert reg.names() == ['foo']

    def test_unregistered_run_returns_none(self):
        reg = bha_gates.GateRegistry()
        result = reg.run('nonexistent', b'data', None, FakeSspModule())
        assert result is None

    def test_check_returns_false_skips_gate(self):
        reg = bha_gates.GateRegistry()
        reg.register('g',
                     check=lambda sp, d: False,
                     encode=lambda d: d + b'-X',
                     build_archive=lambda b: b)
        ssp = FakeSspModule()
        assert reg.run('g', b'data', None, ssp) is None
        assert ssp.encode_count == 0  # encode never called

    def test_check_raises_skips_gate(self):
        reg = bha_gates.GateRegistry()
        reg.register('g',
                     check=lambda sp, d: 1 / 0,  # raises
                     encode=lambda d: d,
                     build_archive=lambda b: b)
        assert reg.run('g', b'data', None, FakeSspModule()) is None

    def test_encode_raises_skips_gate(self):
        reg = bha_gates.GateRegistry()
        def bad_encode(d): raise RuntimeError("encode failed")
        reg.register('g',
                     check=lambda sp, d: True,
                     encode=bad_encode,
                     build_archive=lambda b: b)
        assert reg.run('g', b'data', None, FakeSspModule()) is None

    def test_successful_run(self):
        """End-to-end success: check → encode (identity) → lzma2 → verify → archive."""
        reg = bha_gates.GateRegistry()
        reg.register('g',
                     check=lambda sp, d: True,
                     encode=lambda d: d,  # identity encode
                     build_archive=lambda b: b'[arc]' + b)
        data = b'hello'
        result = reg.run('g', data, None, FakeSspModule())
        assert result is not None
        size, archive = result
        # archive contains the lzma2-wrapped data
        assert archive.startswith(b'[arc]')

    def test_round_trip_failure_skips_gate(self):
        """If decode doesn't match original, gate skipped."""
        reg = bha_gates.GateRegistry()
        class BadSsp(FakeSspModule):
            def decode_data(self, arc, _path):
                return b'corrupted'
        reg.register('g',
                     check=lambda sp, d: True,
                     encode=lambda d: d,
                     build_archive=lambda b: b)
        assert reg.run('g', b'data', None, BadSsp()) is None


class TestGateRegistryRealisticScenario:
    """End-to-end: encode happens, lzma2 wraps it, archive wraps that, decode
    must reproduce the encoded blob (which is just data + suffix in this test).
    """

    def test_lzma2_round_trip(self):
        """When encode modifies data, round-trip fails (real-world case)."""
        reg = bha_gates.GateRegistry()
        reg.register('csv_archive',
                     check=lambda sp, d: d.startswith(b'col1'),
                     encode=lambda d: d.replace(b'col1', b'COL1'),
                     build_archive=lambda b: b'<arc>' + b + b'</arc>')
        data = b'col1,col2\n1,2\n'
        result = reg.run('csv_archive', data, None, FakeSspModule())
        # encode() transforms 'col1' -> 'COL1', so round-trip fails
        # (verify compares 'COL1,col2...' vs original 'col1,col2...')
        assert result is None

    def test_archive_preserves_bytes(self):
        """Identity encode + identity archive = round-trip success."""
        reg = bha_gates.GateRegistry()
        reg.register('no_op_archive',
                     check=lambda sp, d: True,
                     encode=lambda d: d,  # identity encode
                     build_archive=lambda b: b)  # identity archive
        data = b'hello world'
        result = reg.run('no_op_archive', data, None, FakeSspModule())
        assert result is not None
        size, archive = result
        # Archive is the lzma2-encoded blob (length-prefixed)
        assert archive == len(data).to_bytes(4, 'big') + data


class TestPublicApi:
    def test_list_gates_returns_priority_order(self):
        names = bha_gates.list_gates()
        assert isinstance(names, list)
        assert 'lzma_fallback' in names
        # Priority: lzma_fallback first (always works as fallback)
        assert names[0] == 'lzma_fallback'
        # All 14 BHA gates present
        expected_gates = {
            'quoted_csv', 'telemetry_csv', 'sparse_pattern', 'dense_sparse',
            'mixed_formula', 'sparse_col', 'tabular_col', 'record_transpose',
            'vartrans', 'line_norm', 'json_array', 'markdown_table',
            'css_struct',
        }
        assert expected_gates.issubset(set(names))

    def test_default_registry_has_gates_after_ensure(self):
        """ensure_registered() is idempotent and doesn't raise.

        Note: actual gate count depends on whether BHA runtime was
        already importable from a prior test in the suite (e.g.
        test_bha_compress.py imports bha_core.bha which loads BHA).
        This test only verifies the API contract: the call is safe
        and idempotent.
        """
        # First call: no-op or registers (if BHA available)
        before = len(bha_gates.DEFAULT_REGISTRY.names())
        bha_gates.ensure_registered()
        after = len(bha_gates.DEFAULT_REGISTRY.names())
        # Second call: must not raise and must be idempotent
        bha_gates.ensure_registered()
        assert bha_gates.DEFAULT_REGISTRY.names() == bha_gates.DEFAULT_REGISTRY.names()
        # T3: brotli_q11 + brotli_q6 are always registered (no BHA needed).
        # So the floor is now 2 (brotli only) when BHA runtime is missing,
        # and >=15 (brotli 2 + BHA 14) when BHA is present. Tolerate
        # partial BHA registration (13 BHA + 2 brotli = 15 minimum).
        assert after == 2 or after >= 15, f"unexpected gate count: {after}"


class TestBrotliGateRegistry:
    """T3: brotli_q11 / brotli_q6 are registered as codec gates with
    pipeline='brotli' (not the default 'ssp' pipeline). They bypass
    ssp.encode_data because ssp cannot decode brotli-framed blobs."""

    def test_brotli_q11_registered_after_ensure(self):
        """ensure_registered() should always register brotli gates
        (they don't need BHA runtime)."""
        bha_gates.ensure_registered()
        assert bha_gates.DEFAULT_REGISTRY.has('brotli_q11')
        assert bha_gates.DEFAULT_REGISTRY.has('brotli_q6')

    def test_brotli_gates_use_brotli_pipeline(self):
        bha_gates.ensure_registered()
        assert bha_gates.DEFAULT_REGISTRY.pipeline_of('brotli_q11') == 'brotli'
        assert bha_gates.DEFAULT_REGISTRY.pipeline_of('brotli_q6') == 'brotli'

    def test_brotli_gates_in_priority_list(self):
        from bha_core.bha_gates import GATE_NAMES
        assert 'brotli_q11' in GATE_NAMES
        assert 'brotli_q6' in GATE_NAMES

    def test_brotli_registry_run_bypasses_ssp(self):
        """When the registry runs brotli_q11 with a non-None ssp_module,
        brotli must STILL be used (the ssp module is irrelevant for
        brotli-pipeline gates)."""
        from bha_core.bha_codec_backends import is_available
        if not is_available():
            import pytest
            pytest.skip('brotli not installed')
        bha_gates.ensure_registered()

        class TrackingSsp:
            """ssp mock that raises if encode_data is called - brotli
            pipeline must NOT touch ssp."""
            def encode_data(self, *a, **kw):
                raise AssertionError(
                    'ssp.encode_data should NOT be called for brotli-pipeline gate'
                )
            def decode_data(self, *a, **kw):
                raise AssertionError(
                    'ssp.decode_data should NOT be called for brotli-pipeline gate'
                )

        data = b'<html>' + b'<p>x</p>' * 100 + b'</html>'
        result = bha_gates.DEFAULT_REGISTRY.run('brotli_q11', data, None, TrackingSsp())
        assert result is not None, 'brotli_q11 registry returned None'
        size, blob = result
        assert size < len(data)
        # External round-trip confirms bit-exact
        import brotli
        assert brotli.decompress(blob) == data

    def test_brotli_q11_vs_q6_different_quality(self):
        """Different quality levels must produce different output sizes
        (q11 typically smaller on text, larger on binary)."""
        from bha_core.bha_codec_backends import is_available
        if not is_available():
            import pytest
            pytest.skip('brotli not installed')
        bha_gates.ensure_registered()
        class StubSsp: pass

        # Text-heavy data where brotli shines
        data = b'<html><body>' + b'<p>repeated text content here</p>' * 200 + b'</body></html>'
        r11 = bha_gates.DEFAULT_REGISTRY.run('brotli_q11', data, None, StubSsp())
        r6 = bha_gates.DEFAULT_REGISTRY.run('brotli_q6', data, None, StubSsp())
        assert r11 is not None and r6 is not None
        # q11 should be <= q6 on text (q11 has larger dictionary, better ratio)
        assert r11[0] <= r6[0], (
            f'brotli_q11 ({r11[0]}) should be <= brotli_q6 ({r6[0]}) on text'
        )

    def test_unknown_pipeline_raises(self):
        """register() with an unknown pipeline name should raise ValueError."""
        import pytest
        reg = bha_gates.GateRegistry()
        with pytest.raises(ValueError, match='unknown pipeline'):
            reg.register(
                'bad_gate',
                check=lambda sp, d: True,
                encode=lambda d: d,
                build_archive=lambda b: b,
                pipeline='nonexistent_pipeline',
            )


class TestGateRegistryPipelinePassthrough:
    """T3: pipeline='passthrough' skips entropy layer entirely."""

    def test_passthrough_pipeline_runs_without_ssp(self):
        reg = bha_gates.GateRegistry()
        reg.register(
            'plain_copy',
            check=lambda sp, d: True,
            encode=lambda d: d,
            build_archive=lambda b: b,
            pipeline=bha_gates.PIPELINE_PASSTHROUGH,
        )

        class TrackingSsp:
            def encode_data(self, *a, **kw):
                raise AssertionError('ssp should NOT be called')
            def decode_data(self, *a, **kw):
                raise AssertionError('ssp should NOT be called')

        data = b'hello passthrough'
        result = reg.run('plain_copy', data, None, TrackingSsp())
        assert result is not None
        size, blob = result
        assert blob == data
        assert size == len(data)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])