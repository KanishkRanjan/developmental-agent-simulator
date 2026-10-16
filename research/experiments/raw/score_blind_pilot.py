"""Manual action codes assigned from facet-pilot-results.blind.json."""

import json
from collections import Counter, defaultdict

LABELS = {
    'B00':'high','B01':'high','B02':'low','B03':'high','B04':'high','B05':'high',
    'B06':'high','B07':'mixed','B08':'mixed','B09':'high','B10':'high','B11':'low',
    'B12':'high','B13':'high','B14':'high','B15':'high','B16':'mixed','B17':'high',
    'B18':'high','B19':'low','B20':'high','B21':'mixed','B22':'high','B23':'high',
    'B24':'high','B25':'high','B26':'high','B27':'high','B28':'mixed','B29':'low',
    'B30':'low','B31':'mixed','B32':'high','B33':'mixed','B34':'low','B35':'high',
    'B36':'high','B37':'mixed','B38':'high','B39':'high','B40':'high','B41':'mixed',
    'B42':'high','B43':'high','B44':'high','B45':'low','B46':'low','B47':'high',
}

blind = json.load(open('work/facet-pilot-results.blind.json'))
key = json.load(open('work/facet-pilot-results.key.json'))
rows = [json.loads(line) for line in open('work/facet-pilot-results.jsonl')]
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
        for facet in (r['target_facet'] for r in group[:1]): pass
    for facet in {'E':['E2','E3'],'C':['C2','C5'],'O':['O1','O4']}[domain]:
        group=[r for r in scored if r['target_facet']==facet and r['method']=='facets']
        print(facet, [(r['direction'],r['label'],r['concordant']) for r in sorted(group,key=lambda x:x['scenario'])])

open('work/facet-pilot-scored.json','w').write(json.dumps(scored,indent=2)+'\n')
