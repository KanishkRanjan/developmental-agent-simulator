# Persistent build state

## Latest: household environment and conversation layer

[Household implementation](HOUSEHOLD_IMPLEMENTATION.md) is the newest phase. Explicit rooms/audibility, private multi-turn conversation, waking windows/response intervals and elapsed calendar reservations now connect to the existing scheduler, memory/mood and optional cognition/development paths. Use `household_example.py` for a short scene or `simulate.py --household` for fresh combined policies; archived policies remain unchanged.

Thirteen suites pass **185 named checks plus twelve core checks**, including 24 new household checks. The actual HauhauCS 27B scene completed four independent turns/23 calls with no Graphiti fallback; a closed-room person received none of it. The final seven-year scripted combined run completed 61 actions including 16 conversation turns. [Verification](household-verification.json) and the implementation guide record the source-version boundary: optional crystallization/sample-clock refinements are locally checked, while the preserved live trace precedes them. These are engineering results, not measured human fidelity. Automatic scenario authoring, interviews, report generation and a GUI remain proposed.

Earlier milestone sections below are historical and keep their original scope.

## Latest: local Graphiti and MiroFish-inspired tools

[GRAPHITI_IMPLEMENTATION.md](GRAPHITI_IMPLEMENTATION.md) and [setup guide](graphiti-local/README.md) supersede older “no Graphiti/embedding model” statements below. The engine now has a local Graphiti/Neo4j/BGE retrieval index, durable background outbox, explicit fallback diagnostics and read-only quick/deep/history/chain tools. No Zep Cloud subscription or hosted inference dependency was added.

Twelve suites pass **161 checks plus twelve core checks**. The final actual 27B fixture completed five calls/one action with graph-based recall, no fallback, preserved privacy and matching JSON/SQLite restoration. Durable offline-queue/restart behavior was checked separately. The index is derived from private views, not a new source of world truth; immutable-cache scale and unrestricted extraction/history limitations remain explicit. The graph service/container remain running; language test clients have finished.


## Current phase and the five previously listed gaps

Read [CURRENT_STATUS.md](CURRENT_STATUS.md). All five categories—semantic/gist/interference recall; evidence-based reinterpretation/narrative; autonomous recall/planning/budgets/habits; constrained families/history/questions; world transitions/births/newborn opportunities—have connected implementations. Older missing-work lists below are historical.

The next phase adds `goal_plans.py`: ordered action-bound steps, received-outcome completion, archived replans, stale-binding protection and no progress for merely writing an intention. New combined policies enable `planning.grounded_plans`; archived policies remain unchanged. Eleven suites now pass **149 checks plus twelve core checks**, and a fresh three-year scripted run completed 28 resolved actions. [Evidence](goal-plans-verification.json) now includes the completed actual 27B tests: a failed default-policy task stayed unfinished, and a controlled draft/review fixture completed two received-outcome-linked steps. [Live report](GOAL_PLANS_LIVE_REPORT.md) records exact scope, model, source hashes and checkpoint checks. The restored SSH connection and loopback forward worked; no inference job remains running.


## Latest fresh test and infant correction

See [LATEST_TEST_REPORT.md](LATEST_TEST_REPORT.md) and [fresh-integration-verification.json](fresh-integration-verification.json). The current verification is **139 named regression checks plus twelve core checks**. Fresh actual 27B caregiver/infant runs and a resumed adult memory interaction completed; a second 100-year scripted scenario completed 165 resolved actions with six deaths and no pending activities. This seed did not produce a birth; earlier new-generation evidence remains separate.

Testing exposed infant CAPS rules with adult-like cognitive challenges despite nonverbal action constraints. `situation.py` now provides bounded infant sensory triggers/nonverbal reactions, `engine.py` supplies capability context and refreshes generated rules at ages two/five. A wrong-root JSON response failed safely; explicit schema/repair feedback fixed the replay. Final regression and corrected infant evidence are recorded with source hashes. These checks establish runnable behavior, not human validity or full scientific coverage. Earlier counts/traces below are historical.


Updated 16 October 2026. Read this file with the [complete design inventory](../design-coverage-ledger.md) and [conversation review](../full-conversation-review.md) when continuing work. Those earlier documents describe the research design; they are not implementation completion claims.

## Latest authoritative status: full software pass

