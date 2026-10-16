"""Manual action codes assigned from facet-pilot-v2-results.blind.json."""

import json
from collections import Counter

LABELS = {
    'B00':'low','B01':'low','B02':'mixed','B03':'low','B04':'low','B05':'low',
    'B06':'low','B07':'low','B08':'high','B09':'high','B10':'low','B11':'high',
    'B12':'high','B13':'mixed','B14':'low','B15':'low','B16':'high','B17':'mixed',
    'B18':'low','B19':'low','B20':'mixed','B21':'high','B22':'low','B23':'high',
    'B24':'low','B25':'low','B26':'low','B27':'high','B28':'mixed','B29':'low',
    'B30':'low','B31':'low','B32':'high','B33':'low','B34':'low','B35':'low',
    'B36':'low','B37':'low','B38':'high','B39':'high','B40':'low','B41':'mixed',
    'B42':'mixed','B43':'low','B44':'low','B45':'low','B46':'mixed','B47':'low',
}

blind = json.load(open('work/facet-pilot-v2-results.blind.json'))
key = json.load(open('work/facet-pilot-v2-results.key.json'))
rows = [json.loads(line) for line in open('work/facet-pilot-v2-results.jsonl')]
assert len(blind) == len(rows) == len(LABELS) == 48
assert set(LABELS) == {entry['blind_id'] for entry in blind}

scored = []
for entry in blind:
    row = rows[key[entry['blind_id']]]
    assert row['response'] == entry['response']
    first, second = {'E':('E2','E3'),'C':('C2','C5'),'O':('O1','O4')}[row['domain']]
    target_high = (row['direction'] == 'first_high') == (row['target_facet'] == first)
    label = LABELS[entry['blind_id']]
    scored.append({**{field:row[field] for field in ('domain','direction','method','target_facet','scenario')},
                   'blind_id':entry['blind_id'], 'label':label, 'target_high':target_high,
                   'concordant':label == ('high' if target_high else 'low')})

for domain in 'ECO':
    print('\n',domain)
    for method in ('domains','facets'):
        group=[r for r in scored if r['domain']==domain and r['method']==method]
        print(method, Counter(r['label'] for r in group), sum(r['concordant'] for r in group), '/',len(group))
    for facet in {'E':['E2','E3'],'C':['C2','C5'],'O':['O1','O4']}[domain]:
        group=[r for r in scored if r['target_facet']==facet and r['method']=='facets']
        print(facet, [(r['direction'],r['label'],r['concordant']) for r in sorted(group,key=lambda x:x['scenario'])])

open('work/facet-pilot-v2-scored.json','w').write(json.dumps(scored,indent=2)+'\n')
