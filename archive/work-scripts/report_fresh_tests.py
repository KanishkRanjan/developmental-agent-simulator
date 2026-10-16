from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json,sys
sys.path.insert(0,'outputs/agent_engine')
from engine import Engine
import situation
b=Path('outputs/agent_engine')
def read(p):return json.loads(p.read_text())
def write(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n')
checks=read(Path('work/fresh-regression-results.json'));assert all(x['exit_code']==0 for x in checks)
old=read(b/'final-engineering-verification.json')
suites=[]
for item in old['scripts']:
 name=item['script'].removeprefix('check_').removesuffix('.py').replace('_','-')
 data=read(b/(name+'-engineering-checks.json'));assert data['passed']
 suites.append({**item,'checks':len(data['checks'])})
core=read(b/'final-core-retest/engineering-checks.json');assert core['passed']
sources=[Path(p) for p in old['source_sha256']]
verification={**old,'verified_utc':datetime.now(timezone.utc).isoformat(),'scripts':suites,
 'named_checks':sum(x['checks'] for x in suites),'core_demo':{'passed':True,'checks':len(core['checks']),'path':'final-core-retest/engineering-checks.json'},
 'source_sha256':{str(p):sha256(p.read_bytes()).hexdigest() for p in sources}}
write(b/'pre-infant-fix-verification.json',old)
lives={}
for name in ['fresh-integrated-test/run','fresh-infant-test/run','fresh-memory-continuation','fixed-infant-test-v2/run']:
 folder=b/name;summary=read(folder/'summary.json');assert summary['status']=='completed'
 e=Engine.load(folder/'world.json');e.save(folder/'world.sqlite');assert Engine.load(folder/'world.sqlite').state==e.state
 assert not e.state['runtime'].get('pending_activities')
 rows=[json.loads(line) for line in (folder/'requests.jsonl').read_text().splitlines()]
 assert all('facets' not in r['context'] and 'facets_percentiles' not in r['context'] for r in rows)
 initial=Engine.load(b/'full-build-live/run/world.json' if name=='fresh-memory-continuation' else folder.parent/'initial.json')
 for owner,episodes in initial.world.observations.items():assert e.world.observations[owner][:len(episodes)]==episodes
 if name=='fresh-memory-continuation':assert e.state['actions'][:len(initial.state['actions'])]==initial.state['actions']
 for a in e.state['actions'][len(initial.state['actions']):]:
  assert a['status']=='resolved'
  outcome=next(v for v in e.state['events'] if v['id']==a['outcome_event']);assert outcome['day']>a['day']
 if name=='fixed-infant-test-v2/run':
  a=next(a for a in e.state['actions'] if a['owner']=='bea');assert a['decision']['speech']=='' and a['decision']['plan']==[]
  assert all(r['trigger_context'] in [v[1] for v in situation.INFANT_TRIGGERS.values()] and r['narrative_shift'] in situation.INFANT_REACTIONS.values() for r in e.agent('bea')['caps_rules'])
 info={'passed':True,'status':summary['status'],'requests':len(rows),'new_actions':summary['new_actions'],
       'seconds':summary['seconds'],'repairs':sum('output_repair' in r['context'] for r in rows),
       'json_sqlite_equivalence':True,'earlier_history_preserved':True,'no_pending_activities':True,
       'elapsed_outcomes':True,'requests_by_purpose':summary['requests'],
       'source_files_changed_since_launch':[Path(p).name for p,digest in read(folder/'source-hashes.json').items() if sha256(Path(p).read_bytes()).hexdigest()!=digest]}
 write(folder/'integrity-checks.json',info);lives[name]=info
century=Engine.load(b/'fresh-century-test/world.json');assert Engine.load(b/'fresh-century-test/world.sqlite').state==century.state
assert century.day==36525 and not century.state['runtime']['pending_activities']
assert all(a['status']=='resolved' for a in century.state['actions'])
century_info={**read(b/'fresh-century-test/summary.json'),'passed':True,'deaths':sum(not a['alive'] for a in century.state['agents'].values()),'json_sqlite_equivalence':True,'no_pending_activities':True}
write(b/'fresh-century-test/integrity-checks.json',century_info)
failed=read(b/'fixed-infant-test/run/summary.json');assert failed['status']=='failed'
failure_world=Engine.load(b/'fixed-infant-test/run/world.json');assert not failure_world.state['actions'] and not failure_world.agent('bea').get('caps_rules')
report={'scope':'software integration and correctness; comparative/human predictive evaluation deferred',
 'verified_utc':verification['verified_utc'],'regression_suites':len(suites),'named_checks':verification['named_checks'],'core_checks':len(core['checks']),
 'live_runs':lives,'scripted_century':century_info,
 'confirmed_fix':'Bounded infant sensory trigger/nonverbal reaction catalogs, capability context, and rule refresh at ages two/five.',
 'failed_attempt':{'path':'fixed-infant-test/run','reason':'Model used signatures root key instead of rules on all three responses; event rolled back before action or rules committed.',
 'fix':'Required root JSON shape in prompt and precise missing-root validation feedback. Fresh replay succeeded.'},
 'source_sha256':verification['source_sha256']}
write(b/'fresh-integration-verification.json',report)
verification['live_integrity']+=['fixed-infant-test-v2/run/integrity-checks.json','fresh-memory-continuation/integrity-checks.json']
verification['fresh_integration_report']='fresh-integration-verification.json'
write(b/'final-engineering-verification.json',verification)
print(json.dumps({k:v for k,v in report.items() if k not in ['source_sha256','live_runs']},indent=2))
