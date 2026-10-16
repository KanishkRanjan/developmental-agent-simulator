from pathlib import Path
import json,sys
from hashlib import sha256
from datetime import datetime,timezone
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
from engine import Engine
b=Path('outputs/agent_engine')
for label in ('full-build-live','full-build-infant-live'):
 folder=b/label/'run';e=Engine.load(folder/'world.json');s=e.state
 records=[json.loads(r) for r in (folder/'requests.jsonl').read_text().splitlines()]
 summary=json.loads((folder/'summary.json').read_text());assert summary['status']=='completed'
 assert len(s['actions'])==2 and all(a['status']=='resolved' for a in s['actions']) and not s['runtime']['pending_activities']
 for action in s['actions']:
  event=next(event for event in s['events'] if event['id']==action['outcome_event'])
  assert event['day']>action['day']
 for record in records:
  assert 'facets' not in record['context'] and 'facets_percentiles' not in record['context']
  for memory in record['context'].get('memory_candidates',[]): assert memory['event'] in s['agents'][record['agent']]['memory_meta']
 initial=Engine.load(b/label/'initial.json')
 for owner,episodes in initial.world.observations.items():assert e.world.observations[owner][:len(episodes)]==episodes
 e.save(folder/'world.sqlite');assert Engine.load(folder/'world.sqlite').state==s
 result={'passed':True,'scope':'actual HauhauCS 27B integration; scenario fixture, no human predictive claim',
   'requests':len(records),'resolved_actions':2,'pending_activities':0,'elapsed_outcomes':True,
   'json_sqlite_equivalence':True,'earlier_episodes_preserved':True,
   'model':summary['model'],'seconds':summary['seconds'],
   'repair_requests':sum('output_repair' in row['context'] for row in records),
   'generated_biographies':[key for key,entity in s['entities'].items() if entity.get('generated_biography')]}
 if label.endswith('infant-live'):
  child=[a for a in s['actions'] if a['owner']=='alex'][0]
  assert child['decision']['speech']=='' and child['decision']['plan']==[]
  assert s['agents']['alex'].get('narrative_identity') is None
  result.update(infant_nonverbal=True,infant_narrative_absent=True,caregiving_episodes=len(s['agents']['alex'].get('caregiving_experiences',[])),
    caregiver_chosen_response=next(a['decision']['action_id'] for a in s['actions'] if a['owner']=='maya'))
 source_hashes=json.loads((folder/'source-hashes.json').read_text())
 result['later_modified_source_files']=[Path(name).name for name,digest in source_hashes.items() if sha256(Path(name).read_bytes()).hexdigest()!=digest]
 (folder/'integrity-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(label,result)
manifest=b/'final-engineering-verification.json';archive=b/'integrated-stage-verification.json'
if not archive.exists():archive.write_bytes(manifest.read_bytes())
files={'context':'context','fidelity':'fidelity','situation':'situation','lifetime':'lifetime','development':'development',
 'temperament':'temperament','world_growth':'world-growth','interaction':'interaction','extended':'extended','complete':'complete'}
scripts=[]
for name,out in files.items():
 data=json.loads((b/(out+'-engineering-checks.json')).read_text());assert data['passed']
 scripts.append({'script':'check_'+name+'.py','passed':True,'checks':len(data['checks']),'scope':data['scope']})
core=json.loads((b/'full-build-core-check/engineering-checks.json').read_text());assert core['passed']
sources=list(b.glob('*.py'))+[b.parent/'identity_state_prototype.py',b.parent/'profile_population_v1.py',b.parent/'profile_population_v1_model.json']
verification={'passed':True,'verified_utc':datetime.now(timezone.utc).isoformat(),'scope':'engineering checks; scientific/human predictive validity not established',
 'scripts':scripts,'named_checks':sum(r['checks'] for r in scripts),
 'core_demo':{'passed':True,'checks':len(core['checks']),'path':'full-build-core-check/engineering-checks.json'},
 'source_sha256':{str(p.resolve()):sha256(p.read_bytes()).hexdigest() for p in sources},
 'live_integrity':['full-build-live/run/integrity-checks.json','full-build-infant-live/run/integrity-checks.json'],
 'lifespan_integrity':'full-lifespan-final/integrity-checks.json'}
manifest.write_text(json.dumps(verification,indent=2)+'\n');print('Named checks:',verification['named_checks'])
