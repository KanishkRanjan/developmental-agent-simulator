"""Action codes entered from shuffled responses before opening the key."""

import json
from pathlib import Path

codes = (
    'low high high mixed high low high high low low high low '
    'mixed high high high low low high high low low high high '
    'low high low low high high high low high high high high '
    'high high mixed low low low low high high low low high'
).split()
assert len(codes) == 48

base = Path(__file__).parent
blind = json.loads((base / 'prompt-style-results.blind.json').read_text())
key = json.loads((base / 'prompt-style-results.key.json').read_text())
raw = [json.loads(line) for line in (base / 'prompt-style-results.jsonl').read_text().splitlines()]
scored = []
for item in blind:
    blind_id = item['blind_id']
    label = codes[int(blind_id[1:])]
    row = raw[key[blind_id]]
    target_high = row['profile'][row['target_facet']] == 85
    scored.append({
        'domain': row['domain'], 'direction': row['direction'],
        'method': row['method'], 'target_facet': row['target_facet'],
        'scenario': row['scenario'], 'blind_id': blind_id, 'label': label,
        'target_high': target_high,
        'concordant': (label == 'high' if target_high else label == 'low'),
    })
(base / 'prompt-style-scored.json').write_text(json.dumps(scored, indent=2) + '\n')
for method in ('original', 'sectioned'):
    subset = [r for r in scored if r['method'] == method]
    print(method, 'concordant', sum(r['concordant'] for r in subset), '/', len(subset))
    pairs = 0
    for domain in 'ECO':
        for scenario in range(4):
            pair = [r for r in subset if r['domain'] == domain and r['scenario'] == scenario]
            assert len(pair) == 2
            pairs += all(r['concordant'] for r in pair)
    print(method, 'opposite-action pairs', pairs, '/ 12')
