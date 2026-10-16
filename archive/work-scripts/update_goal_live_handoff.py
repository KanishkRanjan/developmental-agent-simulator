from pathlib import Path
import json
b=Path('outputs/agent_engine');r=json.loads((b/'goal-plans-verification.json').read_text())
assert r['actual_27b_new_layer']['status']=='completed'
a=r['actual_27b_new_layer']['fixtures']['goal-plans-live'];z=r['actual_27b_new_layer']['fixtures']['goal-plans-success-live']
report=f'''# Plan execution: actual 27B results

16 October 2026. Both fixtures used the existing local HauhauCS 27B and the current checked source files. No implementation changes were necessary during this live test.

| Fixture | Outcome | Requests |
|---|---|---|
| Combined default policy | One resolved action. The task failed, the goal stayed active at progress 0, the bound step remained pending, and replanning was requested. | {a['requests']} total; {a['goal_planning_requests']} plan generation; {a['repair_requests']} repairs. |
| Controlled draft/review | Two resolved actions: draft then review. Both completed steps cite received outcome events; the goal reached progress 1 and completed. | {z['requests']} total; {z['goal_planning_requests']} plan generations; {z['repair_requests']} repairs. |

Both worlds saved/restored identically from JSON and SQLite, retained no pending activities, and recorded outcomes later than their intentions. Runtime source hashes match the verification manifest. Eleven local suites remain at 149 checks, plus twelve core checks.

The success fixture intentionally supplies one eligible action per stage and guarantees successful outcomes. It verifies wiring and prerequisite progression, not personality choice, planning quality or human predictive validity. The default-policy fixture offers alternatives and allows failure. An action binding remains a model judgment within controller-authored scenario actions, costs and progress rules.

[Machine-readable phase evidence](goal-plans-verification.json) · [Default-policy integrity](goal-plans-live/run/integrity-checks.json) · [Success-fixture integrity](goal-plans-success-live/run/integrity-checks.json) · [Current implementation map](CURRENT_STATUS.md)
'''
(b/'GOAL_PLANS_LIVE_REPORT.md').write_text(report)
p=b/'CURRENT_STATUS.md';s=p.read_text().replace('The new goal-execution layer has local/scripted checks; its actual 27B check is pending reconnection.', 'The new goal-execution layer has local/scripted checks and actual 27B failure/success fixtures.')
s+='\n## Actual 27B completion\n\n[Live report](GOAL_PLANS_LIVE_REPORT.md): the default-policy failure left its goal unfinished and requested replanning; the controlled draft/review fixture completed two outcome-linked steps. Both checkpoints restored identically from JSON/SQLite with no pending activities. This short engineering coverage does not establish unrestricted planning quality.\n';p.write_text(s)
for name in ['BUILD_STATE.md','source-to-code-audit.md','RESUME.md','FULL_BUILD_STATE.md','REVIEW_LATER.md']:
 p=b/name;s=p.read_text();s=s.replace('[Evidence](goal-plans-verification.json) distinguishes local/scripted tests from the **new layer\'s pending 27B test**: the SSH master and API forward closed and automatic reconnection failed. Earlier live traces do not verify this new layer.', '[Evidence](goal-plans-verification.json) now includes the completed actual 27B tests: a failed default-policy task stayed unfinished, and a controlled draft/review fixture completed two received-outcome-linked steps. [Live report](GOAL_PLANS_LIVE_REPORT.md) records exact scope, model, source hashes and checkpoint checks. The restored SSH connection and loopback forward worked; no inference job remains running.')
 p.write_text(s)
p=Path('outputs/START_HERE.md');s=p.read_text().replace('The newest layer has 149 local checks plus twelve core checks; its 27B check awaits reconnection.', 'The newest layer has 149 local checks plus twelve core checks and completed actual 27B failure/success tests. See [the live report](agent_engine/GOAL_PLANS_LIVE_REPORT.md).');p.write_text(s)
