from pathlib import Path
import json,sys
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
from engine import Engine
from lifetime import Lifetime
base=Path('outputs/agent_engine/crystallization-live-example')
base.mkdir(exist_ok=True)
e=Engine.load('outputs/agent_engine/development-live-example/run/world.json')
e.state.pop('runtime')
p=json.loads(Path('outputs/agent_engine/development-live-example/policy.json').read_text())
p.pop('consolidation_batch_size',None)
p['opportunities']=[{'id':'cleanup','actor':'alex','min_age':5,'max_age':12,'rate_per_year':6,
 'situation':'Maya asks you to clean a shared play area. Another child left the mess; you did not make it. You have time to respond and act. What do you do?',
 'options':[{'id':'tidy','label':'Explain that it feels unfair, then tidy the play area carefully.','success_probability':1,
 'success_text':'I said that the mess was not mine, then tidied the play area carefully.','failure_text':'I tried to tidy but struggled.',
 'valence_success':.1,'valence_failure':-.2},
 {'id':'decline','label':'Decline the cleanup and return to your own game.','success_probability':1,
 'success_text':'I declined the cleanup and returned to my game.','failure_text':'I could not return to the game.',
 'valence_success':.1,'valence_failure':-.1}]}]
p['description']='Synthetic repeated-trigger integration fixture based on an already generated signature. Not an independent realism evaluation. Two actions offered; state-conditioned exposure remains an unvalidated proxy for enacted state.'
e.save(base/'initial.json')
(base/'policy.json').write_text(json.dumps(p,indent=2)+'\n')
c=Lifetime(e,p)
o=p['opportunities'][0]
due=e.state['runtime']['next_opportunities']['cleanup']
for seq in (1,2):
 due=c._next_opportunity(o,due,seq)
(base/'target.json').write_text(json.dumps({'until_day':due,'scope':p['description']},indent=2)+'\n')
print(due)
