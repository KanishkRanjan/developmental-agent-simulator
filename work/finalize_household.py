from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json,sys
sys.path.insert(0,'outputs/agent_engine')
from engine import Engine
import household
b=Path('outputs/agent_engine')
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
p=b/'household-live/run';s=read(p/'summary.json');assert s['status']=='completed'
e=Engine.load(p/'world.json');initial=Engine.load(b/'household-live/initial.json')
assert Engine.load(p/'world.sqlite').state==e.state
session=e.state['runtime']['conversations']['homework'];turns=session['turns']
assert len(turns)==4 and [t['speaker'] for t in turns]==['alex','maya','alex','maya']
assert session['status']=='closed' and session['next_day'] is None and not session['reservations']
assert len(e.state['actions'])==4 and all(a['status']=='resolved' for a in e.state['actions'])
assert all(t['recipients']==[t['speaker'],*(['maya','bea'] if t['speaker']=='alex' else ['alex','bea'])] for t in turns)
assert all(t['event'] in e.agent('bea')['memory_meta'] and t['event'] not in e.agent('noor')['memory_meta'] for t in turns)
assert list(e.agent('noor')['memory_meta'])==['noor-private']
assert all(not ev['facts'] and not ev['outcomes'] for ev in e.state['events'])
rows=[json.loads(line) for line in (p/'requests.jsonl').read_text().splitlines()]
assert len(rows)==23
assert all('PRIVATE_VIOLET_OBSERVATORY' not in json.dumps(r['context']) for r in rows)
assert all('facets' not in r['context'] for r in rows)
assert all(r['context']['personality'] for r in rows)
for owner,observations in initial.world.observations.items():assert e.world.observations[owner][:len(observations)]==observations
for owner in ['alex','maya']:
 assert e.agent(owner)['retrieval_focus']['graph_retrieval']['status']=='ready'
 assert all(r['status']=='completed' for r in e.agent(owner)['calendar'])
action_rows=[r for r in rows if r['purpose']=='action']
assert action_rows[1]['agent']=='maya' and turns[0]['event'] in json.dumps(action_rows[1]['context'])
changed=[Path(name).name for name,h in read(p/'source-hashes.json').items() if sha256(Path(name).read_bytes()).hexdigest()!=h]
assert set(changed)=={'full_scenario.py','household.py','check_household.py'},changed
version_note=('The live trace used its preserved source hashes. Subsequent edits added only the optional crystallization hook in household.py (disabled in this live policy), corrected illustrative full_scenario.py conversation clock times (not imported by run_live.py), and extended check_household.py. Final-version household/legacy regressions and the seven-year scripted combined run passed separately.')
integrity={'passed':True,'model':s['model'],'seconds':s['seconds'],'requests':len(rows),
 'repairs':sum('output_repair' in r['context'] for r in rows),'resolved_conversation_turns':4,
 'speakers':[t['speaker'] for t in turns],'bystander_received':True,'closed_room_excluded':True,
 'private_absent_agent_episode_excluded_from_model_contexts':True,'numeric_facet_table_not_sent':True,
 'subsequent_reply_has_received_prior_turn':True,'no_canonical_claim_promotion':True,
 'original_episodes_preserved':True,'json_sqlite_equivalence':True,'no_pending_conversation_reservations':True,
 'graph_backend':'graphiti_neo4j_local_bge_rrf','no_graph_fallback':True,
 'source_files_changed_after_live_load':changed,'source_version_boundary':version_note,
 'scope':'Synthetic adolescent/caregiver dialogue wiring, manually initialized dispositions and omitted childhood; no measured realism or predictive advantage.'}
write(p/'integrity-checks.json',integrity)
lifetime=Engine.load(b/'household-lifetime-final/world.json')
assert Engine.load(b/'household-lifetime-final/world.sqlite').state==lifetime.state
completed=[k for k,v in lifetime.state['runtime']['conversations'].items() if v['status']=='closed']
assert len(completed)==4
assert sum(len(v['turns']) for v in lifetime.state['runtime']['conversations'].values())==16
assert len(lifetime.state['actions'])==61 and all(a['status']=='resolved' for a in lifetime.state['actions'])
assert sum(len(a.get('developmental_exposures',[])) for a in lifetime.state['agents'].values())>=16
assert not lifetime.state['runtime']['pending_activities']
write(b/'household-lifetime-final/integrity-checks.json',{'passed':True,'years':7,'provider':'scripted_engineering_fixture',
 'resolved_actions':61,'completed_conversations':4,'conversation_turns':16,'retained_agents':6,
 'json_sqlite_equivalence':True,'no_pending_activities':True,'developmental_exposure_hook':True,
 'scope':'Combined two-caregiver integration; model-only paths skipped; no birth in this fixture.'})
assert all(r['exit_code']==0 for r in read(Path('work/fresh-regression-results.json')))
old=read(b/'final-engineering-verification.json');assert old['named_checks'] in (161,183,185)
if not (b/'pre-household-verification.json').exists():write(b/'pre-household-verification.json',old)
v=read(b/'pre-household-verification.json')
check=read(b/'household-engineering-checks.json');assert check['passed']
v['scripts'].append({'script':'check_household.py','checks':len(check['checks']),'passed':True,'scope':check['scope']})
v['named_checks']=sum(r['checks'] for r in v['scripts']);assert v['named_checks']==185
core=read(b/'household-core-check/engineering-checks.json');assert core['passed']
v['core_demo']={'passed':True,'checks':len(core['checks']),'path':'household-core-check/engineering-checks.json'}
files=list(b.rglob('*.py'))+[b.parent/'identity_state_prototype.py',b.parent/'profile_population_v1.py',b.parent/'profile_population_v1_model.json']
v['source_sha256']={str(path.resolve()):sha256(path.read_bytes()).hexdigest() for path in files}
v['verified_utc']=datetime.now(timezone.utc).isoformat();v['latest_phase']='household-verification.json'
v['live_integrity'].append('household-live/run/integrity-checks.json');write(b/'final-engineering-verification.json',v)
write(b/'household-verification.json',{'passed':True,'verified_utc':v['verified_utc'],'suites':13,'named_checks':185,
 'core_checks':12,'new_checks':check,'actual_27b':integrity,'combined_scripted':read(b/'household-lifetime-final/integrity-checks.json'),
 'mirofish_reference_commit':'7657031ac01184afe2cb220f5ee3545573b5e843','new_paid_dependencies':False,
 'source_version_boundary':version_note,'scope':'Engineering integration only; comparative human prediction remains untested.'})
transcript=['# Actual local 27B household conversation','','Synthetic initialized family fixture. These are agent utterances, not verified world facts.','']
for t,a in zip(turns,e.state['actions']):
 transcript += [f"**{e.state['entities'][t['speaker']]['name']}** — day {t['day']:.8f}; heard by Alex, Maya and Bea:",
                '',a['decision']['speech'],'']
transcript+=['Noor was in a closed bedroom and received none of these turns.','',
             'The generated history/biology subjects and Friday deadline were not supplied as canonical facts. They remain unverified utterances; this run demonstrates coherent reply/routing, not faithful factual recall.']
(b/'household-live/transcript.md').write_text('\n'.join(transcript)+'\n')
print(json.dumps({'named_checks':185,'core_checks':12,'live_turns':4,'requests':len(rows),'repairs':integrity['repairs'],'source_version_note':version_note},indent=2))
