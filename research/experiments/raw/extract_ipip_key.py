import json
import re
from pathlib import Path

source = Path('work/IPIPNEO120-paper.txt').read_text()
matches = re.findall(r'^\d+\s+(\d+)\s+(\+|/C0)([NEOAC][1-6])\s+(.+?)\s+\.\d+\s*$', source, re.M)
items = [{'item': int(number), 'facet': facet, 'reverse': sign != '+', 'text': label}
         for number, sign, facet, label in matches]
assert len(items) == 120, len(items)
assert sorted(item['item'] for item in items) == list(range(1, 121))
assert len({item['facet'] for item in items}) == 30
assert all(sum(item['facet'] == facet for item in items) == 4 for facet in {item['facet'] for item in items})
Path('outputs/ipip_neo_120_key.json').write_text(json.dumps({
    'source': 'Johnson (2014), Table 1, https://doi.org/10.1016/j.jrp.2014.05.003',
    'items': sorted(items, key=lambda item: item['item']),
}, indent=2) + '\n')