Read [FULL_BUILD_STATE.md](FULL_BUILD_STATE.md) and [REVIEW_LATER.md](REVIEW_LATER.md). The combined entry point is now `simulate.py`, with `full_scenario.py` for initialization/policy. Open structured biographies, whole available-corpus search, ambiguous references/reminders, actual elapsed activities, configurable variation/culture, new-goal scheduling, conserved transfers, world/newborn hazards and SQLite provenance are connected to the earlier integrated layers.

**Verified:** ten suites, 136 named checks plus the twelve-check core demo. The final 85-year scripted lifecycle has 209 resolved actions, five retained agents including one new child, three deaths, ten dynamic opportunities and three newborn hazards, with identical restored JSON/SQLite state. The adult 27B fixture completed eighteen calls/two actions; the infant fixture completed seventeen calls/two actions, including two safe output repairs. Detailed status, source-version boundaries and remaining scientific assumptions are in the full-build handoff. Neither a full live lifespan nor human predictive improvement is claimed.

All earlier notes below are historical. This section and the coverage audit supersede their missing-implementation lists; empirical/instrument uncertainty and user exclusions remain in force.

## Historical integrated policy extension

The previously missing mechanism categories now have connected provisional implementations. Read [integrated-build-notes.md](integrated-build-notes.md) and the updated [coverage audit](source-to-code-audit.md) for exact limits. New modules `cognition.py` and `life_policy.py` connect through `engine.py`/`lifetime.py`; `integrated-demo.json` is the combined policy, with `initialize_life.py --integrated --inherited` for its initial goals/resources.

Implemented: bounded local-model semantic selection before decisions; gist-only detail access and topic fan interference; received-evidence retain/defer/revise gates and versioned narrative; event-driven autonomous recall; competing goals with day-level hours/resource constraints; decaying cue/action familiarity; constrained canonical biography/history expansion; actual-contact social questions; independent trust/closeness changes with daily budgets; action-dependent and exogenous world facts/resources, shared relationship transitions, births/illness/death; necessary parent/caregiver context and declared newborn opportunity templates. Transactions and dynamic opportunity streams survive checkpoint/resume. Model-generated prose cannot authorize world facts or fabricate personal historical observations.

Verification is recorded in [final-engineering-verification.json](final-engineering-verification.json): nine passing scripts, 111 named checks, plus the twelve-check core demonstration. The earlier 82-check milestone is preserved in `development-stage-verification.json`. The combined scripted scenario reached age 22 with 50 resolved actions, 42 opportunity steps, three world transitions and 481 scheduled autonomous-recall opportunities. Scripted mode deliberately skips model cognition/background generation; this is engineering evidence, not an actual-model lifetime result.

`integrated-live-example/continued-run` completed a short actual 27B interaction: constrained biography slot selection, semantic recall, two independently chosen actions, two appraisals, two situation interpretations, two signature generations and two reflections (12 requests, 130.714 seconds). The model revised two earlier meanings with received evidence and produced an evolving narrative and plan; the controller recorded two hours and habit evidence. It followed a first attempt whose invalid biography milestone IDs were rejected transactionally. A later reflection probe also exposed a self-targeting ambiguity; the input/prompt was corrected and the failed evidence retained. The corrected final replay completed ten requests in 76.24 seconds with two further resolved actions. Across the two successful segments there are four resolved actions, 22 requests and three memory reinterpretations. [Live report](integrated-live-example/report.md) and [final integrity checks](integrated-live-example/final-continued-run/integrity-checks.json) record restored state, preserved episodes/actions and matching final runtime hashes. This remains a short seeded fixture, not a full live lifespan validation.

Remaining scope is now primarily richness, scale and grounding rather than the complete absence of those mechanism categories: unrestricted coherent histories, high-recall semantic indexing, ambiguous entities, learned state covariance, child norms, TGA/instrument mapping, empirical developmental/hazard coefficients and richer population/economic policies. Wider society/clinical extensions remain separate. This is not full scientific source replication or established human predictive improvement. Earlier notes below are historical and do not supersede this section.

## Historical developmental milestone: source fidelity audit

**Latest live result:** the restored connection served the same HauhauCS 27B model. Resuming the archived age-19 checkpoint completed the scenario at age 22 (day 8035.5), with four additional actions, 31 resolved actions total and the preparation goal at progress 1.0. The continuation made 13 requests in 187.948 seconds, with no output repairs. [Integrity checks](development-lifetime-live/continued-run/integrity-checks.json) confirm prior actions and policy were preserved, the final checkpoint restored, and adult signatures refreshed with the earlier version archived. The actual-token guard ran on all calls; no overflow required adaptive reduction. This is a limited scenario, not a complete lifetime model or predictive validation. The SSH socket disappeared again after the final save, preventing a separate caregiver-role probe; the main run is complete and safe. [RESUME.md](RESUME.md) points to the latest checkpoint.

