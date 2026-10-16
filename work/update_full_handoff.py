from pathlib import Path
b=Path('outputs/agent_engine')
p=Path('outputs/START_HERE.md');s=p.read_text();a=s.index('The latest extension is');z=s.index('\n\n1.',a)
s=s[:a]+'''The latest software pass is [Full build state](agent_engine/FULL_BUILD_STATE.md); the [review-later guide](agent_engine/REVIEW_LATER.md) has the one-command launcher and evidence. Earlier integrated/developmental notes retain their historical scope.''' +s[z:]
a=s.index('## Current scope');z=s.index('## Continuing safely',a)
s=s[:a]+'''## Current scope

The accepted developmental-engine layers now have connected software paths, including full available-corpus indexed retrieval, ambiguous references and heard reminders, open-value structured biographies, actual elapsed activities, configurable temporary variability/cultural expression, self-set goal opportunities, conserved transfers, exogenous hazards, newborn opportunities/hazards and SQLite provenance/checkpoint storage. `simulate.py` initializes and runs the combined policy from infancy onward. It uses the existing local HauhauCS 27B, with no smaller fallback.

Ten check suites (136 named checks) and the twelve-check core demo pass. An 85-year scripted lifecycle completed with 209 resolved actions and a new generation. Separate adult and infant 27B fixtures completed. [Full build state](agent_engine/FULL_BUILD_STATE.md) distinguishes provider/fixture/source versions and gives exact evidence. These are implementation checks, not human-realism or predictive-improvement results.

Empirical coefficients, child norms, instrument/TGA mapping and learned psychological/cultural/economic laws remain research boundaries. Structured chronology is implemented; unrestricted semantic consistency is not guaranteed. Do not claim a fitted clinical simulator, missing research report or every scientific proposal has been validated. User choices and source uncertainty remain authoritative.

''' +s[z:];p.write_text(s)
p=b/'BUILD_STATE.md';s=p.read_text();s=s.replace('## Latest authoritative status: integrated policy extension','## Historical integrated policy extension',1);i=s.index('## Historical integrated policy extension')
s=s[:i]+'''## Latest authoritative status: full software pass

Read [FULL_BUILD_STATE.md](FULL_BUILD_STATE.md) and [REVIEW_LATER.md](REVIEW_LATER.md). The combined entry point is now `simulate.py`, with `full_scenario.py` for initialization/policy. Open structured biographies, whole available-corpus search, ambiguous references/reminders, actual elapsed activities, configurable variation/culture, new-goal scheduling, conserved transfers, world/newborn hazards and SQLite provenance are connected to the earlier integrated layers.

**Verified:** ten suites, 136 named checks plus the twelve-check core demo. The final 85-year scripted lifecycle has 209 resolved actions, five retained agents including one new child, three deaths, ten dynamic opportunities and three newborn hazards, with identical restored JSON/SQLite state. The adult 27B fixture completed eighteen calls/two actions; the infant fixture completed seventeen calls/two actions, including two safe output repairs. Detailed status, source-version boundaries and remaining scientific assumptions are in the full-build handoff. Neither a full live lifespan nor human predictive improvement is claimed.

All earlier notes below are historical. This section and the coverage audit supersede their missing-implementation lists; empirical/instrument uncertainty and user exclusions remain in force.

''' +s[i:];p.write_text(s)
p=b/'README.md';s=p.read_text();i=s.index('**Current status:**');j=s.index('\n',i)
s=s[:i]+'''**Current entry point:** [Review later](REVIEW_LATER.md), [full build state](FULL_BUILD_STATE.md), and `simulate.py`. The accepted engine layers now include indexed recall, open histories, reference resolution, elapsed activities, state variability/culture, autonomous goal opportunities, world/newborn hazards and JSON/SQLite persistence. Ten suites pass (136 checks), plus the core demo; separate 27B adult/infant runs and an 85-year scripted lifecycle are saved. Scientific calibration and predictive validity remain unresolved.''' +s[j:];p.write_text(s)
for name in ('integrated-build-notes.md','development-notes.md'):
 p=b/name;s=p.read_text();idx=s.index('\n\n');s=s[:idx]+'''\n\n**Newer handoff:** [FULL_BUILD_STATE.md](FULL_BUILD_STATE.md) and [REVIEW_LATER.md](REVIEW_LATER.md) supersede older missing-software lists below. These notes retain their original equations, assumptions and historical evidence.''' +s[idx:];p.write_text(s)
p=b/'sources/README.md';s=p.read_text();s+='''\n## Full software pass\n\n[FULL_BUILD_STATE.md](../FULL_BUILD_STATE.md) maps the newly connected indexing, open histories, identity binding, elapsed activities, temporary variation/culture, goal/hazard/generation policies and SQLite provenance. [Review later](../REVIEW_LATER.md) is the current executable entry point. These implementations preserve the source/user boundaries; new default coefficients are scenario choices. They do not supply missing TGA/child norms or a missing broader/clinical research report.\n''';p.write_text(s)
p=b/'RESUME.md';s=p.read_text();idx=s.index('## Latest build and checkpoints');end=s.index('## Reconnect',idx)
s=s[:idx]+'''## Latest build and checkpoints

Read [FULL_BUILD_STATE.md](FULL_BUILD_STATE.md) and [REVIEW_LATER.md](REVIEW_LATER.md). `simulate.py` is the combined launcher. Ten suites pass (136 named checks), plus the core demo.

- [Adult 27B final world](full-build-live/run/world.json), [policy](full-build-live/run/policy-used.json), [integrity](full-build-live/run/integrity-checks.json): two resolved actions, eighteen calls, open biographies/indexed recall/elapsed completion. This is a seeded age-18 fixture.
- [Infant 27B final world](full-build-infant-live/run/world.json), [policy](full-build-infant-live/run/policy-used.json), [integrity](full-build-infant-live/run/integrity-checks.json): two resolved actions, seventeen calls, nonverbal infant behavior and independently delayed care; two exact-mention output repairs. JSON/SQLite worlds both restore.
- [85-year scripted final world](full-lifespan-final/world.json), [policy](full-lifespan-final/policy.json), [integrity](full-lifespan-final/integrity-checks.json): 209 resolved actions, a new generation, three deaths. Scripted provider skips model-only paths.

Earlier `integrated-live-example` and `development-lifetime-live` runs remain archived with their own policies. Do not replace policy fingerprints to enable newer features on them. For a new complete combined scenario, use the launcher and a fresh output directory. For a resume, use the corresponding checkpoint/provider/archived policy and a fresh run output directory. No inference client from this work is still running.

## Remaining research scope

The accepted software paths now exist; scientific coefficients, child norms, instrument mapping, semantic truth/consistency and population/clinical calibration remain unresolved. Graph persistence is SQLite; no Neo4j service or additional embedding model was installed. Comparative evaluation remains paused. Exact live/local/source-version boundaries are in the full-build state.

''' +s[end:];p.write_text(s)
