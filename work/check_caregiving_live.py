from pathlib import Path
import json,sys,time
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
import engine as module
from engine import Engine
base=Path('outputs/agent_engine/development-live-example')
e=Engine.load(base/'run/world.json')
model=json.loads((base/'run/summary.json').read_text())['model']
seen=[]
original=module.request_json
def recorded(system,context,api,model,max_tokens=600):
 seen.append(context)
 return original(system,context,api,model,max_tokens)
module.request_json=recorded
before=json.dumps(e.state,sort_keys=True)
observation={'text':'Maya sat beside me, listened while I explained why I was upset, and said it was okay to be stuck. We still did not solve the project.',
 'source':'direct','kind':'direct','encountered':['maya'],'valence':-.9,'arousal':.99,'importance':.99,'confidence':.99,
 'caregiving':{'caregiver':'maya','responsiveness':.01,'acceptance':.01}}
start=time.monotonic()
appraised=e.appraise('alex',observation,api='http://127.0.0.1:18081',model=model)
assert json.dumps(e.state,sort_keys=True)==before
assert set(seen[0]['new_observation']['caregiving'])=={'caregiver'}
assert not set(seen[0]['new_observation']) & {'valence','arousal','importance','confidence','meaning'}
result={'passed':True,'scope':'one actual-model appraisal without controller score hints; no event committed',
 'seconds':round(time.monotonic()-start,3),'controller_scores_omitted_from_model_input':True,
 'appraisal':appraised,'context':seen[0]}
(base/'final-caregiving-smoke.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='context'},indent=2))
