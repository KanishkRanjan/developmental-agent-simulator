import json,sys
from pathlib import Path
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
from full_scenario import build
from lifetime import Lifetime
base=Path('outputs/agent_engine/full-build-live');base.mkdir(exist_ok=True)
e,p=build()
for mid,day,text,meaning in [('seed-rejection',16*365.25,'Bea did not reply when I shared an idea.','I felt uncertain about sharing ideas.'),
 ('seed-context',17*365.25,'Bea said being busy had delayed a reply.','A delayed reply can have explanations besides rejection.'),
 ('seed-meeting',18*365.25,'Bea and I met to discuss making time for projects and friendship.','I care about both shared projects and friendship.')]:
 observation={'text':text,'source':'direct','meaning':meaning,'importance':.7,'references':['bea']}
 if mid=='seed-meeting':observation['encountered']=['bea']
 recipients={'alex':observation}
 if mid=='seed-meeting':recipients['bea']={'text':'Alex and I met to discuss our projects and friendship.','source':'direct','encountered':['alex']}
 e.schedule(mid,day,'Explicitly seeded synthetic history.',recipients);e.advance(day)
 e.agent('alex')['memory_meta'][mid].update(summary=meaning,topics=['relationships','projects','sharing'])
p['world_hazards']=[];p['world_events']=[];p['newborn_opportunities']=[];p['newborn_hazards']=[];p.pop('goal_opportunity')
p['cognition']['rumination_per_year']=0
rule=p['opportunities'][3];p['opportunities']=[rule];rule['id']='live-joint-task';rule['min_age']=18;rule['max_age']=19;rule['rate_per_year']=365
rule['situation']='Bea is available to discuss a project. Decide whether to discuss it together or work alone.'
# Preserve two offered choices and independent peer responses. No result is forced.
c=Lifetime(e,p);due=e.state['runtime']['next_opportunities'][rule['id']]
e.save(base/'initial.json');(base/'policy.json').write_text(json.dumps(p,indent=2)+'\n')
until=due+2/24+.00001
(base/'target.json').write_text(json.dumps({'until_day':until,'first_start_day':due,
 'scope':'short age-18 fixture with seeded history and omitted earlier years; full-source pipeline engineering only'},indent=2)+'\n')
print(until)
