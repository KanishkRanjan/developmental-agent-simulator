from pathlib import Path
import json,sys
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
from initialize_life import initialize
from lifetime import Lifetime
base=Path('outputs/agent_engine/interaction-live-example')
base.mkdir(exist_ok=True)
e=initialize(inherited=True)
e.advance(5*365.25)
p=json.loads(Path('outputs/agent_engine/development-demo.json').read_text())
p['opportunities']=[p['opportunities'][0]]
p['opportunities'][0]['options']=[p['opportunities'][0]['options'][0]]
p.pop('consolidation_batch_size',None)
p['description']='One child request and an independent caregiver reply on the actual model. Child request is forced to exercise interaction; caregiver has two replies. Both dispositions use the fitted adult reference with explicit child extrapolation.'
e.save(base/'initial.json')
(base/'policy.json').write_text(json.dumps(p,indent=2)+'\n')
c=Lifetime(e,p)
due=next(iter(e.state['runtime']['next_opportunities'].values()))
(base/'target.json').write_text(json.dumps({'until_day':due,'scope':p['description']},indent=2)+'\n')
print(due)
