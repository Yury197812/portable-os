"""L15: Adaptive recommender v11.

Trained on telemetry_v1.json (per-file × per-codec bits/byte and encode_ms).
Predicts the best codec for a new input based on file extension + size +
entropy heuristic.

Algorithm:
  1. For each training file, compute features (ext, size_log, has_repeats,
     ascii_ratio).
  2. For each (file, codec), have a (ratio, encode_ms) pair.
  3. Use a simple "nearest neighbors by extension+size" classifier:
     - For each query file: find K nearest training files by (ext, size)
     - Score each codec by sum of (1/distance) * (gain over median)
  4. Recommend the codec with highest weighted score.

Output: v11 JSON recommender rules compatible with the existing
investigate_ssp5_recommender_v9b.py format.

Why simple? L14 telemetry has only ~46 files. Heavier models (neural net)
would over-fit. k-NN with class-balanced weights is what v9b uses; v11
extends it with telemetry-driven features.
"""
from __future__ import annotations
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

# Telemetry lives in the parent project's benchmark directory (large
# artifact, kept outside the package). Rules JSON is written next to
# this module so bha_recommender_v11 can find it relatively.
#
# T2 retraining: telemetry_v2.json adds the BHA_VS_BROTLI crossover
# fixtures so v11 routing can correctly learn that brotli dominates
# on small web files. Pass --telemetry=v1 to use the legacy corpus.
_HERE = Path(__file__).parent
_PROJECT = _HERE.parent
DEFAULT_TELEMETRY = _PROJECT / 'benchmark' / 'codec-benchmark' / 'telemetry_v2.json'
LEGACY_TELEMETRY = _PROJECT / 'benchmark' / 'codec-benchmark' / 'telemetry_v1.json'
TELEMETRY = DEFAULT_TELEMETRY
OUT = _HERE / 'rules.json'


def features_of(name: str, size: int):
    """Extract features from filename and size. Cheap sniff."""
    ext = Path(name).suffix.lower().lstrip('.') or 'none'
    # Size buckets: log-2 base
    if size < 8_000:
        size_bucket = 'tiny'
    elif size < 80_000:
        size_bucket = 'small'
    elif size < 400_000:
        size_bucket = 'medium'
    elif size < 2_000_000:
        size_bucket = 'large'
    else:
        size_bucket = 'xlarge'
    return {'ext': ext, 'size_bucket': size_bucket, 'size_log': round(math.log2(max(size, 1)), 1)}


def load_telemetry():
    """Load telemetry_v1.json into list of (file_features, codec, ratio, ms)."""
    data = json.loads(TELEMETRY.read_text())
    training = []
    for row in data['rows']:
        feats = features_of(row['file'], row['input_size'])
        for c in row['codecs']:
            if 'error' in c:
                continue
            training.append({
                'file': row['file'],
                'features': feats,
                'codec': c['codec'],
                'ratio': c['ratio'],
                'bits_per_byte': c['bits_per_byte'],
                'encode_ms': c['encode_p50_ms'],
            })
    return training


def score_codec(training, query_feats, k=5):
    """For each codec, compute sum of (1/(d+0.5)) * (ratio / max_ratio - 1)
    across K nearest training points by (ext + size_log).

    Returns dict: codec -> total score.
    """
    if not training:
        return {}
    # Distance function: 0 if same ext, large if different
    def dist(t, q):
        if t['features']['ext'] != q['ext']:
            return 10.0  # heavy penalty for different ext
        return abs(t['features']['size_log'] - q['size_log'])

    # Group training by codec to compute per-codec median ratio (for gain calc)
    by_codec = defaultdict(list)
    for t in training:
        by_codec[t['codec']].append(t['ratio'])
    medians = {c: statistics.median(rs) for c, rs in by_codec.items()}
    # Max median = best typical codec
    max_med = max(medians.values()) if medians else 1.0

    # Sort training by distance to query
    q_ext = query_feats['ext']
    q_log = query_feats['size_log']
    candidates = [(dist(t, query_feats), t) for t in training if t['features']['ext'] == q_ext]
    candidates.sort(key=lambda x: x[0])
    candidates = candidates[:k * 6]  # take more than k since we group by codec

    # Aggregate per codec
    scores = defaultdict(float)
    counts = defaultdict(int)
    for d, t in candidates:
        # Score = (gain over max_med) / (d + 0.5) -- gain is positive when better
        gain = (t['ratio'] - max_med) / max(max_med, 0.01)
        weight = 1.0 / (d + 0.5)
        scores[t['codec']] += gain * weight
        counts[t['codec']] += 1

    # Add BHA-dominant boost: in catalog, BHA codecs are preferred when ratio is comparable
    BHA_DOMINANT = {
        'lzma9_extreme', 'lzma6', 'brotli_11', 'brotli_6',
        'zstd_22', 'zstd_3', 'bz2_9',
    }
    final = {}
    for c, sc in scores.items():
        # Penalize slow codecs slightly (encode_ms > 100ms is slow)
        ms_penalty = 0.0
        # Not easy without query info; skip
        # Apply BHA-dominant bonus
        bonus = 0.05 if c in BHA_DOMINANT else 0.0
        final[c] = sc + bonus

    return final


