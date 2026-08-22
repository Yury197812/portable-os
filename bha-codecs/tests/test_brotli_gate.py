"""Unit tests for bha_core.bha_codec_backends + brotli gate integration.

Tests:
  - brotli backend availability + round-trip
  - bha_parallel.worker_gate dispatches brotli_q11 / brotli_q6 correctly
  - 1000-iteration determinism (size_unique == 1)
  - v11 recommender routes small web files to brotli_q11 first

These tests do NOT require the BHA runtime - they use a stub ssp module.
"""
from __future__ import annotations
import os
import pytest

# Locate benchmark fixtures used in BHA_VS_BROTLI.md.
FIXTURE_ROOT = r'D:\4\bha-codecs\benchmark'


def _resolve_fixture(*candidates: str) -> str | None:
    """Return the first existing path from candidates, or None."""
    for c in candidates:
        p = os.path.join(FIXTURE_ROOT, c)
        if os.path.exists(p):
            return p
    return None


# Web/structured-text fixtures at <=80KB (the Brotli crossover window).
SMALL_FIXTURES = [
    (_resolve_fixture('bro_html+json-50k.html',
                      'bro_html+json-80k.html'),
     'html', 1 << 16),
    (_resolve_fixture('bro_json-80k.json'),
     'json', 1 << 16),
    (_resolve_fixture('bro_markdown-50k.md',
                      'bro_markdown-80k.md'),
     'md', 1 << 16),
    (_resolve_fixture('crossover_html_100kb.html'),
     'html', 1 << 17),  # borderline: just above 64KB threshold
]


class TestBrotliBackendAvailability:
    def test_brotli_is_available(self):
        """brotli 1.2.0 should be installed in the env (verified earlier)."""
        from bha_core.bha_codec_backends import is_available, list_gate_names
        assert is_available(), 'brotli Python binding missing'
        names = list_gate_names()
        assert 'brotli_q11' in names
        assert 'brotli_q6' in names

    def test_quality_for_returns_int(self):
        from bha_core.bha_codec_backends import quality_for
        assert quality_for('brotli_q11') == 11
        assert quality_for('brotli_q6') == 6
        assert quality_for('unknown_gate') is None


class TestBrotliBackendRoundTrip:
    def test_round_trip_small_html(self):
        from bha_core.bha_codec_backends import brotli_compress, brotli_decompress
        data = b'<html><body>Hello, brotli!</body></html>' * 10
        c = brotli_compress(data, quality=11)
        d = brotli_decompress(c)
        assert d == data
        # Ratio check: HTML should compress well
        assert len(c) < len(data) // 3

    def test_round_trip_random_bytes(self):
        """Random bytes - brotli should still produce a valid (maybe larger) blob."""
        from bha_core.bha_codec_backends import brotli_compress, brotli_decompress
        import os
        data = os.urandom(2000)
        c = brotli_compress(data, quality=11)
        d = brotli_decompress(c)
        assert d == data

    def test_round_trip_empty(self):
        from bha_core.bha_codec_backends import brotli_compress, brotli_decompress
        c = brotli_compress(b'', quality=11)
        d = brotli_decompress(c)
        assert d == b''


class TestBrotliDeterminism:
    """Per BHA_SAFE_SKILLS SKILL 5: 1000 iterations, all sizes must match."""

    @pytest.mark.parametrize('quality', [6, 11])
    def test_determinism_1000_iterations(self, quality):
        from bha_core.bha_codec_backends import brotli_compress
        data = b'<html><body>' + b'<p>para</p>' * 200 + b'</body></html>'
        sizes = set()
        for _ in range(1000):
            c = brotli_compress(data, quality=quality)
            sizes.add(len(c))
        assert len(sizes) == 1, f'brotli non-deterministic at q={quality}: {sizes}'


