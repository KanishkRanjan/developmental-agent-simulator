from pathlib import Path
import json,sys,time
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
import engine as module
from engine import Engine
base=Path('outputs/agent_engine/interaction-live-example')
e=Engine.load(base/'run/world.json')
e.advance(18*365.25)
model=json.loads((base/'run/summary.json').read_text())['model']
records=[]
original=module.request_json
def record(system,context,api,model,max_tokens=600):
 out=original(system,context,api,model,max_tokens)
 records.append({'context':context,'response':out})
 return out
module.request_json=record
start=time.monotonic()
e.generate_signatures('alex',api='http://127.0.0.1:18081',model=model)
assert e.agent('alex')['caps_versions'] and e.agent('alex')['caps_provenance']['stage']==2
proposal=e.propose('maya','Alex, a person in your care, asks whether you can help plan a difficult task. What do you do?',
 api='http://127.0.0.1:18081',model=model)
assert any(r['dependent']=='alex' for r in proposal['context']['identity']['known_caregiving_roles'])
assert all('facets_percentiles' not in r['context'] for r in records)
e.save(base/'age-refresh-world.json')
result={'passed':True,'scope':'synthetic age skip for signature refresh and one caregiver proposal; no full life development inferred, no new action committed',
 'seconds':round(time.monotonic()-start,3),'archived_signature_versions':len(e.agent('alex')['caps_versions']),
 'new_stage':e.agent('alex')['caps_provenance']['stage'],'known_caregiving_role_in_context':True,'requests':records}
(base/'age-refresh-smoke.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='requests'},indent=2))
