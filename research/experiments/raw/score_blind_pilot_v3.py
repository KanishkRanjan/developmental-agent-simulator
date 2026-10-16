"""Manual action codes entered from the shuffled V3 response list before opening the key."""

import json
from pathlib import Path

codes = dict(enumerate(
    'high low high low low low low low high high high mixed '
    'mixed high low low high high low high low high low low '
    'low low low mixed low high high low mixed high high low '
    'low low high high high high low high mixed low mixed low'.split()
))
assert len(codes) == 48

base = Path(__file__).parent
blind = json.loads((base / 'facet-pilot-v3-results.blind.json').read_text())
key = json.loads((base / 'facet-pilot-v3-results.key.json').read_text())
raw = [json.loads(line) for line in (base / 'facet-pilot-v3-results.jsonl').read_text().splitlines()]
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
(base / 'facet-pilot-v3-scored.json').write_text(json.dumps(scored, indent=2) + '\n')
for method in ('facets', 'domains'):
    for domain in 'ECO':
        subset = [r for r in scored if r['method'] == method and r['domain'] == domain]
        print(method, domain, sum(r['concordant'] for r in subset), '/', len(subset))
    pairs = 0
    for domain in 'ECO':
        for situation in range(4):
            subset = [r for r in scored if r['method'] == method and r['domain'] == domain and r['scenario'] == situation]
            pairs += all(r['concordant'] for r in subset)
    print(method, 'opposite-action pairs', pairs, '/ 12')
