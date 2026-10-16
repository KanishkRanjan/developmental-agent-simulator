from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json,sys,time
sys.path.insert(0,'outputs/agent_engine')
from engine import Engine
import graphiti_bridge
b=Path('outputs/agent_engine')
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
p=b/'graphiti-live/run-verified';summary=read(p/'summary.json');assert summary['status']=='completed'
e=Engine.load(p/'world.json');initial=Engine.load(b/'graphiti-live/initial.json')
assert len(e.state['actions'])==1 and e.state['actions'][0]['status']=='resolved' and not e.state['runtime']['pending_activities']
a=e.state['actions'][0];assert next(v['day'] for v in e.state['events'] if v['id']==a['outcome_event'])>a['day']
assert e.agent('alex')['retrieval_focus']['graph_retrieval']['status']=='ready'
assert e.agent('alex')['retrieval_focus']['graph_retrieval']['backend']=='graphiti_neo4j_local_bge_rrf'
assert set(e.agent('alex')['retrieval_focus']['ids'])=={'dismissal','encouragement'}
rows=[json.loads(line) for line in (p/'requests.jsonl').read_text().splitlines()]
assert summary['requests']['retrieval_query']==0 and len(rows)==5
assert all('violet observatory' not in json.dumps(r['context']).lower() and 'facets' not in r['context'] for r in rows)
for owner,old in initial.world.observations.items():assert e.world.observations[owner][:len(old)]==old
e.save(p/'world.sqlite');assert Engine.load(p/'world.sqlite').state==e.state
changed=[Path(name).name for name,d in read(p/'source-hashes.json').items() if sha256(Path(name).read_bytes()).hexdigest()!=d];assert not changed
integrity={'passed':True,'model':summary['model'],'requests':len(rows),'repairs':sum('output_repair' in r['context'] for r in rows),
 'seconds':summary['seconds'],'resolved_actions':1,'semantic_recall_ids':e.agent('alex')['retrieval_focus']['ids'],
 'graph_backend':e.agent('alex')['retrieval_focus']['graph_retrieval']['backend'],'no_graph_fallback':True,
 'original_episodes_preserved':True,'other_agent_private_episode_excluded':True,'json_sqlite_equivalence':True,
 'elapsed_outcome':True,'no_pending_activities':True,'current_source_hashes_match':True,
 'scope':'seeded adult wiring fixture with neutral synthetic traits, omitted childhood, one eligible activity and guaranteed outcome; not realism or personality-choice evaluation'}
write(p/'integrity-checks.json',integrity)
# Ensure the latest canonical checkpoint views reached the background worker.
for owner,agent in e.state['agents'].items():
 if agent['alive'] and agent['memory_meta']:
  key=graphiti_bridge.snapshot_key(graphiti_bridge.snapshot(e,owner));end=time.monotonic()+45
  while True:
   status=graphiti_bridge.request('/status/'+key)
   if status['status']=='done':break
   assert status['status']!='failed',status
   if time.monotonic()>end:raise AssertionError('Final graph outbox did not drain')
   time.sleep(.1)
manifest=b/'final-engineering-verification.json'
if not (b/'pre-graphiti-verification.json').exists():write(b/'pre-graphiti-verification.json',read(manifest))
v=read(b/'pre-graphiti-verification.json');assert all(r['exit_code']==0 for r in read(Path('work/fresh-regression-results.json')))
check=read(b/'graphiti-engineering-checks.json');assert check['passed']
v['scripts'].append({'script':'check_graphiti.py','checks':len(check['checks']),'passed':True,'scope':check['scope']})
v['named_checks']=sum(s['checks'] for s in v['scripts']);assert v['named_checks']==161
core=read(b/'graphiti-core-check/engineering-checks.json');assert core['passed']
v['core_demo']={'passed':True,'checks':len(core['checks']),'path':'graphiti-core-check/engineering-checks.json'}
files=list(b.rglob('*.py'))+[b.parent/'identity_state_prototype.py',b.parent/'profile_population_v1.py',b.parent/'profile_population_v1_model.json']
v['source_sha256']={str(path.resolve()):sha256(path.read_bytes()).hexdigest() for path in files}
v['verified_utc']=datetime.now(timezone.utc).isoformat();v['latest_phase']='graphiti-verification.json';v['live_integrity'].append('graphiti-live/run-verified/integrity-checks.json');write(manifest,v)
restart=read(b/'graphiti-restart-probe-final/integrity-checks.json');assert restart['passed']
report={'verified_utc':v['verified_utc'],'named_checks':v['named_checks'],'core_checks':len(core['checks']),
 'scope':'local infrastructure and integrated behavior; no measured improvement in human prediction',
 'actual_local_graph_service':graphiti_bridge.request('/health'),'live_27b':integrity,'durable_restart':restart,
 'latest_checkpoint_views_indexed':True,'hosted_services_used':False,'subscription_required':False,
 'embedding':{'name':'BAAI/bge-small-en-v1.5','revision':'5c38ec7c405ec4b44b94cc5a9bb96e735b38267a','device':'cpu','dimensions':384},
 'mirofish_reference_commit':'7657031ac01184afe2cb220f5ee3545573b5e843',
 'preserved_attempts':{'run':'initial live Graphiti wiring before later view-time/startup refinements',
   'run-final':'service-start race caused a recorded private-FTS fallback; subsequently added bounded startup-503 waiting',
   'run-verified':'current final runtime, actual graph retrieval without fallback'},
 'limits':['immutable view graphs need cache compaction for long live population runs','no autonomous Graphiti LLM fact extraction or claim invalidation','panorama is checkpoint interpretation history, not exact past cognitive state reconstruction','short seeded live fixture, not full live lifespan or accuracy evaluation'],
 'source_sha256':v['source_sha256']}
write(b/'graphiti-verification.json',report);print(json.dumps({k:z for k,z in report.items() if k not in ['source_sha256','limits','preserved_attempts']},indent=2))