def evaluate(training):
    """LOO evaluation: for each training point, hide it, predict, compare."""
    correct_top1 = 0
    correct_top3 = 0
    n = 0
    by_ext = defaultdict(lambda: [0, 0])  # [correct, total]
    for i, hold_out in enumerate(training):
        # Find best codec for this file: smallest bits_per_byte
        # (we want to predict which codec minimizes output_size)
        train_subset = training[:i] + training[i+1:]
        # Get all codecs for the hold-out file
        all_for_file = [t for t in training if t['file'] == hold_out['file']]
        if not all_for_file:
            continue
        actual_best = min(all_for_file, key=lambda t: t['bits_per_byte'])['codec']

        # Predict
        scores = score_codec(train_subset, hold_out['features'])
        if not scores:
            continue
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        predicted = ranked[0][0]
        top3 = {c for c, _ in ranked[:3]}

        n += 1
        ext = hold_out['features']['ext']
        if predicted == actual_best:
            correct_top1 += 1
            by_ext[ext][0] += 1
        if actual_best in top3:
            correct_top3 += 1
        by_ext[ext][1] += 1

    return {
        'top1_pct': round(100 * correct_top1 / n, 1) if n else 0,
        'top3_pct': round(100 * correct_top3 / n, 1) if n else 0,
        'n': n,
        'by_ext': {k: round(100 * v[0] / v[1], 1) if v[1] else 0
                   for k, v in sorted(by_ext.items()) if v[1] >= 1},
    }


def main():
    training = load_telemetry()
    print(f'training points: {len(training)}')
    # Aggregate: per codec, how often it's best
    by_codec = defaultdict(int)
    by_file = defaultdict(list)
    for t in training:
        by_file[t['file']].append(t)
    best_per_file = {f: min(rs, key=lambda t: t['bits_per_byte'])['codec']
                     for f, rs in by_file.items()}
    for c in best_per_file.values():
        by_codec[c] += 1
    print(f'\nBest codec per file (from telemetry):')
    for c, n in sorted(by_codec.items(), key=lambda x: -x[1]):
        print(f'  {c:20s}  {n} files')

    print('\n--- LOO evaluation ---')
    metrics = evaluate(training)
    print(f'top-1: {metrics["top1_pct"]}%   top-3: {metrics["top3_pct"]}%   on {metrics["n"]} files')
    print('per ext:')
    for ext, pct in metrics['by_ext'].items():
        print(f'  .{ext:10s}  {pct}%')

    # Save rules: per (ext, size_bucket), top codec
    rules = defaultdict(lambda: defaultdict(float))
    for t in training:
        ext = t['features']['ext']
        size_b = t['features']['size_bucket']
        rules[ext][t['codec']] += t['ratio'] - 1.0  # gain over 1.0
        rules[ext]['_count'] = rules[ext].get('_count', 0) + 1

    out = {
        'version': 'v11',
        'method': 'k-NN-by-(ext,size_log), weighted by gain over max median',
        'training_source': str(TELEMETRY),
        'loo_metrics': metrics,
        'best_per_file': best_per_file,
        'codec_distribution': dict(by_codec),
        'rules_by_ext': {k: dict(v) for k, v in rules.items()},
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f'\nrecommender rules saved: {OUT}')


if __name__ == '__main__':
    main()