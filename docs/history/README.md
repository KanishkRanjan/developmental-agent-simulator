# Milestone history

These documents record earlier build phases in the order they were written. Each keeps its original counts, scope and wording; only link targets were updated when files moved. The current state is in [BUILD_STATE.md](../BUILD_STATE.md).

| Document | What it recorded |
|---|---|
| [BUILD_STATE-log.md](BUILD_STATE-log.md) | The full running build-state log, newest milestone first (formerly `outputs/agent_engine/BUILD_STATE.md`). |
| [START_HERE-log.md](START_HERE-log.md) | The previous continuation guide with every milestone banner (formerly `outputs/START_HERE.md`). |
| [CURRENT_STATUS.md](CURRENT_STATUS.md) | Five-layer implementation map and the grounded goal-plans phase (161 checks). |
| [GOAL_PLANS_LIVE_REPORT.md](GOAL_PLANS_LIVE_REPORT.md) | Actual 27B goal-plan failure and success fixtures. |
| [LATEST_TEST_REPORT.md](LATEST_TEST_REPORT.md) | Fresh regression pass (139 checks), infant correction and 100-year scripted run. |
| [FULL_BUILD_STATE.md](FULL_BUILD_STATE.md) | Full software pass (136 checks), adult/infant 27B fixtures and 85-year scripted run. |
| [REVIEW_LATER.md](REVIEW_LATER.md) | One-command launcher and evidence index from the full software pass. |
| [live-run-report.md](live-run-report.md) | First actual-model run report. |

## Old to new paths

Run artifacts (`source-hashes.json`, summaries, reports) still contain the absolute and relative paths that were true when they were produced. Use this map to locate those files now.

| Old location | New location |
|---|---|
| `outputs/agent_engine/*.py` (engine modules and launchers) | `devsim/*.py`, run as `python3 -m devsim.<module>` |
| `outputs/identity_state_prototype.py`, `outputs/profile_population_v1.py` | `devsim/` |
| `outputs/profile_population_v1_model.json`, `outputs/ipip_neo_120_key.json` | `devsim/data/` |
| `outputs/agent_engine/development-demo.json`, `integrated-demo.json` | `devsim/policies/` |
| `outputs/agent_engine/check_*.py` | `checks/`, run as `python3 -m checks.check_<suite>` or `python3 -m checks.run_all` |
| `outputs/agent_engine/*-engineering-checks.json` | `checks/results/` |
| `outputs/agent_engine/*verification.json`, `api-wiring-checks.json`, `work/fresh-regression-results.json` | `runs/verification/` |
| `outputs/agent_engine/<run>/` | `runs/live/`, `runs/scripted/`, `runs/core/` or `runs/probes/` (see [runs/README.md](../../runs/README.md)) |
| `outputs/agent_engine/graphiti-local/` | `services/graphiti-local/` |
| `outputs/agent_engine/sources/` | `research/sources/` |
| `outputs/agent_engine/README.md` | `docs/engine.md` |
| `outputs/agent_engine/{source-to-code-audit,development-notes,integrated-build-notes,RESUME,HOUSEHOLD_IMPLEMENTATION,GRAPHITI_IMPLEMENTATION}.md`, `source-audit-manifest.json` | `docs/` |
| `outputs/agent_engine/{GRAPHITI_MIROFISH_REVIEW,MIROFISH_NEXT_FEATURES}.md`, `outputs/*.md` design notes | `docs/design/` |
| `outputs/` personality experiments and their scored results | `research/experiments/`, `research/experiments/results/` |
| `work/` experiment data, rubrics and scoring scripts | `research/experiments/raw/` |
| `work/IPIP*` paper, notebook and dataset | `research/ipip-neo-120/` |
| `work/` page-marked report extractions (hyphenated names) | `research/sources/page-marked/` |
| `work/` one-off prepare/finalize/update/verify scripts | `archive/work-scripts/` |

Byte-identical duplicates in `work/` were removed: the space-named report `.txt` copies, `mood-report.*` and `lifespan-report.*` (the same files as `research/sources/Mood and Memory.*` and `Lifespan Development.*`), `model_retention_eval.py` and the two `identity-*-results.jsonl` files (identical to the copies in `research/experiments/`).
