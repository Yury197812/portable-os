"""Generate test fixtures for the BHA vs brotli crossover benchmark.

Sizes to test: 100KB, 200KB, 400KB, 800KB, 1MB.
Two content types: HTML+inline-JSON (favors brotli) and JSON array
(favors BHA via structural codecs).

We already have:
  bro_html+json-50k.html  (3.4KB)
  bro_html+json-80k.html  (5.5KB)
  bro_json-50k.json       (9.5KB)
  bro_json-80k.json       (15KB)
  bro_specific_html_200k.html (200KB)
  bro_specific_html_500k.html (1.5MB)

Missing: 100KB / 400KB / 800KB / 1MB in both content types.
We generate them by repeating/expanding the existing fixtures.
"""
import os
import random

OUT = r'D:\\4\\bha-codecs\\benchmark'

def gen_html_inline_json(target_kb: int, seed: int) -> str:
    rnd = random.Random(seed)
    parts = ['<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>']
    parts.append('<div class="container">')
    while sum(len(p) for p in parts) < target_kb * 1024:
        i = rnd.randint(0, 100000)
        parts.append(
            f'<div class="item" data-id="{i:06d}">'
            f'<span class="user">user_{i:05d}</span>'
            f'<span class="email">user{i}@example.com</span>'
            f'<span class="role">{"admin" if i%3==0 else "editor" if i%3==1 else "viewer"}</span>'
            f'<span class="time">2026-08-2{i%9}T12:00:0{i%10}Z</span>'
            f'<span class="status">{"active" if i%2 else "inactive"}</span>'
            f'</div>\n'
        )
    parts.append('</div></body></html>')
    return ''.join(parts)


def gen_json_array(target_kb: int, seed: int) -> bytes:
    """Real-shape JSON array, like bro_json-50k.json but bigger."""
    import json
    rnd = random.Random(seed)
    obj = {'hits': {'hits': [], 'total': 0, 'page': 1, 'version': 'v1'}}
    n = 0
    while len(json.dumps(obj)) < target_kb * 1024:
        i = rnd.randint(0, 1000000)
        obj['hits']['hits'].append({
            'id': f'A{i:06d}',
            'type': ['publication', 'dataset', 'poster'][i % 3],
            'title': f'Исследование номер {i} в области науки ' + 'тест ' * rnd.randint(0, 3),
            'authors': [
                {'name': f'Author {i:05d}', 'affiliation': f'University {i % 50}'},
                {'name': f'Coauthor {i:05d}', 'affiliation': f'Institute {i % 30}'},
            ],
            'tags': [f'tag_{i%100}', f'field_{i%40}', f'year_{2020 + (i % 6)}'],
            'doi': f'10.5281/zenodo.{1000000 + i}',
            'files': [{'name': f'file_{i}.pdf', 'size': 100000 + i}],
        })
        n += 1
    obj['hits']['total'] = n
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


# Generate fixtures
SIZES_KB = [100, 200, 400, 800, 1024]
for kb in SIZES_KB:
    html = gen_html_inline_json(kb, seed=42)
    p_html = os.path.join(OUT, f'crossover_html_{kb}kb.html')
    with open(p_html, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'  wrote {p_html} ({len(html.encode("utf-8"))} B)')

for kb in SIZES_KB:
    data = gen_json_array(kb, seed=42)
    p_json = os.path.join(OUT, f'crossover_json_{kb}kb.json')
    with open(p_json, 'wb') as f:
        f.write(data)
    print(f'  wrote {p_json} ({len(data)} B)')

print('done')
