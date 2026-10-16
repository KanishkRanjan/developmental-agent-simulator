from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json,sys
sys.path.insert(0,'outputs/agent_engine')
from engine import Engine
b=Path('outputs/agent_engine')
def read(p):return json.loads(p.read_text())
def write(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
m=b/'final-engineering-verification.json';old=read(m)
if not (b/'pre-goal-plans-verification.json').exists():write(b/'pre-goal-plans-verification.json',old)
assert all(r['exit_code']==0 for r in read(Path('work/fresh-regression-results.json')))
new=read(b/'goal-plans-engineering-checks.json');assert new['passed']
v=read(b/'pre-goal-plans-verification.json');v['scripts'].append({'script':'check_goal_plans.py','passed':True,'checks':len(new['checks']),'scope':new['scope']})
v['named_checks']=sum(s['checks'] for s in v['scripts'])
core=read(b/'goal-plans-core-test/engineering-checks.json');assert core['passed'];v['core_demo']={'passed':True,'checks':len(core['checks']),'path':'goal-plans-core-test/engineering-checks.json'}
sources=list(b.glob('*.py'))+[b.parent/'identity_state_prototype.py',b.parent/'profile_population_v1.py',b.parent/'profile_population_v1_model.json']
v['source_sha256']={str(p.resolve()):sha256(p.read_bytes()).hexdigest() for p in sources};v['verified_utc']=datetime.now(timezone.utc).isoformat()
p=b/'goal-plans-scripted-final';s=read(p/'summary.json');assert s['status']=='completed'
e=Engine.load(p/'world.json');assert Engine.load(p/'world.sqlite').state==e.state
assert not e.state['runtime']['pending_activities']
plans=[g for a in e.state['agents'].values() for g in a['goals'].values() if 'execution_plan' in g]
assert plans and any(any(t['status']=='completed' for t in g['execution_plan']['steps']) for g in plans)
report={'verified_utc':v['verified_utc'],'passed_local_checks':True,'named_checks':v['named_checks'],'new_plan_checks':len(new['checks']),
 'scripted_scenario':s,'goals_with_execution_ledgers':len(plans),'json_sqlite_equivalence':True,
 'actual_27b_new_layer':'pending: SSH master absent, API unreachable, automatic reconnection failed; user asked to reconnect',
 'prior_live_traces':'Historical traces cover earlier core layers; none establishes that the new plan layer ran on 27B.',
 'scope':'bounded execution of intentions using controller-authored actions and progress rules, not validated unrestricted planning',
 'source_sha256':v['source_sha256']}
write(b/'goal-plans-verification.json',report);v['latest_phase']='goal-plans-verification.json';write(m,v)
note='''
## Current phase and the five previously listed gaps

Read [CURRENT_STATUS.md](CURRENT_STATUS.md). All five categories—semantic/gist/interference recall; evidence-based reinterpretation/narrative; autonomous recall/planning/budgets/habits; constrained families/history/questions; world transitions/births/newborn opportunities—have connected implementations. Older missing-work lists below are historical.

The next phase adds `goal_plans.py`: ordered action-bound steps, received-outcome completion, archived replans, stale-binding protection and no progress for merely writing an intention. New combined policies enable `planning.grounded_plans`; archived policies remain unchanged. Eleven suites now pass **149 checks plus twelve core checks**, and a fresh three-year scripted run completed 28 resolved actions. [Evidence](goal-plans-verification.json) distinguishes local/scripted tests from the **new layer's pending 27B test**: the SSH master and API forward closed and automatic reconnection failed. Earlier live traces do not verify this new layer.
'''
for name in ['BUILD_STATE.md','source-to-code-audit.md','RESUME.md','FULL_BUILD_STATE.md','REVIEW_LATER.md']:
 p=b/name;s=p.read_text();title,body=s.split('\n',1);p.write_text(title+'\n'+note+'\n'+body)
p=Path('outputs/START_HERE.md');s=p.read_text().replace('## Latest verification','## Current implementation map\n\n[CURRENT_STATUS.md](agent_engine/CURRENT_STATUS.md) is the current five-layer map and executable-planning phase status. All five formerly missing categories now exist. The newest layer has 149 local checks plus twelve core checks; its 27B check awaits reconnection.\n\n## Latest verification',1);p.write_text(s)
print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
