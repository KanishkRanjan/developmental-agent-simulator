# Integrated build: cognition, planning, histories and world transitions

## Household continuation, 16 October 2026

[Household implementation](HOUSEHOLD_IMPLEMENTATION.md) documents the new room routing, multi-turn interaction, availability/calendar timing, private observations and optional existing cognition/development hooks. `simulate.py --household` enables it in a fresh combined policy. Latest verification is 185 named checks plus twelve core checks, a four-turn actual 27B fixture and a seven-year scripted combined run. Read the guide for source-version boundaries, commands, explicit assumptions and remaining proposals; older figures below retain their historical scope.

## Latest: local Graphiti and MiroFish-inspired tools

[GRAPHITI_IMPLEMENTATION.md](GRAPHITI_IMPLEMENTATION.md) and [setup guide](../services/graphiti-local/README.md) supersede older “no Graphiti/embedding model” statements below. The engine now has a local Graphiti/Neo4j/BGE retrieval index, durable background outbox, explicit fallback diagnostics and read-only quick/deep/history/chain tools. No Zep Cloud subscription or hosted inference dependency was added.

Twelve suites pass **161 checks plus twelve core checks**. The final actual 27B fixture completed five calls/one action with graph-based recall, no fallback, preserved privacy and matching JSON/SQLite restoration. Durable offline-queue/restart behavior was checked separately. The index is derived from private views, not a new source of world truth; immutable-cache scale and unrestricted extraction/history limitations remain explicit. The graph service/container remain running; language test clients have finished.


**Newer handoff:** [FULL_BUILD_STATE.md](history/FULL_BUILD_STATE.md) and [REVIEW_LATER.md](history/REVIEW_LATER.md) supersede older missing-software lists below. These notes retain their original equations, assumptions and historical evidence.

16 October 2026. This extends the existing developmental engine. It supplies runnable policies for the categories previously missing; it does not establish a complete theory of human behavior. Read this with the source-to-code audit. Earlier age-22 traces retain their historical scope.

## Connected behavior

| Layer | Runtime path | Remaining boundary |
|---|---|---|
| Semantic recall | `Lifetime._before_decision` calls `cognition.semantic_recall`; the local 27B model selects relevant private representations by meaning before construal/action. Actual retrieval produces explicit recall and affect events. | Bounded scan, default 24 candidates, maximum 64. No embedding index. Older high-value memories outside the candidate set may be missed. Omitted count is retained. |
| Detail loss and interference | `Engine.memories` delegates to `cognition.views` when enabled. Related topic associations reduce retrieval accessibility. Below the configured threshold, only an already retained summary or evidence-linked gist is exposed. | This is a deterministic representation policy, not calibrated stochastic forgetting or a complete interference theory. No summary means no invented reconstruction. Immutable original records remain available to the controller for audit, not automatically to the agent. |
| Conditional reinterpretation | After received outcomes, `cognition.reflect` can retain, defer or revise an earlier meaning, citing both old and new received evidence. Revisions preserve prior meanings and original episodes. Deferred cases persist in an exposure queue. | The LLM supplies a qualitative gate; syntax and evidence checks cannot establish its interpretation is psychologically correct. No rejected reconsolidation equations or similarity multipliers were restored. |
| Narrative identity | Reflection can update a subjective self-story with evidence and previous versions; it reaches later action/appraisal context. | Model inference may contain unjustified certainty or narrative embellishment. It cannot write world facts. Not a measured McAdams instrument. |
| Rumination | Autonomous recall events have seeded exponential waiting times. Received memories, mood congruence, salience, refractory periods and habituation affect recall; gist recall cannot reset the original-detail clock. | Declared event-rate policy, not continuous cognition or an empirical rumination model. No background ticks manufacture life events. |
| Plans, goals and habits | Options can target competing existing goals. Duration and costs filter options; resolved outcomes account for hours/resources. Reflection can revise plans. Cue/action familiarity builds on independent days and decays with elapsed time. | Aggregate simulated-day capacity rather than a continuous calendar. Habits influence context without forcing actions. Deadlines are visible for replanning; no automatic assumption that missing one means failure. |
| Family and histories | Necessary new caregivers can be generated before a child's disposition, with separate biological-parent/caregiver lists. Needed-person expansion chooses controller-authored biography alternatives and constrained historical milestones; shared milestone IDs cannot contradict earlier commitments. | Canonical scenario alternatives rather than unrestricted generated biographies. Generated overview prose is explicitly synthetic; only selected canonical slots reach personal context. No retroactive private memories, infinite ancestry or truth-from-testimony. |
| Probing and credibility | Reflection can queue evidence-linked questions about known references, independently of closeness. A question is transmitted only through an actual selected contact. Directly received encounters may update trust and closeness separately, with provenance. | No invented answer or automatic introduction. Ambiguous entity resolution is not implemented. Trust is a subjective expectation, not world-truth verification. |
| World/demographic consequences | Fixed world transitions and action-dependent effects support resources, employment/other mutable facts, joint relationship roles, births, illness/recovery and death. Newborn opportunity templates join the event scheduler and survive resume. | Explicit scenario hazards/outcomes, not fitted demographic rates, market clearing, a comprehensive economy or a clinical model. Income can be exogenous; there is no claim of a closed conserved-money economy. |

