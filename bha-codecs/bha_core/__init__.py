"""bha_core — production-ready BHA codec pipeline.

This package contains the core components of the Black Hole Archiver
codec stack, extracted from the larger research project at D:\\4\\bha-codecs.

Layers implemented:
  L3 preprocessor — bha_delta (adaptive int encoder)
  L3 preprocessor — bha_v10_pp_safe (round-trip safe pp_bcj_x86, pp_dedup_substring)
  L9 parallel orchestrator — bha_parallel, bha_persistent_pool
  L8 recommender — recommender_v11 (L15 training), bha_recommender_v11 (API)
  L6 entropy — bench_codecs (multi-codec comparison)

Public API:
  from bha_core import bha_compress, bha_parallel_compress, bha_recommender_v11

The package is self-contained: all paths are resolved relative to this
file's directory. Tests in the parent project use core_check.py to verify
everything works.
"""
__version__ = '1.0'
__all__ = [
    'bha',
    'bha_delta',
    'bha_v10_pp_safe',
    'bha_gates',
    'bha_parallel',
    'bha_persistent_pool',
    'bha_recommender_v11',
    'recommender_v11',
    'bench_codecs',
]