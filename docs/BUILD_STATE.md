# Build state

Updated 16 October 2026 (environment and authoring-gaps phase). This is the single current status file. Earlier milestone sections, with their original counts and wording, are in [the build-state log](history/BUILD_STATE-log.md) and the other [history documents](history/README.md). Where they disagree with this file or [the source-to-code audit](source-to-code-audit.md), this file and the audit win.

## Latest phase: environment, event-driven authoring, in-scenario interviews, cache compaction

This phase closes the remaining software gaps listed after the cockpit:
- **Environment** ([guide](ENVIRONMENT_IMPLEMENTATION.md)): places beyond home, timed `routes` (commutes with in-transit periods), `groups` for institutions and clubs with recurring meetings, written `channels`, and `invitations` whose acceptance is a committed membership fact.
- **Authoring** ([guide](AUTHORING_IMPLEMENTATION.md)): starting facts, intervention `sets_facts`, situation `requires_facts` (a situation can follow an event or an earlier choice), option effects (facts, relationship roles, conversations), the full environment vocabulary, a reachability check for required facts, and a model review of each draft against its setting that must cite real fields. Draft repairs now return the previous draft. The daily rate cap is 365.
- **Interviews inside scenarios** ([interviews](INTERVIEW_IMPLEMENTATION.md)): scheduled in policy, started by an agent's option, taking simulated time on both calendars, and overheard from audible rooms.
- **Graphiti cache compaction** ([setup](../services/graphiti-local/README.md#cache-compaction)): lease-aware deletion of superseded view caches, a stats endpoint, automatic compaction every 25 indexed views. On this machine it cut Neo4j from 1,855 to 203 nodes.

Verification: all 18 suites ran here, 241 named checks plus 12 core checks, including Graphiti ([manifest](../runs/verification/environment-verification.json)). The new and changed suites are:
- `environment`: 9 checks, 5 mutations caught
- `author`: 13 checks, 3 fact-gating mutations caught
- `graphiti`: 16 checks, 3 compaction mutations caught

**Live 27B evidence for the environment and extended authoring is in progress.** Two drafts of an environment-rich setting used the full vocabulary but failed validation (a rate cap set too low, then a 0-year horizon and an overnight availability window). Those led to the clearer vocabulary, an actionable overnight-window error and repairs that keep the previous draft.

## Previous phase: researcher cockpit

[Cockpit implementation](COCKPIT_IMPLEMENTATION.md) adds `devsim/cockpit.py`, a local web view of a run built with only the standard library. An **agent perspective** shows one person's current mood, goals and plans, relationships, calendar, own actions and outcomes, and the memories accessible to them now (gist only when faded). It is built only from what that person received. A labeled **researcher view** shows the model-call timeline and every raw event and action. It can write a static HTML file, or `--serve` a loopback page that polls the run and streams the timeline while a live run is in progress.

- **Checks:** 7 new named checks covering read-only loading, perspective isolation, gist-only faded memories, script-safe embedding, the pre-checkpoint live timeline and the loopback-only server ([results](../checks/results/cockpit-engineering-checks.json)). Five deliberate mutations each fail the suite.
- **Browser:** the static cockpit of the authored Graphiti run rendered in headless Chromium in light and dark themes at 1280 and 390 px with no script errors or overflow. A browser-driven live test streamed new calls and switched to full views when the checkpoint appeared ([evidence](../runs/live/cockpit-live/README.md)).
- **Not yet:** mood history, recall reconstructed at earlier days, mid-run agent state (`run_live` saves at the end), a staged setup wizard and side-by-side run comparison.

## Earlier phase: evidence-linked reports

[Report implementation](REPORT_IMPLEMENTATION.md) adds `devsim/report.py`. Deterministic, read-only **tools** turn a checkpoint into numbered evidence items: observed outcomes (controller events, resolved actions, utterances labeled unverified, state changes since the initial world) and agent interpretations (current memory meanings and prior versions, optional Graphiti searches). The local model then **outlines** sections and **writes** typed claims (observed, agent interpretation, researcher inference). Each claim must cite evidence of the matching category or it is repaired or rejected. `report.md` labels every claim and keeps the executed tool results in a separate appendix.

- **Checks:** 9 new named checks, including read-only tools, category assignment, citation discipline, repair, rendering separation and logging graph failures as tool errors ([results](../checks/results/report-engineering-checks.json)). Four deliberate mutations each fail the suite.
- **Actual HauhauCS 27B:** a report on the authored scenario's Graphiti run, with 5 calls, no repairs, 65 evidence items and 23 claims. Unprompted, it flagged the day-5 club claim that contradicts the day-10 invitation ([evidence](../runs/live/report-live/README.md)).
- **Not yet:** deterministic contradiction detection, cross-run or cross-seed comparison, reconstructing what someone knew at an earlier time, and paging for runs with more evidence than the 8192-token context allows.

## Earlier phase: scenario authoring

[Authoring implementation](AUTHORING_IMPLEMENTATION.md) adds `devsim/author.py`. The local model **drafts** a `scenario.json` from a plain-language setting in a small supported vocabulary (people, household, recurring situations, interventions, assumptions); the draft is accepted only if it compiles, with field-named repair feedback. The researcher reviews it, then a deterministic **compile** step (no model) builds `initial.json`, `policy.json` and `assumptions.json` (every generated number with its path, the compiler defaults and the stated assumptions) and dry-runs the policy with the scripted provider.

- **Checks:** 9 new named checks: compiled people/caregivers/goals/facets, background as labeled private day-0 experience, intervention recipients, the assumptions report, the dry run, determinism, resume from the saved world, a 19-case field-named rejection table, and model-draft repair ([results](../checks/results/author-engineering-checks.json)). Three deliberate mutations each fail the suite.
- **Actual HauhauCS 27B:** the draft compiled after one field-named repair (2 calls, 218 s). Review found a pre-written outcome, a testimony with no person as its source (the compiler now rejects this) and a routine contradicting the setting. The reviewed spec dry-ran for 58 days: 8 resolved actions, nothing pending. A live run with Graphiti recall made 45 calls with 8 graph recalls, no fallback and no repairs; Priya claimed a club meeting before her invitation, seeded by an authored outcome text that mentions the club and can fire early; the speech stayed an unverified utterance ([evidence](../runs/live/author-live/README.md)).
- **Graphiti on the cluster machine:** installed without Docker or root (Neo4j 5.26.32 tarball, JRE 21, pinned Python 3.12 lock); `start.py` gained `--llm-url` and a local-Neo4j path ([setup](../services/graphiti-local/README.md)). `check_graphiti` now runs here.
- **Not yet:** situations triggered by interventions, an effects vocabulary, institutions/groups/channels, checking a draft against its setting.

## Earlier phase: agent interviews

[Interview implementation](INTERVIEW_IMPLEMENTATION.md) adds `devsim/interview.py` with two explicitly separate modes. A **diagnostic** interview questions a frozen copy of the world, in batches of agents × questions, and leaves the run unchanged (checked by state hash). An **in-world** interview is an explicit intervention: a committed identity asks in person, each question is an appraised received event, each reply a committed action, and the result is a new checkpoint. Answers in both modes are labeled generated accounts, not access to true causes.

- **Checks:** 14 new named checks, including information isolation, frozen diagnostics, atomic rollback, id reuse, eligibility, JSON/SQLite restoration and resume under the archived policy ([results](../checks/results/interview-engineering-checks.json)).
- **Actual HauhauCS 27B:** a batch diagnostic of the household scene (4 agents × 2 questions, 8 calls) in which the closed-room agent reported no memory of the conversation, and an in-world interview of Alex by Maya (2 questions, 14 calls) that reached only them and changed no world facts ([evidence](../runs/live/interview-live/README.md)). Graphiti was unavailable on this machine, so recall used the recorded private full-text fallback.
- **Not yet:** interviews scheduled inside scenario policies, agent-initiated interviews, time cost and overhearing for in-world interviews.

## Earlier phase: household environment and conversation

[Household implementation](HOUSEHOLD_IMPLEMENTATION.md) is the newest layer. It adds explicit rooms and audibility, private multi-turn conversation, waking windows and response intervals, and elapsed calendar reservations. These connect to the existing scheduler, memory/mood and optional cognition/development paths. Use `python3 -m devsim.household_example` for a short scene or `python3 -m devsim.simulate --household` for fresh combined policies. Archived policies keep their original behavior.

- **Recorded verification:** 13 suites, **185 named checks plus 12 core checks**, including 24 household checks ([manifest](../runs/verification/household-verification.json)).
- **Actual HauhauCS 27B scene:** four independent turns, 23 calls, no Graphiti fallback; a closed-room person received none of it ([summary](../runs/live/household-live/run/summary.json), [transcript](../runs/live/household-live/transcript.md)).
- **Seven-year scripted combined run:** 61 resolved actions including 16 conversation turns, six agents, matching restored checkpoints ([integrity](../runs/scripted/household-lifetime-final/integrity-checks.json)).
- **Source-version boundary:** optional crystallization and sample-clock refinements are locally checked; the preserved live trace precedes them.

These are engineering results, not measured human fidelity. Scenario authoring, reports and a researcher cockpit have since been implemented.

## Implementation map

| Layer | Implementation | Remaining limit |
|---|---|---|
| Personality, mood, private memory, provenance | `devsim/engine.py`, `personality.py`, `identity_state_prototype.py`, `expression.py`, `references.py` | Facet-to-behavior language and coefficients are provisional. |
| Situational variability | `situation.py` (CAPS-style signatures, construal, bounded temporary offsets; infant sensory triggers) | Domain modifiers and recovery half-life are assumptions. |
| Development, attachment, inheritance | `development.py`, `temperament.py`, `profile_population_v1.py` | Adult-to-child extrapolation is labeled; no child norms. |
| Semantic recall, gist-only access, interference | `cognition.views` / `semantic_recall`, `retrieval.py`, local Graphiti/Neo4j/BGE retrieval (`graphiti_bridge.py`, `graphiti_service.py`, `graph_tools.py`) with explicit private-FTS fallback | Retrieval is bounded and not guaranteed exhaustive; thresholds are provisional. |
| Evidence-based reinterpretation and self-narrative | `cognition.reflect`: retain/defer/revise with received evidence, preserved originals/versions | Evidence-ID validity does not prove semantic correctness. |
| Autonomous recall, planning, budgets, habits | `cognition.ruminate`, `calendar_time.py`, `life_policy.py`, `goal_plans.py` (ordered action-bound steps, received-outcome completion) | Action libraries and progress amounts remain controller-authored. |
| Families, histories, social questions | Parent-first/inherited initialization, lazy activation, `biography.py`, `society.py` | Generated prose has no unrestricted coherence guarantee. |
| World transitions, births, newborn opportunities | `life_policy.apply_effects`, `lifetime.py` world/hazard queues and birth registration | Explicit scenario processes, not calibrated demography or economics. |
| Household rooms and dialogue | `household.py`, `calendar_time.py`, `lifetime.py` queues | Topics, placements and latencies are scenario assumptions; spoken claims are not verified facts. |
| Places, groups, channels, invitations | `household.py` routes/groups/channels/invitations; `lifetime.py` `trip`/`group`/`invite` queue events | Fixed travel times and meeting intervals; membership only grows through invitations; no transport, capacity or weekday model. |
| Researcher interviews | `interview.py`: frozen diagnostic copies and in-world interviews; household conversations in interview mode (scheduled, agent-initiated, timed, overheard) | Answers are generated accounts; questions are fixed in advance with no follow-ups. |
| Scenario authoring | `author.py`: model draft, field-cited model review against the setting, deterministic validated compile with fact gating, effects and environment, assumptions report, scripted dry run | Review is advisory; reachability does not guarantee timing; trust, closeness and resources are not authored. |
| Evidence-linked reports | `report.py`: read-only evidence tools, model outline and sections with typed, category-checked citations, separated rendering | Claims are checked for citation type, not truth; contradictions are found by the model; one checkpoint per report. |
| Researcher cockpit | `cockpit.py`: agent perspectives (accessible memories, mood, goals/plans, relationships, calendar, own actions) and a labeled researcher view; static HTML or loopback live polling | No mood history or past-day recall reconstruction; live view streams calls, not mid-run state. |
| Storage | JSON and SQLite checkpoints (`graph_store.py`); Graphiti index is derived, not canonical, with lease-aware compaction | The embedding cache is not compacted; no population-scale profiling. |

`devsim/lifetime.py` is the scheduler that ties these together; `devsim/full_scenario.py` builds the combined policy that `simulate.py` launches.

## Verification

Run every suite and the core demo from the repository root:

```sh
python3 -m checks.run_all            # add --skip graphiti without the local Graphiti service
```

**Cockpit phase (16 October 2026):** all 17 suites ran here with 224 named checks, including the 7 new cockpit checks and `check_graphiti`; all 12 core checks passed ([manifest](../runs/verification/cockpit-verification.json)).

**Report agent phase (16 October 2026):** all 16 suites ran here with 217 named checks, including the 9 new report checks and `check_graphiti`; all 12 core checks passed ([manifest](../runs/verification/report-verification.json)).

**Scenario authoring phase (16 October 2026):** all 15 suites ran here with 208 named checks, including the 9 new authoring checks and `check_graphiti` against the newly installed local service; all 12 core checks passed ([manifest](../runs/verification/author-verification.json)).

**Interview phase (16 October 2026):** 13 suites ran with 187 named checks, including the 14 new interview checks, and all 12 core checks passed. `check_graphiti` was not run because the Graphiti service is not configured on this machine; with its last recorded 12 checks, 14 suites now record 199 named checks ([manifest](../runs/verification/interview-verification.json)).

**Restructure re-verification (16 October 2026).** After moving the code into the `devsim` package:

- 12 suites passed with 173 named checks, and the core demo passed all 12 core checks. The regenerated `checks/results/*.json` match the committed results exactly.
- `check_graphiti` needs the local Graphiti service, which is not configured on the machine where the restructure ran (`work/graphiti-data/service.json` is missing). It failed the same way before and after the move. Its last recorded pass (12 checks) remains in `checks/results/graphiti-engineering-checks.json`.
- A three-year scripted household simulation produced byte-identical `world.json`, `summary.json`, `policy.json` and `initial.json` before and after the move. So did the sampled demo, `initialize_life --integrated --inherited` and the scripted household scene.
- The live launcher was wiring-checked only: the `run_live` child process starts and stops at the unreachable model API. No actual-model run was repeated.

## Key evidence runs

All recorded runs live under [`runs/`](../runs/README.md). Their contents are unmodified, so internal paths refer to the pre-restructure layout.

| Run | What it shows |
|---|---|
| [`runs/live/cockpit-live`](../runs/live/cockpit-live/README.md) | Static cockpit of the authored Graphiti run, browser screenshots and the live-mode test (above). |
| [`runs/live/report-live`](../runs/live/report-live/README.md) | 27B report on the authored scenario's Graphiti run (above). |
| [`runs/live/author-live`](../runs/live/author-live/README.md) | Live 27B scenario draft, the human review edits, the compiled result, and live runs of it without and with Graphiti recall (above). |
| [`runs/live/interview-live`](../runs/live/interview-live/README.md) | Batch diagnostic and in-world interviews of the household scene with the 27B model (above). |
| [`runs/live/household-live`](../runs/live/household-live/run/summary.json) | Household dialogue with the 27B model (above). |
| [`runs/live/graphiti-live/run-verified`](../runs/live/graphiti-live/run-verified/integrity-checks.json) | Five calls and one action with graph-based recall, no fallback, privacy preserved, JSON/SQLite restoration matched. |
| [`runs/live/goal-plans-success-live`](../runs/live/goal-plans-success-live/run/summary.json), [`goal-plans-live`](../runs/live/goal-plans-live/run/summary.json) | Controlled fixture completing two outcome-linked plan steps; default-policy failure left its goal unfinished and requested replanning. |
| [`runs/live/full-build-live`](../runs/live/full-build-live/run/integrity-checks.json), [`full-build-infant-live`](../runs/live/full-build-infant-live/run/integrity-checks.json) | Seeded adult (18 calls, two actions) and infant (17 calls, two actions, two safe output repairs) fixtures. |
| [`runs/scripted/full-lifespan-final`](../runs/scripted/full-lifespan-final/integrity-checks.json) | 85-year scripted lifecycle: 209 resolved actions, a new generation, three deaths. |
| [`runs/live/development-lifetime-live`](../runs/live/development-lifetime-live/report.md) | Birth-to-22 developmental scenario completed across a resume (31 resolved actions). |
| [`runs/live/integrated-live-example`](../runs/live/integrated-live-example/report.md) | Short integrated fixture: semantic recall, biography slots and evidence-linked reinterpretation. |

Scripted runs skip model-only cognition. Short seeded live fixtures do not exercise every branch and are not full live lifespans.

## Remaining scope

The accepted software paths exist. Empirical coefficients, child norms, instrument/TGA mapping, semantic truth and consistency of generated prose, population/economic/clinical calibration, and Graphiti performance at population scale remain open (lease-aware compaction exists; it is not profiled at that scale). Comparative evaluation is paused until the integrated system is complete. See [the source-to-code audit](source-to-code-audit.md) for mechanism-level status and [RESUME.md](RESUME.md) for checkpoints and reconnecting to the model server.