`integrated-demo.json` combines the new policies with existing inherited profiles, caregiving, situational expression, age curves and crystallization. Existing archived policies/checkpoints retain the earlier behavior; do not swap a checkpoint's policy to enable new layers.

## Provisional mathematics and constraints

For a memory with current base accessibility `R`, topic fan count `n` and policy weight `w`, the view uses `R / (1 + w*log(1+n))`. This changes retrieval access rather than stored stability or factual validity. Default `w=.15`; detail is available above `.45`. These are engineering choices, not coefficients extracted from the report. Fan association depends on model-generated topic labels.

A gist-only recall may generate bounded affect but never rehearses the original episodic detail. Explicit stored summaries/gists can remain available after the episodic representation becomes inaccessible. This is not a claim of permanent human retention. Semantic recall uses the configured local model rather than silently adding another model/service.

Autonomous recall opportunities use a configured rate per simulated year and independently seeded exponential waiting times. Original cooldown and diminishing-affect rules still apply. The default example uses 12 opportunities/year and a minimum one-day gap. Waiting times persist; checkpoint placement does not resample them. World transitions precede cognition/actions at identical timestamps.

Action hours accumulate in `floor(simulated_day)` buckets; example capacity is 12 hours/day. Resource costs are nonnegative and debits cannot overdraw. Habit familiarity decays as `strength * 2**(-elapsed_days/half_life)`; one daily increment per cue/action combination is allowed, with an explicit maximum. Defaults are 30 days, .1 increment and maximum 1. Trust and closeness model updates are each bounded to an absolute .05 budget per target per simulated day; their source evidence is versioned. None of these numbers is calibrated psychology.

All controller events are transactional. Failed appraisal, semantic selection, background choice, reflection or newborn-template validation rolls back the current event, including identities, world effects, resource/time accounting, histories, habits and dynamic opportunity registration. Earlier completed events remain saved. The run recorder rejects a nonempty output directory and records source hashes for new runs.

## Running the integrated scenario

From the project root, choose fresh directories:

```sh
work/profile-env/bin/python -m devsim.initialize_life \
  --inherited --integrated --save runs/live/NEW_RUN/initial.json
work/profile-env/bin/python -m devsim.run_live \
  --world runs/live/NEW_RUN/initial.json \
  --policy devsim/policies/integrated-demo.json --until-day 8035.5 \
  --out runs/live/NEW_RUN/run --api http://127.0.0.1:18081
```

The user-provided cluster connection/loopback forward must be active. `--scripted` on `lifetime.py` is a separate deterministic engineering provider; it intentionally does not claim model-generated semantic recall/reflection/background expansion. Initial years without supplied opportunities are omitted development, not simulated infancy.

To continue a run, use its saved world and archived `policy-used.json` in a fresh output directory. `new_actions` in a summary is the increment for that invocation. Full counts come from the checkpoint. Newly born agents acquire only the supplied `newborn_opportunities`; no template means no invented subsequent life course. Template strings may contain `$actor` and `$caregiver`; missing caregivers skip caregiver-dependent templates.

## Verification and evidence

`check_extended.py` adds integration checks for representation privacy, qualitative revision and deferral, narrative evidence, semantic selection, budget/habit constraints, automatic questions, history consistency, separate trust/closeness, direct shared transitions, necessary-family generation, births/death and multi-generation checkpoint/rollback behavior. The eight earlier suites and the core demo remain required regression checks. The final verification manifest records nine passing suites, 111 named checks plus the twelve-check core demonstration, with exact source hashes.

`integrated-scripted-example` exercises the combined scenario to age 22 with the deterministic provider. The actual 27B evidence is separate under `integrated-live-example`: a short age-18 fixture with explicitly seeded experiences, not a full-life experiment. The first attempt rejected invalid milestone IDs and preserved prior completed work. The subsequent run completed semantic recall, constrained slot selection, two independent agent decisions and appraisals, and evidence-linked reflection. [Final live report](../runs/live/integrated-live-example/report.md) records four resolved actions, 22 requests across two successful segments and three evidence-linked reinterpretations. The final replay also exercises background context and social reflection under the final runtime source hashes. Check its exact summary and trace for what the model chose. Later additions such as new-generation scheduling and daily social budgets have local checks; a short live trace does not exercise every branch.

## What completion means here

The formerly missing categories now have runtime mechanisms under declared policies. Remaining research/scale work includes empirical calibration, child-specific distributions, instrument/TGA mapping, learned state covariance, high-recall semantic indexing, unconstrained consistent biography generation, ambiguous entity resolution, richer world policies and broader society/clinical extensions. The current build is ready for engineering trials of its integrated behavior; no predictive improvement, human replication or source-complete scientific implementation is claimed.