**Historical developmental verification:** [development-stage-verification.json](development-stage-verification.json) records the earlier eight check scripts (82 named checks) plus the core demo passing, with source hashes. These establish implementation properties, not scientific validation.

**Late refinements:** independent caregiver response choices can influence one shared outcome resolving both actions; formal known caregiving roles reach the caregiver's own context without private child history. Generated signatures can refresh at scenario age stages (12/18/40/65) or sustained baseline drift, archiving earlier versions. Original encoding stability is preserved separately from rehearsed accessibility on resume and rollback. Prompt views can be reduced against actual rendered-token counts while proposal staleness checks retain the canonical agent context. Closed connections become explicit transport failures. These final source hashes are newer than parts of the longer trajectory; preserve each trace's scope.

`interaction-live-example/run` actually completed on the 27B server: eight requests, two independently chosen actions, two appraisals, two signature generations and two situation interpretations, with one shared outcome. The child request was forced for wiring coverage; the caregiver chose between two responses. The separate formal-role context and age-refresh probe remains incomplete because its connection failed. Adult signature refresh is now independently live-verified in the longer continuation; formal-role context and forced adaptive overflow reduction remain locally checked.

### Latest continuation: development, inheritance, activation and model robustness

Read [development-notes.md](development-notes.md) for mechanisms, source references, exact assumptions, commands and actual-model evidence. This section supersedes earlier lists that still call attachment, inherited dispositions, maturity and crystallization entirely missing.

New runtime connections: direct received caregiving -> caregiver-specific working expectations -> action/appraisal context; resolved state-conditioned actions -> independent-day exposure -> bounded lasting facet changes; absolute-age maturation separately from learned changes; optional parent-first latent inheritance with separate biological parents/caregivers; selected-interaction lazy activation of committed identities; bounded-thinning opportunity rates based on resolved action counts, progress or facets. These remain explicit simulation policies, not calibrated psychology.

`development-demo.json` enables provisional maturation and crystallization. With crystallization enabled, old success-only trait deltas are not additionally applied. `initialize_life.py --inherited` uses the existing profile environment; its adult-to-child extrapolation is labeled. Legacy policies/checkpoints still retain their original behavior.

Mathematical corrections: the report's genetic weighting example implies 80%, not 50%, variance contribution under its stated noise scales. The new latent model uses square-root variance weights and explicit segregation/non-shared residuals. Founder conditioning uses original materialization dispositions where available, so later acquired changes do not become inherited. Age curves and state recovery use elapsed simulated time rather than function-call counts.

Eight check scripts pass: context, fidelity, situation, lifetime, development, temperament, world growth and interaction. The core demo passes as `development-core-example`. New checks include caregiver information isolation, same-day influence bounds, independent resolved experiences, trajectory/resume equivalence, no post-death maturation, stable sibling generation, selected-person activation and rollback, state-dependent thinning/resume, and actual-token overflow guards.

Actual 27B runs are saved separately: `development-live-example/run` (three actions, six appraisals, two consolidations, three received caregiving episodes; one offered action); `crystallization-live-example/run` (three additional actions, three appraisals, two offered choices, one bounded lasting update after repeated matched states). The latter fixture deliberately matches a generated signature, so it is not independent predictive validation. Subsequent actual-model smoke checks exercise bounded context/tokenization and appraisal with controller score hints removed. Historical traces predate those last refinements; preserve their exact scope.

The longer updated birth-to-22 run is in `development-lifetime-live`. Its first attempt caught a misspelled required model field and correctly rolled the entire first event back; this evidence is retained in `first-attempt`. Bounded structured-output repair allows at most two additional validated responses before mutation. The replacement run repaired three malformed/citation responses and reached age nineteen before the connection dropped. That interrupted state remains archived. The subsequent `continued-run` reached age 22 with 31 resolved actions, 12 caregiving episodes, nine Alex gist beliefs and 90 recalls across agents. The preparation goal completed. Use the archived policy for that trajectory; the current default gained independent caregiver replies afterwards.

Still unfinished: full constrained biography expansion/probing, semantic retrieval/interference/detail loss, automatic conditional reconsolidation and narrative updates, autonomous rumination, competing goals/time allocation/habits, general demographic/social/economic consequences, and empirical/instrument calibration. Wider society/mental-health research remains separate. Do not describe this developmental milestone as full replication of the four-day design.