class TestWorkerGateBrotli:
    """Test that bha_parallel.worker_gate dispatches brotli correctly."""

    def _stub_ssp(self):
        class StubSsp:
            pass
        return StubSsp()

    def test_brotli_q11_returns_compressed_blob(self):
        import bha_core.bha_parallel as bp
        bp._WORKER_SSP = self._stub_ssp()
        data = b'<html>' + b'<p>x</p>' * 50 + b'</html>'
        result = bp.worker_gate(('brotli_q11', data, None))
        assert result is not None, 'brotli_q11 gate returned None'
        name, size, arc = result
        assert name == 'brotli_q11'
        assert size < len(data), f'brotli q11 should compress: {size} vs {len(data)}'

    def test_brotli_q6_returns_compressed_blob(self):
        import bha_core.bha_parallel as bp
        bp._WORKER_SSP = self._stub_ssp()
        data = b'<html>' + b'<p>x</p>' * 50 + b'</html>'
        result = bp.worker_gate(('brotli_q6', data, None))
        assert result is not None
        name, size, _ = result
        assert name == 'brotli_q6'
        assert size < len(data)

    def test_brotli_q11_round_trip_via_external_decompress(self):
        """Independent brotli decode must reproduce original bytes."""
        import bha_core.bha_parallel as bp
        import brotli  # external sanity check
        bp._WORKER_SSP = self._stub_ssp()
        data = b'<!DOCTYPE html>\n<html><body>Real content here</body></html>' * 20
        result = bp.worker_gate(('brotli_q11', data, None))
        assert result is not None
        _, _, arc = result
        assert brotli.decompress(arc) == data

    def test_unknown_gate_returns_none(self):
        import bha_core.bha_parallel as bp
        bp._WORKER_SSP = self._stub_ssp()
        result = bp.worker_gate(('not_a_gate_xyz', b'data', None))
        assert result is None


class TestCodecAliasing:
    """T2: telemetry codec names (brotli_11/brotli_6 from bench_codecs.py)
    are aliased to gate names (brotli_q11/brotli_q6 in worker_gate). They
    denote the same operation; the recommender must use gate names."""

    def test_alias_gate_basic(self):
        from bha_core.bha_recommender_v11 import _alias_gate
        assert _alias_gate('brotli_11') == 'brotli_q11'
        assert _alias_gate('brotli_6')  == 'brotli_q6'
        # Pass-through for non-brotli codecs
        assert _alias_gate('lzma6') == 'lzma6'
        assert _alias_gate('zstd_22') == 'zstd_22'
        assert _alias_gate('') == ''
        assert _alias_gate('unknown') == 'unknown'

    def test_recommend_does_not_contain_telemetry_names(self):
        """After T2 aliasing, recommend() should NEVER return brotli_11
        or brotli_6 (those are telemetry names, not gate names)."""
        from bha_core.bha_recommender_v11 import recommend
        # Sweep sizes and web extensions to make sure aliasing is applied
        # even when the underlying rules.json still has brotli_11 as
        # the top codec.
        for name in ['foo.html', 'data.json', 'a.md', 'config.ini', 'x.txt']:
            for size in [1_000, 50_000, 100_000, 200_000]:
                rec = recommend(name, size, k=10)
                assert 'brotli_11' not in rec, (
                    f'recommend({name}, {size}) returned telemetry name '
                    f'brotli_11 in {rec}'
                )
                assert 'brotli_6' not in rec, (
                    f'recommend({name}, {size}) returned telemetry name '
                    f'brotli_6 in {rec}'
                )

    def test_top_codec_is_aliased(self):
        """_top_codec_for returns gate names (brotli_q11/q6), not telemetry."""
        from bha_core.bha_recommender_v11 import _top_codec_for
        # bro_*_md was best with brotli in telemetry_v2; should be aliased
        codec, src = _top_codec_for('bro_markdown-50k.md', 96_005)
        assert codec in ('brotli_q11', 'brotli_q6'), (
            f'expected brotli_q* in top_codec, got {codec}'
        )


class TestBrotliSmallMaxT2:
    """T2 raises BROTLI_SMALL_MAX from 64 KiB to 256 KiB based on telemetry_v2.
    Verify the new threshold is honoured."""

    def test_brotli_small_max_is_256kib(self):
        from bha_core.bha_recommender_v11 import BROTLI_SMALL_MAX
        assert BROTLI_SMALL_MAX == 1 << 18, (
            f'BROTLI_SMALL_MAX changed unexpectedly: {BROTLI_SMALL_MAX}'
        )

    @pytest.mark.parametrize('name,size', [
        ('page.html', 200_000),       # 200 KB HTML — within new threshold
        ('data.json', 250_000),      # 250 KB JSON — within new threshold
        ('a.md',      100_000),      # 100 KB MD — within new threshold
        ('rules.yaml', 200_000),     # 200 KB YAML
        ('x.xml',     150_000),      # 150 KB XML
    ])
    def test_routes_to_brotli_up_to_256kib(self, name, size):
        from bha_core.bha_recommender_v11 import recommend, BROTLI_SMALL_MAX
        assert size <= BROTLI_SMALL_MAX
        gates = recommend(name, size, k=5)
        assert gates[0] == 'brotli_q11'


