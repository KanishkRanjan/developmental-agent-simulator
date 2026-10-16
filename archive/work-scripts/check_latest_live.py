from pathlib import Path
import json,sys,time
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
from engine import Engine
base=Path('outputs/agent_engine/crystallization-live-example')
e=Engine.load(base/'run/world.json')
model=json.loads((base/'run/summary.json').read_text())['model']
start=time.monotonic()
proposal=e.propose('alex','A friend asks whether you would like to draw a picture together. What do you do?',api='http://127.0.0.1:18081',model=model)
assert 'facets_percentiles' not in proposal['context']
assert 'learned_caregiver_models' in proposal['context']['attachment_expectations']
result={'passed':True,'scope':'one actual model proposal using final context compaction and tokenizer guard; no action committed',
 'seconds':round(time.monotonic()-start,3),'decision':proposal['decision'],'context_view':proposal['context']['context_view']}
(base/'final-transport-smoke.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
