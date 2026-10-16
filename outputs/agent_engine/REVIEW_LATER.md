# Review the completed software build

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


16 October 2026. Start here when you return. The engine now has runnable paths for the accepted developmental-agent architecture, including the extensions listed below. Research assumptions remain visible; implementation does not establish human replication or improved prediction.

## Run it

From the project root, use a fresh output directory:

```sh
work/profile-env/bin/python outputs/agent_engine/simulate.py \
  --years 22 --out outputs/agent_engine/MY_NEW_RUN \
  --api http://127.0.0.1:18081
```

This uses the existing local HauhauCS 27B API and correlated profile environment. It initializes caregivers before children, runs the whole declared policy and saves state, policy, source hashes and model traces. Add `--caregivers 2` for two known caregivers per initial household. Fine-tuning, activation steering and smaller-model fallbacks remain excluded.

For a deterministic software run without inference, add `--scripted`. This intentionally skips model-based appraisal, semantic cognition, biography generation and reflection. It is an engineering provider, not an alternative realism result.

Continue an actual-model run with its saved `world.json`, its exact `policy-used.json` and `run_live.py` in a new output directory. Saved policy fingerprints prevent silently swapping designs. JSON and SQLite checkpoints both load through `Engine.load`. SQLite provides a normalized provenance graph and the complete resumable state. Graph audit queries are controller tools; they do not bypass the agent's memory-access rules.

## What is connected

| Layer | Code and behavior |
|---|---|
| Identity/personality | Correlated thirty-facet internal profiles; selected behavioral language; optional separately supplied Honesty-Humility description. No fabricated TGA conversion. |
| Situations and variability | CAPS signatures, subjective construal, temporary offsets, elapsed-time recovery, configurable correlated variation and explicit per-agent variability. Variation does not overwrite enduring traits. |
| Culture | Supplied context-sensitive expression rules reach the model without inferring cultural stereotypes from identity. |
| Memory | Source-separated episodes, lazy access, immutable originals, gist/detail separation, rehearsal, interference, semantic selection and a full available-corpus FTS/BM25 index with local-model query expansion. |
| Mood | Event/recall impulses, individual settings, valence/arousal distinction, latent bounds, cooldown and habituation; autonomous cognitive events are separately scheduled. |
| Reinterpretation/narrative | Received-evidence retain/defer/revise decisions, exposure queues, earlier versions, evolving self-story and evidence-linked personal lessons. |
| Childhood/development | Parent-first initialization, separate biological parents/caregivers, inherited-disposition proxy, received-care learning, temporary versus enduring change, age curves and bounded crystallization. Infant actions are nonverbal under the new policy. |
| Histories/spawning | Needed-person materialization, canonical alternatives or open-value structured biographies, birth/date/interval/world-lock validation, shared commitments and preserved original experiences. Newborns acquire life opportunities and hazards. |
| References/social knowledge | Listener-scoped candidate identities, unresolved ambiguity, explicit later binding, testimony distinct from truth/acquaintance, received reminders and queued questions transmitted during actual contact. |
| Relationships | Independent replies; actual approaches encoded before task completion; explicit shared encounters; separate trust/closeness with evidence, daily bounds and elapsed-time closeness decay. |
| Planning/agency | Existing and self-set evidence-linked goals; canonical goal opportunities; replanning; budgets, resources, habits and actual elapsed-time reservations/completions. Intervening death or invalid prerequisites can cancel an intention. |
| World/economics | Age-window exogenous hazards, fixed events, action effects, employment/health flags, resource credits/debits, conserved transfers, roles, births, recovery and death. These are declared scenario rules. |
| Persistence/recovery | Atomic JSON/SQLite saves, normalized private provenance graph, archived policies/source hashes, transaction rollback, pending-activity resume and dynamic-generation scheduling. |

## Evidence to inspect

- [Current verification manifest](final-engineering-verification.json) and [new-path checks](complete-engineering-checks.json).
- [85-year scripted run](full-lifespan-final/summary.json): the whole software lifecycle, including a new generation and later-life deaths. This does not execute model-only paths.
- [Adult 27B run](full-build-live/run/summary.json): open biography generation, full-corpus query expansion/reranking, independent choices, actual elapsed completion and reflection. Its fixture starts at age eighteen with explicitly seeded experiences.
- [Infant 27B run](full-build-infant-live/run/summary.json): actual nonverbal early-life path; consult its final status rather than assuming every offered branch ran.
- [Full-build status](FULL_BUILD_STATE.md) records exact final counts and verification boundaries.

## Scientific and scope boundaries

The code supplies policies and mechanisms. The sample rates, state covariance/variance, developmental coefficients, cultural rules, retention thresholds, habit dynamics, household structure and illness/death events are not calibrated population estimates. Adult profile data are not child norms. A semantic index improves candidate coverage mechanically; it does not guarantee exhaustive semantic recall or psychological fidelity. Structured chronology validates facts and intervals, not every semantic assertion in generated prose. Personal interpretations can remain mistaken or overconfident.

The source's unsupported 120-item-to-TGA mapping remains unasserted. Separate Honesty-Humility scores need their own provenance. The rejected numerical reconsolidation design stays excluded. Neo4j/Graphiti deployment and a fitted clinical simulator are not required by this local engine and are not claimed. The broader M1–M8 report was not available; available social/economic primitives do not constitute that missing scientific report. Comparative/human validation remains deferred under the build-first decision.

Use the [source-to-code audit](source-to-code-audit.md), [preserved reports](sources/README.md) and [full-build notes](FULL_BUILD_STATE.md) for continuation. Older milestones remain archived and retain their historical limitations.
