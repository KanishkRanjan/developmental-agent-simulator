# Continue the developmental engine

> Current status, verification counts and run commands: [BUILD_STATE.md](BUILD_STATE.md). Status banners that were repeated at the top of this file are preserved in [the build-state log](history/BUILD_STATE-log.md).

## Latest fresh test and infant correction

See [LATEST_TEST_REPORT.md](history/LATEST_TEST_REPORT.md) and [fresh-integration-verification.json](../runs/verification/fresh-integration-verification.json). The current verification is **139 named regression checks plus twelve core checks**. Fresh actual 27B caregiver/infant runs and a resumed adult memory interaction completed; a second 100-year scripted scenario completed 165 resolved actions with six deaths and no pending activities. This seed did not produce a birth; earlier new-generation evidence remains separate.

Testing exposed infant CAPS rules with adult-like cognitive challenges despite nonverbal action constraints. `situation.py` now provides bounded infant sensory triggers/nonverbal reactions, `engine.py` supplies capability context and refreshes generated rules at ages two/five. A wrong-root JSON response failed safely; explicit schema/repair feedback fixed the replay. Final regression and corrected infant evidence are recorded with source hashes. These checks establish runnable behavior, not human validity or full scientific coverage. Earlier counts/traces below are historical.


Updated 16 October 2026. The integrated extension has now passed local checks and a short actual 27B replay. Earlier development-stage checkpoints remain preserved. Continue from the checkpoint appropriate to the policy; do not confuse scripted, seeded short-live and earlier lifespan evidence.

## Latest build and checkpoints

Read [FULL_BUILD_STATE.md](history/FULL_BUILD_STATE.md) and [REVIEW_LATER.md](history/REVIEW_LATER.md). `simulate.py` is the combined launcher. Ten suites pass (136 named checks), plus the core demo.

- [Adult 27B final world](../runs/live/full-build-live/run/world.json), [policy](../runs/live/full-build-live/run/policy-used.json), [integrity](../runs/live/full-build-live/run/integrity-checks.json): two resolved actions, eighteen calls, open biographies/indexed recall/elapsed completion. This is a seeded age-18 fixture.
- [Infant 27B final world](../runs/live/full-build-infant-live/run/world.json), [policy](../runs/live/full-build-infant-live/run/policy-used.json), [integrity](../runs/live/full-build-infant-live/run/integrity-checks.json): two resolved actions, seventeen calls, nonverbal infant behavior and independently delayed care; two exact-mention output repairs. JSON/SQLite worlds both restore.
- [85-year scripted final world](../runs/scripted/full-lifespan-final/world.json), [policy](../runs/scripted/full-lifespan-final/policy.json), [integrity](../runs/scripted/full-lifespan-final/integrity-checks.json): 209 resolved actions, a new generation, three deaths. Scripted provider skips model-only paths.

Earlier `integrated-live-example` and `development-lifetime-live` runs remain archived with their own policies. Do not replace policy fingerprints to enable newer features on them. For a new complete combined scenario, use the launcher and a fresh output directory. For a resume, use the corresponding checkpoint/provider/archived policy and a fresh run output directory. No inference client from this work is still running.

## Remaining research scope

The accepted software paths now exist; scientific coefficients, child norms, instrument mapping, semantic truth/consistency and population/clinical calibration remain unresolved. Canonical graph persistence is SQLite/JSON. The optional local Graphiti index (Neo4j 5.26 + BGE) was installed on the cluster machine on 16 October 2026 without Docker; see [the Graphiti setup](../services/graphiti-local/README.md). Comparative evaluation remains paused. Exact live/local/source-version boundaries are in the full-build state.

## Reconnect

**16 October 2026:** the HauhauCS 27B llama.cpp server was running on the cluster machine itself at `http://127.0.0.1:8081` (8192-token context); the interview runs used it directly, without the SSH forward. Check it again rather than assuming it is still up. The same day the local Graphiti service was installed there (no Docker; `work/graphiti-runtime/`, `work/graphiti-env/`). Start it with `python3 services/graphiti-local/start.py --llm-url http://127.0.0.1:8081`; it listens on loopback port 18082, with Neo4j on 17687/17474.

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

Update [build state](BUILD_STATE.md), [the audit](source-to-code-audit.md) and [checkpoint status](../runs/live/development-lifetime-live/checkpoint-status.json) after changes. The project-root agent instructions point new sessions to these records.
