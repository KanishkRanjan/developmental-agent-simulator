# Continue the developmental engine

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


Updated 16 October 2026. The integrated extension has now passed local checks and a short actual 27B replay. Earlier development-stage checkpoints remain preserved. Continue from the checkpoint appropriate to the policy; do not confuse scripted, seeded short-live and earlier lifespan evidence.

## Latest build and checkpoints

Read [FULL_BUILD_STATE.md](FULL_BUILD_STATE.md) and [REVIEW_LATER.md](REVIEW_LATER.md). `simulate.py` is the combined launcher. Ten suites pass (136 named checks), plus the core demo.

- [Adult 27B final world](full-build-live/run/world.json), [policy](full-build-live/run/policy-used.json), [integrity](full-build-live/run/integrity-checks.json): two resolved actions, eighteen calls, open biographies/indexed recall/elapsed completion. This is a seeded age-18 fixture.
- [Infant 27B final world](full-build-infant-live/run/world.json), [policy](full-build-infant-live/run/policy-used.json), [integrity](full-build-infant-live/run/integrity-checks.json): two resolved actions, seventeen calls, nonverbal infant behavior and independently delayed care; two exact-mention output repairs. JSON/SQLite worlds both restore.
- [85-year scripted final world](full-lifespan-final/world.json), [policy](full-lifespan-final/policy.json), [integrity](full-lifespan-final/integrity-checks.json): 209 resolved actions, a new generation, three deaths. Scripted provider skips model-only paths.

Earlier `integrated-live-example` and `development-lifetime-live` runs remain archived with their own policies. Do not replace policy fingerprints to enable newer features on them. For a new complete combined scenario, use the launcher and a fresh output directory. For a resume, use the corresponding checkpoint/provider/archived policy and a fresh run output directory. No inference client from this work is still running.

## Remaining research scope

The accepted software paths now exist; scientific coefficients, child norms, instrument mapping, semantic truth/consistency and population/clinical calibration remain unresolved. Graph persistence is SQLite; no Neo4j service or additional embedding model was installed. Comparative evaluation remains paused. Exact live/local/source-version boundaries are in the full-build state.

## Reconnect

The user's existing connection command, to run in their terminal:

```sh
ssh -fMN -S /Users/kanishkranjan/Documents/Codex/2026-10-15/realtime-voice-chat/work/s \
  -o ConnectTimeout=120 -o ControlPersist=12h \
  -o ServerAliveInterval=15 -o ServerAliveCountMax=6 \
  -J nst1 kanishk@192.168.136.150
```

After the user restores authentication, reuse that master and recreate the loopback-only forward:

```sh
ssh -S /Users/kanishkranjan/Documents/Codex/2026-10-15/realtime-voice-chat/work/s \
  -O check kanishk@192.168.136.150
ssh -S /Users/kanishkranjan/Documents/Codex/2026-10-15/realtime-voice-chat/work/s \
  -O forward -L 127.0.0.1:18081:127.0.0.1:8081 kanishk@192.168.136.150
```

If the forward already exists, reuse it. Verify the served model against `development-lifetime-live/run/server-model.json`: the selected HauhauCS 27B local model, not a smaller fallback. Do not close the user's master or restart their server without evidence that it is necessary.

## Future continuation

Use a new output directory and the completed world and its archived policy for any intentional extension. The policy has only the supplied age windows; increasing the end day alone does not create richer opportunities. Inspect and document a policy extension rather than silently changing a checkpoint's fingerprint. Preserve earlier request traces and summaries.

Update [build state](BUILD_STATE.md), [the audit](source-to-code-audit.md) and [checkpoint status](development-lifetime-live/checkpoint-status.json) after changes. The project-root agent instructions point new sessions to these records.
