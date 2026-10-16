# Recorded runs

Preserved simulation evidence. **Do not edit or overwrite these directories.** Their files are exactly as produced, so `source-hashes.json` keys, summaries and reports refer to the pre-restructure layout (`outputs/agent_engine/...`); see [the path map](../docs/history/README.md#old-to-new-paths). Write new runs to a fresh directory.

## `live/`

Actual HauhauCS 27B runs: `requests.jsonl` traces, `server-model.json`, summaries, checkpoints and integrity checks. Many contain several attempts (`run`, `continued-run`, `final-run`, `first-attempt`); each keeps its own scope.

- `audited-live-example`
- `crystallization-live-example`
- `development-lifetime-live`
- `development-live-example`
- `fixed-infant-test`
- `fixed-infant-test-v2`
- `fresh-infant-test`
- `fresh-integrated-test`
- `fresh-memory-continuation`
- `full-build-infant-live`
- `full-build-live`
- `goal-plans-live`
- `goal-plans-success-live`
- `graphiti-live`
- `household-live`
- `integrated-live-example`
- `interaction-live-example`
- `interview-live`
- `live-example`
- `situation-live-example`

## `scripted/`

Deterministic engineering-provider runs from `simulate --scripted` and earlier scripted demos. They skip model-only cognition.

- `fresh-century-test`
- `full-build-short-check`
- `full-build-short-check-v2`
- `full-lifespan-final`
- `full-lifespan-scripted`
- `goal-plans-scripted`
- `goal-plans-scripted-final`
- `graphiti-launcher-scripted-check`
- `household-lifetime-check`
- `household-lifetime-final`
- `integrated-scripted-example`
- `lifetime-example`

## `core/`

Outputs of the twelve-check core demonstration (`devsim.demo`) recorded at successive milestones.

- `audited-example`
- `development-core-example`
- `example`
- `example-sampled`
- `final-core-check`
- `final-core-retest`
- `fresh-core-test`
- `full-build-core-check`
- `goal-plans-core-test`
- `graphiti-core-check`
- `household-core-check`
- `integrated-core-check`
- `integrated-final-core`

## `probes/`

Graphiti durable-queue/restart probes.

- `graphiti-restart-probe`
- `graphiti-restart-probe-final`

## `verification/`

Verification manifests from each phase (suites, check counts and source hashes). The newest is `household-verification.json`; `final-engineering-verification.json` is the cumulative engineering manifest.
