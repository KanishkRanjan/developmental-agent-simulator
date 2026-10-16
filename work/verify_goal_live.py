from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import sys,json
sys.path.insert(0,'outputs/agent_engine')
from engine import Engine
b=Path('outputs/agent_engine')
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
results={}
for label in ['goal-plans-live','goal-plans-success-live']:
 p=b/label/'run';s=read(p/'summary.json');assert s['status']=='completed'
 e=Engine.load(p/'world.json');e.save(p/'world.sqlite');assert Engine.load(p/'world.sqlite').state==e.state
 assert not e.state['runtime']['pending_activities']
 rows=[json.loads(line) for line in (p/'requests.jsonl').read_text().splitlines()]
 assert s['requests']['goal_planning']>0
 assert all('facets' not in r['context'] and 'facets_percentiles' not in r['context'] for r in rows)
 for action in e.state['actions']:
  assert action['status']=='resolved';outcome=next(v for v in e.state['events'] if v['id']==action['outcome_event']);assert outcome['day']>action['day']
 changed=[Path(name).name for name,digest in read(p/'source-hashes.json').items() if sha256(Path(name).read_bytes()).hexdigest()!=digest]
 assert not changed
 g=e.agent('maya')['goals']['personal-task' if label=='goal-plans-live' else 'draft-review']
 if label=='goal-plans-live':
  assert g['progress']==0 and g['status']=='active' and g['execution_plan']['needs_replan']
  assert any(a['success'] is False for t in g['execution_plan']['steps'] for a in t['attempts'])
  assert all(t['status']=='pending' for t in g['execution_plan']['steps'])
 else:
  assert g['progress']==1 and g['status']=='completed'
  steps=[t for plan in [*g.get('execution_plan_versions',[]),g['execution_plan']] for t in plan['steps'] if t['status']=='completed']
  assert {t['action_id'] for t in steps}=={'draft','review'}
  assert all(t['completed_event'] in e.agent('maya')['memory_meta'] for t in steps)
  assert len(e.state['actions'])==2
 result={'passed':True,'scope':'actual 27B engineering fixture; not predictive/personality validation',
  'model':s['model'],'requests':sum(s['requests'].values()),'goal_planning_requests':s['requests']['goal_planning'],
  'resolved_actions':s['new_actions'],'seconds':s['seconds'],'repair_requests':sum('output_repair' in r['context'] for r in rows),
  'goal_status':g['status'],'goal_progress':g['progress'],'no_pending_activities':True,'elapsed_outcomes':True,
  'json_sqlite_equivalence':True,'source_hashes_match_current':True}
 write(p/'integrity-checks.json',result);results[label]=result
report=read(b/'goal-plans-verification.json');report['actual_27b_new_layer']={'status':'completed','fixtures':results,
 'scope':'default policy failure path plus controlled draft/review successful outcomes; one eligible action per stage in success fixture'}
report['prior_live_traces']='Earlier traces retain their historical scope; these new fixtures exercise the goal execution layer on the current source.'
report['live_verified_utc']=datetime.now(timezone.utc).isoformat();write(b/'goal-plans-verification.json',report)
v=read(b/'final-engineering-verification.json');assert all(sha256(Path(name).read_bytes()).hexdigest()==digest for name,digest in v['source_sha256'].items())
for label in results:
 path=label+'/run/integrity-checks.json'
 if path not in v['live_integrity']:v['live_integrity'].append(path)
v['goal_plans_live_verified_utc']=report['live_verified_utc'];write(b/'final-engineering-verification.json',v)
print(json.dumps(results,indent=2))
