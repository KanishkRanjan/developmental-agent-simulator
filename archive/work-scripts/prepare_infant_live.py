from pathlib import Path
import json,sys
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
from full_scenario import build
from lifetime import Lifetime
e,p=build();p['opportunities']=[p['opportunities'][0]];p['opportunities'][0]['rate_per_year']=365
p['world_hazards']=[];p['world_events']=[];p['newborn_opportunities']=[];p['newborn_hazards']=[]
p.pop('goal_opportunity');p['cognition']['rumination_per_year']=0
b=Path('outputs/agent_engine/full-build-infant-live');b.mkdir(exist_ok=True)
c=Lifetime(e,p);due=e.state['runtime']['next_opportunities'][p['opportunities'][0]['id']];until=due+1/24
(b/'target.json').write_text(json.dumps({'until_day':until,'first_day':due,'scope':'synthetic infancy integration with two offered nonverbal choices, not calibrated development'},indent=2)+'\n')
e.save(b/'initial.json');(b/'policy.json').write_text(json.dumps(p,indent=2)+'\n');print(until)
