# Full software-build handoff

> **Historical record.** Moved here in the October 2026 restructure; content is unchanged apart from link targets. Counts and scope are as of writing. Commands and bare file names refer to the old `outputs/agent_engine/` layout; see [the path map](README.md#old-to-new-paths).

## Latest: household environment and conversation layer

[Household implementation](../HOUSEHOLD_IMPLEMENTATION.md) is the newest phase. Explicit rooms/audibility, private multi-turn conversation, waking windows/response intervals and elapsed calendar reservations now connect to the existing scheduler, memory/mood and optional cognition/development paths. Use `household_example.py` for a short scene or `simulate.py --household` for fresh combined policies; archived policies remain unchanged.

Thirteen suites pass **185 named checks plus twelve core checks**, including 24 new household checks. The actual HauhauCS 27B scene completed four independent turns/23 calls with no Graphiti fallback; a closed-room person received none of it. The final seven-year scripted combined run completed 61 actions including 16 conversation turns. [Verification](../../runs/verification/household-verification.json) and the implementation guide record the source-version boundary: optional crystallization/sample-clock refinements are locally checked, while the preserved live trace precedes them. These are engineering results, not measured human fidelity. Automatic scenario authoring, interviews, report generation and a GUI remain proposed.

Earlier milestone sections below are historical and keep their original scope.

## Latest: local Graphiti and MiroFish-inspired tools

[GRAPHITI_IMPLEMENTATION.md](../GRAPHITI_IMPLEMENTATION.md) and [setup guide](../../services/graphiti-local/README.md) supersede older “no Graphiti/embedding model” statements below. The engine now has a local Graphiti/Neo4j/BGE retrieval index, durable background outbox, explicit fallback diagnostics and read-only quick/deep/history/chain tools. No Zep Cloud subscription or hosted inference dependency was added.

Twelve suites pass **161 checks plus twelve core checks**. The final actual 27B fixture completed five calls/one action with graph-based recall, no fallback, preserved privacy and matching JSON/SQLite restoration. Durable offline-queue/restart behavior was checked separately. The index is derived from private views, not a new source of world truth; immutable-cache scale and unrestricted extraction/history limitations remain explicit. The graph service/container remain running; language test clients have finished.


## Current phase and the five previously listed gaps

Read [CURRENT_STATUS.md](CURRENT_STATUS.md). All five categories—semantic/gist/interference recall; evidence-based reinterpretation/narrative; autonomous recall/planning/budgets/habits; constrained families/history/questions; world transitions/births/newborn opportunities—have connected implementations. Older missing-work lists below are historical.

The next phase adds `goal_plans.py`: ordered action-bound steps, received-outcome completion, archived replans, stale-binding protection and no progress for merely writing an intention. New combined policies enable `planning.grounded_plans`; archived policies remain unchanged. Eleven suites now pass **149 checks plus twelve core checks**, and a fresh three-year scripted run completed 28 resolved actions. [Evidence](../../runs/verification/goal-plans-verification.json) now includes the completed actual 27B tests: a failed default-policy task stayed unfinished, and a controlled draft/review fixture completed two received-outcome-linked steps. [Live report](GOAL_PLANS_LIVE_REPORT.md) records exact scope, model, source hashes and checkpoint checks. The restored SSH connection and loopback forward worked; no inference job remains running.


## Latest fresh test and infant correction

See [LATEST_TEST_REPORT.md](LATEST_TEST_REPORT.md) and [fresh-integration-verification.json](../../runs/verification/fresh-integration-verification.json). The current verification is **139 named regression checks plus twelve core checks**. Fresh actual 27B caregiver/infant runs and a resumed adult memory interaction completed; a second 100-year scripted scenario completed 165 resolved actions with six deaths and no pending activities. This seed did not produce a birth; earlier new-generation evidence remains separate.

Testing exposed infant CAPS rules with adult-like cognitive challenges despite nonverbal action constraints. `situation.py` now provides bounded infant sensory triggers/nonverbal reactions, `engine.py` supplies capability context and refreshes generated rules at ages two/five. A wrong-root JSON response failed safely; explicit schema/repair feedback fixed the replay. Final regression and corrected infant evidence are recorded with source hashes. These checks establish runnable behavior, not human validity or full scientific coverage. Earlier counts/traces below are historical.


Updated 16 October 2026. This supersedes earlier lists that call the newly connected software paths missing. It does not supersede source uncertainty, user exclusions or the distinction between an engineering implementation and validated human behavior.

## Entry point

Use [REVIEW_LATER.md](REVIEW_LATER.md). The one-command launcher is `simulate.py`; `full_scenario.py` builds the combined policy and initializes caregivers before children. Existing earlier policies and traces remain preserved.

```sh
work/profile-env/bin/python outputs/agent_engine/simulate.py \
  --years 22 --out outputs/agent_engine/NEW_RUN --api http://127.0.0.1:18081
```

`--caregivers 2` selects two known caregivers per initial household. `--scripted` uses the deterministic engineering provider. The correlated profile environment is already present under `work/profile-env`. Source hashes, launch arguments and policy are saved. The live runner requires the selected local HauhauCS 27B and rejects a smaller/unrelated fallback.

## What changed in this pass

- `retrieval.py`: local-model query expansion over the entire available private corpus, SQLite FTS5/BM25 candidate retrieval and bounded semantic reranking. Hidden original details never enter the index. Topic-fan counting now uses a linear counting pass.
- `references.py`: listener-local identity candidates, retained name/pronoun ambiguity, unknown-reference records without person creation, explicit later identification and preserved binding provenance. Appraisal can identify exact heard mentions and available-memory reminders. Gist reminders cannot rehearse lost original details.
- `biography.py`: open text values and structured dated intervals, constrained by birth, existing current facts, shared world effects and earlier timeline commitments. These are synthetic initialization, not newly received memories or proof of testimony. `life_policy.py` retains the older canonical-alternative mode too.
- `calendar_time.py`: actual reservations across simulated-day boundaries, later completion, cancellation on intervening death/prerequisite/resource changes and pending-intention recovery. Approaches are encoded before independent replies. Costs/habits/outcomes apply once at resolution.
- `expression.py`: configurable positive-semidefinite state correlation, per-agent variation settings, seeded elapsed-time innovations and explicit cultural rules. Optional supplied Honesty-Humility uses a separate construct/provenance and language, never an invented Big Five/TGA conversion. New-policy infant actions have empty speech/plans; infant reflection omits adult verbal narrative.
- `society.py`: elapsed-time closeness views and conserved transfers. Existing independent trust/closeness updates and private evidence boundaries remain intact.
- `lifetime.py`/`cognition.py`: self-set received-evidence goals can acquire canonical actionable opportunities. Exogenous age-window hazards and newborn hazard/opportunity templates join the persistent scheduler. Hazards model declared scenario processes, not empirically fitted epidemiology.
- `graph_store.py`: atomic SQLite checkpoints with normalized owner-scoped provenance nodes/edges and complete resumable state. JSON remains supported. Forensic graph access is a controller audit facility, not an agent recall bypass or multi-user security boundary.
- `full_scenario.py`/`simulate.py`: infancy, early childhood, school, adolescence, adult tasks, separate caregiver agency, birth/new-generation policies, generic illness/recovery and later-life death in one runnable setup.

All earlier integrated layers remain connected: behavioral-language personality, CAPS/construal, mood, gist, subjective interpretation, attachment proxies, inherited dispositions, age maturation, bounded crystallization, plans and habits. Fine-tuning/LoRA/activation steering/9B remain excluded.

## Final local verification

[Verification manifest](../../runs/verification/final-engineering-verification.json): **ten suites, 136 named checks, plus the twelve-check core demonstration**, with final source hashes. [Complete-path checks](../../checks/results/complete-engineering-checks.json) add full-corpus search/privacy, unresolved identification, open histories, temporary variation/culture, elapsed reservations, interrupted completion/retry, conserved transfers, graph round-trips, hazards and no model fallback. The earlier 111-check milestone is archived in `integrated-stage-verification.json`.

[85-year final scripted run](../../runs/scripted/full-lifespan-final/integrity-checks.json) completed at day 31046.25 with **209 resolved actions, five retained agent records, one new child, three later-life deaths, ten dynamic opportunities and three newborn hazards**. No activities remained pending. JSON and SQLite checkpoints restore identically. The new child continued into adulthood; this is a lifecycle software check. Scripted mode skips model-only semantic, biography, appraisal and reflection paths. It is not a full 27B lifespan or human-validity experiment.

The first short launcher attempt rejected duplicate opportunity IDs before advancing. IDs were scoped by actor, and the corrected short/final lifespan runs completed. The failed attempt remains archived in `full-build-short-check`.

## Actual 27B results

| Fixture | Verified result | Scope |
|---|---|---|
| [Adult](../../runs/live/full-build-live/run/integrity-checks.json) | Two resolved independently chosen actions, eighteen requests, 192.132 seconds, zero repairs. Open biographies for Alex/Bea, indexed query expansion and semantic selection, elapsed outcomes and final reflection. | Starts at age eighteen with explicitly seeded experiences and omitted earlier development. Narrative updates were optional; the model did not add a narrative in this fixture. |
| [Infant](../../runs/live/full-build-infant-live/run/integrity-checks.json) | Two resolved actions, seventeen requests, 173.771 seconds, two repaired appraisal outputs. Alex chose a nonverbal support signal with empty speech/plan. Maya independently chose `delay`; one received caregiving episode was retained. Infant narrative remained absent. | Synthetic initial family at simulated day 1.38; two offered infant choices and independent caregiver responses. No desired supportive response was forced. |

Both final worlds restore from JSON/SQLite, retain earlier episodes, separate start from outcome time and have no pending activities. The two infant repair calls rejected mention spans not literally present in received text; the third response passed before mutation. Current summaries count repairs as model requests, not extra accepted observations.

Traces have on-disk source hashes captured at run start. The adult trace precedes the final selected-model rejection guard and repeated-reference provenance repair. The infant trace exercises the model guard; the subsequent repeated-binding provenance repair is covered locally. Exact later changed filenames are listed in each integrity file. Do not claim every final source branch ran live merely because a trace completed.

## Deliberate research boundaries

The supplied reports propose a research architecture; they do not settle every rate, covariance, measurement mapping or causal link. The working defaults are explicit scenario policies. Data fitting and scientific evaluation remain for later review: child-specific norms, fitted state/development/hazard parameters, learned cultural mappings and a defensible TGA instrument mapping are not invented. Model interpretations, narratives and overview prose can be overconfident; structural validity is not semantic truth.

The graph storage is SQLite, without a deployed Neo4j/Graphiti service. The semantic index uses FTS/query expansion rather than a new embedding model. It searches the full available corpus before bounded reranking but cannot guarantee perfect semantic recall. Structured biography validation does not solve unrestricted semantic consistency. Generic illness/resource/role policies are not a fitted clinical or economic model. The separate mental-health extension and unavailable broad M1–M8 report are not falsely represented as completed scientific implementations.

Comparative and human predictive evaluation remain deferred under the user's build-first instruction. No improvement percentage or accurate reconstruction of a real person is established.

## Continue safely

Read the project-root agent instructions, this file, [the audit](../source-to-code-audit.md) and relevant preserved source passages. Use the correct saved world's archived policy; never replace a fingerprint to force a new policy onto old history. Reuse/check the existing SSH master and model forward before further actual inference. Do not restart the server merely because a saved connection closed.

No live inference job from this build remains running. All completed artifacts and failed-attempt evidence are retained under `outputs/agent_engine`. Keep future temporary scripts in `work/` and update the build state/audit after implementation changes.
