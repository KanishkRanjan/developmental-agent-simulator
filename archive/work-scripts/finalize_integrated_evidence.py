from pathlib import Path
from hashlib import sha256
import json,sys
from datetime import datetime,timezone
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
from engine import Engine
b=Path('outputs/agent_engine'); live=b/'integrated-live-example'; final=live/'final-continued-run'
e=Engine.load(final/'world.json');initial=Engine.load(live/'initial.json');previous=Engine.load(live/'continued-run/world.json')
assert len(e.state['actions'])==4 and all(a['status']=='resolved' for a in e.state['actions'])
assert e.state['actions'][:2]==previous.state['actions']
for owner,episodes in initial.world.observations.items(): assert e.world.observations[owner][:len(episodes)]==episodes
assert e.agent('alex')['narrative_identity'] and e.agent('alex')['habits'] and e.agent('alex')['time_use']
assert e.state['entities']['alex']['facts']['education'] in ('secondary-school','vocational-school')
assert e.agent('alex')['resources']['money']==25
assert any(t.get('kind')=='autonomous_recall' and t.get('memory') for t in e.state['runtime']['trace'])
revisions=[u for u in e.state['updates'] if u['kind']=='revision']
assert len(revisions)>=2
for u in revisions: assert all(mid in e.agent(u['owner'])['memory_meta'] for mid in u['evidence'])
records=[]
for directory in ('continued-run','final-continued-run'):
 rows=[json.loads(x) for x in (live/directory/'requests.jsonl').read_text().splitlines()]; records.extend(rows)
 assert all('facets' not in r['context'] and 'facets_percentiles' not in r['context'] for r in rows)
 for r in rows:
  for m in r['context'].get('memory_candidates',[]): assert m['event'] in e.agent(r['agent'])['memory_meta']
  if r['purpose']=='reflection': assert r['context']['new_evidence']['event'] not in r['context'].get('revision_target_ids',[])
hashes=json.loads((final/'source-hashes.json').read_text())
for name in ('engine.py','cognition.py','life_policy.py','lifetime.py','run_live.py','initialize_life.py','context_view.py'):
 p=b/name;assert hashes[str(p.resolve())]==sha256(p.read_bytes()).hexdigest(),name
result={'passed':True,'scope':'short actual HauhauCS 27B integration with seeded prior history; not predictive validation or a full live lifetime',
 'final_day':e.day,'resolved_actions':len(e.state['actions']),'initial_actions_preserved':True,
 'original_episodes_preserved':True,'model_requests_successful_segments':len(records),'received_evidence_revisions':len(revisions),
 'semantic_recall_calls':sum(r['purpose']=='semantic_recall' for r in records),'reflection_calls':sum(r['purpose']=='reflection' for r in records),
 'narrative_present':True,'habits_and_time_accounting_present':True,'background_choice_committed':True,
 'checkpoint_restored':True,'final_runtime_sources_match_recorded_hashes':True,
 'failed_attempts_preserved':['run','final-run'],'late_branched_features_locally_checked':['multi-generation scheduling','new caregiver creation','daily social budgets','illness/death branch']}
(final/'integrity-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
# Preserve the earlier developmental verification before updating the entry point.
manifest=b/'final-engineering-verification.json';archive=b/'development-stage-verification.json'
if not archive.exists(): archive.write_bytes(manifest.read_bytes())
files={'context':'context','fidelity':'fidelity','situation':'situation','lifetime':'lifetime','development':'development',
 'temperament':'temperament','world_growth':'world-growth','interaction':'interaction','extended':'extended'}
scripts=[]
for name,out in files.items():
 data=json.loads((b/(out+'-engineering-checks.json')).read_text());assert data['passed']
 scripts.append({'script':'check_'+name+'.py','passed':True,'checks':len(data['checks']),'scope':data['scope']})
core=json.loads((b/'integrated-final-core/engineering-checks.json').read_text());assert core['passed']
sources=list(b.glob('*.py'))+[b.parent/'identity_state_prototype.py',b.parent/'profile_population_v1.py',b.parent/'profile_population_v1_model.json',b/'integrated-demo.json']
verification={'passed':True,'verified_utc':datetime.now(timezone.utc).isoformat(),
 'scope':'engineering properties only; short actual-model integration recorded separately, no human predictive validity',
 'scripts':scripts,'named_checks':sum(r['checks'] for r in scripts),'core_demo':{'passed':True,'checks':len(core['checks']),'path':'integrated-final-core/engineering-checks.json'},
 'source_sha256':{str(p.resolve()):sha256(p.read_bytes()).hexdigest() for p in sources},
 'live_integrity':'integrated-live-example/final-continued-run/integrity-checks.json'}
manifest.write_text(json.dumps(verification,indent=2)+'\n')
print('Named checks:',verification['named_checks'])
