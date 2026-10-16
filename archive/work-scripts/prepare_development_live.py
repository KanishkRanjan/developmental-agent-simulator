from pathlib import Path
import json, sys
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
from initialize_life import initialize
from lifetime import Lifetime
base=Path('outputs/agent_engine/development-live-example')
base.mkdir(exist_ok=True)
e=initialize(inherited=True)
e.advance(5*365.25)
p=json.loads(Path('outputs/agent_engine/development-demo.json').read_text())
p['opportunities']=[p['opportunities'][0]]
o=p['opportunities'][0]
o['rate_per_year']=12
o['options']=[o['options'][0]]
o['options'][0]['success_probability']=0
p['consolidation_batch_size']=3
p['description']='Synthetic integration fixture: three received caregiving episodes despite unsolved tasks. One offered action deliberately tests wiring. Rates, maturity curves and genetic variance share are unfitted. Empty years before age five were not developed.'
e.save(base/'initial.json')
(base/'policy.json').write_text(json.dumps(p,indent=2)+'\n')
c=Lifetime(e,p)
due=e.state['runtime']['next_opportunities'][o['id']]
for sequence in (1,2):
 due=c._next_opportunity(o,due,sequence)
(base/'target.json').write_text(json.dumps({'until_day':due,'scope':p['description']},indent=2)+'\n')
print(due)