### Continuation: situational personality and durable sources

The project-root `AGENTS.md` points to `outputs/START_HERE.md`, this state, the audit and `sources/README.md`. Ten PDF reports plus their extracted text are now preserved under `sources/`; copied PDFs were checked against the audit hashes. The complete raw Claude transcript is not locally archived: preserve that distinction from the local conversation review.

`situation.py` and the engine/controller now connect one-time model-generated CAPS-style signatures, subjective eight-dimensional situation construal plus controllability, rule-specific temporary domain shifts, and behavioral-language expression before action. Offsets remain separate from enduring facet scores. Simultaneous influences are summed before bounding; recovery depends on elapsed simulated days rather than tick count. `development-demo.json` enables the layer for local-model runs. Scripted runs deliberately skip model-generated rules/construal. Old archived policies remain compatible and retain their original behavior.

`check_situation.py` passes: read purity, bounds, unchanged baseline, exact half-life behavior, checkpoint equivalence, malformed-output rejection and complete event rollback after signature generation. The existing fidelity and lifetime checks also pass. This is an engineering implementation of the report's suggested architecture, not empirical calibration, a TGA mapping, learned state covariance or the full TESSERA model.

`situation-live-example/run` completed on the actual 27B API: one signature-generation request, one construal, one action, two appraisals and one consolidation, in 56.5 seconds. Two actions were offered. In this natural scenario the model matched no full signature trigger, so no temporary shift was forced merely because a dimension was present. A second actual-model synthetic matched-trigger probe activated `sig-02`, produced nonzero temporary offsets and an action context with behavioral-language shifts, while enduring traits stayed unchanged. It is saved separately in `situation-live-example/matched-*`; its action is an intention only, with no world outcome awarded. The probe fixture was designed from a generated trigger to exercise the branch, not to establish predictive performance.

The user identified a real numerical-prompting departure and requested a complete reread and correctness pass. Read [source-to-code-audit.md](source-to-code-audit.md) before continuing. It supersedes earlier broad descriptions of component completion. The complete visible conversation and ten reports (171 pages of extracted text) were reread; hidden historical attachments and independent verification of every cited study are outside that completion claim.

Repaired: selected behavioral-language personality on all model paths; actual-use and listener-cued recall; recalled-affect habituation; per-agent affect parameter support; accessibility/cue gating for old episodes; source-linked personality-conditioned gist consolidation; continuous event-time scheduling for constant-rate age-window opportunities. The source's rejected reconsolidation formulas remain excluded. Each provisional replacement is labeled.

The corrected `audited-live-example/run` contains an actual 27B wiring check: one action, two appraisals, one consolidation response, three recorded recalls and two gist beliefs. Both adults used the existing correlated sampler. All requests used language descriptions instead of a numeric personality table. This check offers one action, so it does not measure behavioral diversity or improvement.

Historical audit-stage scope: core demo/lifetime/fidelity checks passed and a quiet forty-year interval took zero opportunity steps. The later developmental continuation above now supplies provisional attachment, inherited dispositions, maturity/crystallization and bounded state-dependent rate mechanisms. Full biography/probing and wider society modules still need work.

## Latest verified milestone: live cluster run complete

Historical milestone below describes the pre-audit prototype, not the corrected full design.

The user restored the SSH connection. It was reused successfully to reach `nst-n6` and the selected HauhauCS 27B local API. A loopback-only forward on local port 18081 reaches remote port 8081 through that existing SSH connection.

`run_live.py` completed 89 ticks through simulated age 22 with **30 actual model actions and 36 actual appraisals**, in about seven minutes. All 30 actions were resolved and saved. The final checkpoint restored successfully. This supersedes earlier notes that live inference was blocked. Read [the actual run report](live-run-report.md) and `live-example/summary.json`.

The scenario goal incorrectly included delivery while its actions only prepared material. This was corrected for future runs. No delivered presentation is claimed for the completed run. Exact policies for both saved age-22 runs are archived alongside their checkpoints; resume them with those archived policies.

## Decisions that must survive context changes

