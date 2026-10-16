from pathlib import Path
import json, sys, time
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
import engine as module
from engine import Engine
from situation import offsets
base=Path('outputs/agent_engine/situation-live-example')
e=Engine.load(base/'run/world.json')
original=module.request_json
records=[]
def recorded(system,context,api,model,max_tokens=600):
 start=time.monotonic()
 result=original(system,context,api,model,max_tokens)
 records.append({'context':context,'response':result,'seconds':round(time.monotonic()-start,3)})
 return result
module.request_json=recorded
model=json.loads((base/'run/summary.json').read_text())['model']
rule=e.agent('alex')['caps_rules'][1]
scenario='Synthetic integration scenario: '+rule['trigger_context']+' What do you do?'
previous=dict(e.agent('alex')['facets'])
e.prepare_situation('alex',scenario,'matched-situation-probe',api='http://127.0.0.1:18081',model=model)
proposal=e.propose('alex',scenario,api='http://127.0.0.1:18081',model=model)
e.commit_action('matched-situation-intention',proposal)
assert e.agent('alex')['facets']==previous
assert e.agent('alex')['situational_state']['perception']['active_rule_ids']
assert any(abs(v)>0 for v in offsets(e.agent('alex'),e.day).values())
assert proposal['context']['temporary_behavior']['tendencies']
assert all('facets_percentiles' not in r['context'] for r in records)
e.save(base/'matched-world.json')
(base/'matched-requests.json').write_text(json.dumps(records,indent=2)+'\n')
result={'passed':True,'scope':'synthetic trigger matched to generated rule; integration only, not evidence of realism',
 'active_rule_ids':e.agent('alex')['situational_state']['perception']['active_rule_ids'],
 'temporary_behavior':proposal['context']['temporary_behavior'],'enduring_traits_unchanged':True,
 'action':proposal['decision']['action'],'status':'intention only; no world outcome awarded'}
(base/'matched-integrity-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
