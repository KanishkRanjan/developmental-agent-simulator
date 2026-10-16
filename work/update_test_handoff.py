from pathlib import Path
import json
b=Path('outputs/agent_engine');r=json.loads((b/'fresh-integration-verification.json').read_text())
lines=['# Fresh integrated test results','', '16 October 2026. Software correctness and integration checks; comparative evaluation remains deferred.','',
'**139 regression checks and the twelve-check core demo passed.** Testing found and repaired an upstream infant-capability gap.','',
'The old action selector enforced empty infant speech/plans, but generated situational rules could still describe riddles and complex challenges. Infant rule generation now chooses bounded sensory triggers and nonverbal reactions; shared context carries capability constraints, and generated rules refresh at ages two and five. These are explicit scenario constraints, not validated developmental norms.','',
'A first replay returned the wrong root JSON key three times. The controller rejected it and rolled the event back before committing an action or rules. The prompt now gives the required root shape and the validator reports the missing key precisely. The corrected fresh replay completed. Failed evidence remains in `fixed-infant-test/run`.','',
'| Test | Result |','|---|---|']
for name,info in r['live_runs'].items():
 lines.append(f"| {name} | {info['new_actions']} new resolved actions; {info['requests']} model requests; {info['repairs']} repairs; checkpoint restored identically from JSON/SQLite. |")
lines+=['| Fresh 100-year scripted scenario | 165 resolved actions, six retained agents, six deaths, no pending activities; JSON/SQLite identical. This seed produced no new birth; the earlier 85-year fixture covers new-generation scheduling. |','',
'The adult continuation selected earlier encounters through indexed query expansion/semantic recall, received independent replies, and revised interpretations after the outcome. Earlier actions and original observations were preserved. The final infant replay checked bounded rules, empty speech/plans, received interactions and elapsed outcomes on the actual local HauhauCS 27B.','',
'The scripted lifespan skips model cognition. Short live runs do not establish a complete live lifespan, human realism, or predictive improvement. Broader scope and scientific boundaries remain in the source audit. Traces before the infant correction retain their recorded source hashes; the corrected infant trace uses the final runtime.','',
'[Machine-readable evidence](fresh-integration-verification.json) · [Current verification manifest](final-engineering-verification.json) · [Source audit](source-to-code-audit.md)','']
(b/'LATEST_TEST_REPORT.md').write_text('\n'.join(lines))
note='''
## Latest fresh test and infant correction

See [LATEST_TEST_REPORT.md](LATEST_TEST_REPORT.md) and [fresh-integration-verification.json](fresh-integration-verification.json). The current verification is **139 named regression checks plus twelve core checks**. Fresh actual 27B caregiver/infant runs and a resumed adult memory interaction completed; a second 100-year scripted scenario completed 165 resolved actions with six deaths and no pending activities. This seed did not produce a birth; earlier new-generation evidence remains separate.

Testing exposed infant CAPS rules with adult-like cognitive challenges despite nonverbal action constraints. `situation.py` now provides bounded infant sensory triggers/nonverbal reactions, `engine.py` supplies capability context and refreshes generated rules at ages two/five. A wrong-root JSON response failed safely; explicit schema/repair feedback fixed the replay. Final regression and corrected infant evidence are recorded with source hashes. These checks establish runnable behavior, not human validity or full scientific coverage. Earlier counts/traces below are historical.
'''
for file in ['BUILD_STATE.md','FULL_BUILD_STATE.md','RESUME.md','source-to-code-audit.md','development-notes.md','REVIEW_LATER.md']:
 p=b/file;s=p.read_text();first,rest=s.split('\n',1);p.write_text(first+'\n'+note+'\n'+rest)
p=Path('outputs/START_HERE.md');s=p.read_text();s=s.replace('## Read first','## Latest verification\n\nRead [the fresh test report](agent_engine/LATEST_TEST_REPORT.md): 139 regression checks, twelve core checks, current infant capability fix, fresh 27B traces and a separate 100-year scripted run. Older 136-check milestones below are preserved history.\n\n## Read first',1);p.write_text(s)
p=b/'sources/README.md';p.write_text(p.read_text()+'\n## Infant capability correction\n\n[Latest test report](../LATEST_TEST_REPORT.md) records the observed adult-like infant rule-generation failure and bounded sensory/nonverbal engineering repair. Age-two/five refresh boundaries and catalogs are scenario capability constraints; they are not measured infant norms or a new claim from the research reports.\n')