class TestRecommenderBrotliRouting:
    """v11 must route small web files to brotli_q11 first."""

    @pytest.mark.parametrize('name,size', [
        ('foo.html', 5_000),
        ('bar.html', 60_000),
        ('data.json', 5_000),
        ('page.htm', 30_000),
        ('a.md', 50_000),
        ('config.ini', 1_000),
        ('rules.yaml', 30_000),
        ('x.xml', 8_000),
        ('x.txt', 500),
        ('a.svg', 20_000),
        ('main.js', 30_000),
    ])
    def test_small_web_ext_routes_to_brotli(self, name, size):
        from bha_core.bha_recommender_v11 import recommend, BROTLI_SMALL_MAX
        assert size <= BROTLI_SMALL_MAX, 'fixture should be in small band'
        gates = recommend(name, size, k=5)
        assert gates[0] == 'brotli_q11', (
            f'expected brotli_q11 first for {name}@size={size}, got {gates}'
        )

    @pytest.mark.parametrize('name,size', [
        ('big.html', 400_000),
        ('huge.html', 500_000),
        ('big.json', 500_000),
        ('large.md', 300_000),
    ])
    def test_large_web_ext_does_not_route_to_brotli_first(self, name, size):
        from bha_core.bha_recommender_v11 import recommend, BROTLI_SMALL_MAX
        assert size > BROTLI_SMALL_MAX, 'fixture should be in large band'
        gates = recommend(name, size, k=5)
        assert gates[0] != 'brotli_q11', (
            f'brotli should NOT win above threshold for {name}@size={size}, got {gates}'
        )

    @pytest.mark.parametrize('name,size', [
        ('data.csv', 1_000),
        ('big.csv', 500_000),
        ('data.bin', 1_000),
        ('log.log', 500),       # .log NOT in BROTLI_PREFERRED_EXTS
        ('data.dat', 5_000),    # unknown / generic binary
    ])
    def test_non_web_ext_does_not_route_to_brotli(self, name, size):
        """csv/bin/log stay on BHA path (not in BROTLI_PREFERRED_EXTS)."""
        from bha_core.bha_recommender_v11 import recommend
        gates = recommend(name, size, k=5)
        assert gates[0] != 'brotli_q11', (
            f'brotli should NOT route {name}@size={size}, got {gates}'
        )


class TestFixtureRoundTrip:
    """End-to-end: read fixture, compress via worker_gate, decompress,
    assert byte-exact match. Uses real BHA_VS_BROTLI corpus."""

    @pytest.mark.parametrize('quality', ['brotli_q11', 'brotli_q6'])
    def test_fixture_round_trip(self, quality):
        import bha_core.bha_parallel as bp
        bp._WORKER_SSP = type('S', (), {})()  # stub
        fixture_path = SMALL_FIXTURES[0][0]  # first available fixture
        if fixture_path is None:
            pytest.skip('no fixture available')
        data = open(fixture_path, 'rb').read()
        # Skip if fixture > 100KB (above brotli crossover)
        if len(data) > 100_000:
            pytest.skip(f'fixture {fixture_path} too large for brotli domain')
        result = bp.worker_gate((quality, data, fixture_path))
        assert result is not None, f'{quality} failed on {fixture_path}'
        _, _, arc = result
        import brotli
        assert brotli.decompress(arc) == data, f'round-trip failed for {fixture_path}'
        # brotli must beat LZMA on these inputs (the whole point of T1)
        import lzma
        lzma_size = len(lzma.compress(data, format=lzma.FORMAT_XZ, preset=6))
        # Allow 5% margin for edge cases; brotli should win comfortably
        assert len(arc) <= lzma_size * 1.05, (
            f'{quality} did not beat LZMA on {fixture_path}: '
            f'brotli={len(arc)} vs lzma={lzma_size}'
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])