- Build the integrated system first; evaluate and improve it afterwards. Do not substitute another narrow comparison for implementing the user's design.
- Use the existing local 27B model through its API. Do not add a 9B comparison, fine-tuning, LoRA or activation steering.
- The application is a social simulation research tool. Memory, mood, lifetime development, life planning, family and relationships all belong in its intended architecture.
- Preserve the full design, including correlated facets, situational behavior, attachment/culture, parent/caregiver context, lazy materialization, probing versus belief versus acquaintance, explicit information flow and slow trait development.
- A generated report is a proposed source, not proof of a psychological law. Provisional constants must remain visible.
- Do not restore the rejected numerical reconsolidation implementation.
- Correct clear mathematical/implementation errors as they are found, record the original issue and replacement, and keep source references accessible for continuation. Do not mistake an uncalibrated coefficient for an algebraic error with a uniquely known fix.
- Never estimate an improvement percentage from architectural richness alone. No full-system predictive result exists yet.

## Current runnable milestone

`engine.py` implements one connected, persistent state loop, with model-based appraisal/action entry points. `demo.py` exercises family context, later caregiver materialization, private/received speech, memory, mood, reinterpretation, a goal plan and an action-dependent life event. Saved state resumes without dropping the agent's history.

The standard-library example and an example using the existing correlated population sampler both ran successfully. The subsequent automatic lifetime controller also ran birth-to-age-22: 89 ticks, 27 resolved actions, automatic stage eligibility, goal progress and bounded evidence-linked trait development. These particular example files use scripted decisions; actual 27B model output is stored separately in `live-example`. This is an initial engine milestone, not a completed autonomous society or a validated developmental model.

## What exists versus what still needs a policy

| Exists as runnable behavior | Still needs implementation or grounding |
|---|---|
| Automatic age-eligible opportunities, bounded state-dependent rate policies, prerequisites and scenario action outcomes | Calibrated demographic/structural policies and a general world resolver |
| Goals, deadlines, plans and recorded intentions | Replanning triggers, competing-goal allocation and durable habits |
| Memory encoding, gated ranking, actual-use rehearsal, source-linked gist and revisions | Semantic search, detail-loss modeling and calibrated forgetting/revision |
| Power-law affect with latent mass budget, individual settings, recalled affect and habituation | Calibrated trait/time mappings, state appraisal behavior and autonomous rumination policy |
| Family constraints, selected-contact activation, optional inherited dispositions and received caregiver learning | Full constrained biography generation, child norms and calibrated developmental policies |
| Separate trust/closeness/acquaintance and testimony provenance | Grounded automatic trust changes, social probing and introduction policies |
| Bounded repeated state-conditioned changes, age curves and learned attachment in context | Empirical grounding, richer narrative/role dynamics and fitted state variability |

## Next implementation sequence

1. Completed: connect the local 27B appraisal and action path to the running cluster and save an actual childhood-to-adult scenario separately from the scripted example.
2. Extend the implemented controller beyond the supplied scenario; it already takes intended actions, resolves explicit consequences and delivers subjective observations to participants.
3. Extend constrained life-event generation and replanning; the age-eligible opportunity process and automatic stage goals are now implemented.
4. Extend childhood, caregivers, belief revision and social introductions without inventing contradictory background.
5. Resume comparative/human validation after the integrated behavior exists.

Earlier, the saved SSH control socket was absent and a fresh attempt failed at an authentication prompt. The user reconnected, resolving this blocker. No SSH-server restart was required by any verified finding.

## Files and verification

- `example/world.json`: synthetic-profile saved simulation.
- `example-sampled/world.json`: saved simulation using the existing correlated sampler (adult-to-child extrapolation explicitly marked).
- `example*/trace.json`: before/after agent contexts with the scripted action labeled.
- `example*/engineering-checks.json`: completed correctness checks, not scientific validation.
- `lifetime.py`: automatic age-eligible event/action/appraisal/outcome/development loop, with atomic tick rollback on provider failure.
- `development-demo.json`: visible scenario rates and effects; all are assumptions.
- `lifetime-example/age22.json`: saved automatic run with scripted decisions.
- `check_lifetime.py` / `lifetime-engineering-checks.json`: restart equivalence, bounded changes, age eligibility, outcome links, rollback and a stubbed model integration check.
- `source-to-code-audit.md` / `source-audit-manifest.json`: authoritative reread scope, confirmed departures, repairs and remaining coverage.
- `personality.py`: internal numerical facets to selected behavioral descriptions.
- `check_fidelity.py` / `fidelity-engineering-checks.json`: source-fidelity regression checks.
- `audited-live-example/run`: corrected actual-model integration trace; distinct from the older full scenario.

Do not conflate the previous prompt pilots or short memory/mood probes with a result for this integrated system.
