import json,sys
from pathlib import Path
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
from engine import Engine
base=Path('outputs/agent_engine/development-lifetime-live')
e=Engine.load(base/'continued-run/world.json'); previous=Engine.load(base/'run/world.json')
s=e.state; a=e.agent('alex')
records=[json.loads(line) for line in (base/'continued-run/requests.jsonl').read_text().splitlines()]
assert e.day==8035.5 and len(s['actions'])==31
assert all(x['status']=='resolved' for x in s['actions'])
assert s['actions'][:27]==previous.state['actions']
assert len(a['caps_versions'])==1 and a['caps_provenance']['stage']==2
assert len([r for r in records if r['purpose']=='action'])==4
assert not any('facets_percentiles' in r['context'] or 'facets' in r['context'] for r in records)
assert all(r['context'].get('context_view',{}).get('original_records_preserved') for r in records)
assert a['goals']['community-presentation']['status']=='completed'
assert s['runtime']['policy_fingerprint']==previous.state['runtime']['policy_fingerprint']
result={'status':'age22_scenario_completed','passed':True,'checkpoint':'continued-run/world.json','last_saved_age_years':22.0,'last_saved_day':e.day,'resolved_actions':len(s['actions']),'new_actions':4,'observations_by_agent':{k:len(v['memory_meta']) for k,v in s['agents'].items()},'caregiving_episodes':len(a['caregiving_experiences']),'gists_by_agent':{k:len(v['beliefs']) for k,v in s['agents'].items()},'recall_events':sum(len(v['recall_log']) for v in s['agents'].values()),'output_repair_requests':3,'continuation_output_repair_requests':sum('output_repair' in r['context'] for r in records),'current_goal':a['goals']['community-presentation'],'checkpoint_restored':True,'prior_actions_preserved':True,'archived_policy_preserved':True,'age22_completed':True,'archived_signature_versions':len(a['caps_versions']),'refreshed_signature_stage':a['caps_provenance']['stage'],'continuation_requests':len(records),'token_budget_guard_live':True,'overflow_reduction_branch_live':False,'scope':'limited archived three-phase scenario; first events start at age five; independent caregiver replies verified separately; token guard ran but no overflow reduction was needed; no comparative predictive validation','connection_after_completion':'SSH socket disappeared again after successful final save; separate caregiver-role probe could not connect'}
for target in [base/'checkpoint-status.json',base/'continued-run/integrity-checks.json']:
 target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
