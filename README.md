# Developmental Agent Simulator

A research prototype for persistent agents with correlated personality facets, private memory, mood, goals, developmental change, family relationships, and a shared simulation environment. Local language decisions use the selected HauhauCS 27B model through an OpenAI-compatible local API. Fine-tuning, activation steering, hosted inference and paid Zep services are outside the current setup.

Start with [the continuation guide](docs/START_HERE.md), [the current build state](docs/BUILD_STATE.md) and [the source-to-code audit](docs/source-to-code-audit.md).

## Layout

| Path | Contents |
|---|---|
| `devsim/` | The engine package: agents, memory, mood, development, cognition, planning, household, storage and the launchers (`simulate`, `run_live`, `household_example`, `interview`, `author`, `report`, `cockpit`, `graphiti_bridge` (cache stats and compaction), `demo`, `initialize_life`). `devsim/policies/` holds the demo scenario policies; `devsim/data/` the fitted profile model and IPIP key. |
| `checks/` | Engineering check suites (`check_*.py`), `run_all.py`, and their latest results in `checks/results/`. |
| `services/graphiti-local/` | Optional self-hosted Graphiti/Neo4j/BGE retrieval service (Docker + `uv`, separately pinned). |
| `docs/` | Current status, audit, mechanism notes and phase guides; `docs/design/` for research design reviews; `docs/history/` for earlier milestone records and the old→new path map. |
| `runs/` | Preserved simulation evidence: `live/` (actual 27B), `scripted/` (deterministic provider), `core/` (core demo), `probes/`, and `verification/` manifests. See [runs/README.md](runs/README.md). |
| `research/` | The ten source reports (`sources/`), the IPIP-NEO-120 paper/dataset, and the earlier personality-prompting experiments. |
| `archive/` | One-off scripts from earlier phases, kept for provenance; not runnable as-is. |
| `work/` | Gitignored local state: virtual environments, Graphiti config/outbox, scratch runs. |

Installed virtual environments, third-party repository clones, model weights, credentials, private Graphiti service configuration/outbox, and caches are excluded from the repository. JSON/SQLite simulation checkpoints are included; the derived Neo4j/embedding index can be rebuilt.

## Setup

Use Python 3.12 or newer. From the repository root:

```sh
python3 -m venv work/profile-env
work/profile-env/bin/python -m pip install -e .
```

The engine core needs only the standard library; numpy/pandas/pyarrow/scipy (pinned in `requirements.txt`) are used for sampled and inherited personality profiles. Without installing, run commands from the repository root so `devsim` is importable.

## Run

Engineering checks and the core demo:

```sh
work/profile-env/bin/python -m checks.run_all            # --skip graphiti without the local graph service
```

A local engineering run without an LLM or graph service:

```sh
work/profile-env/bin/python -m devsim.simulate \
  --scripted --household --caregivers 2 --years 7 \
  --out runs/scripted/MY_NEW_SCRIPTED_RUN
```

Use a fresh output directory for each run. The scripted provider checks software behavior and skips model-only cognition; it is not a language-model result.

For actual-model runs, start or forward the selected local 27B endpoint to `http://127.0.0.1:18081`. The historical SSH details are in [RESUME.md](docs/RESUME.md); adapt them to your own machine rather than assuming the original socket exists. Set up optional Graphiti retrieval using [the graph guide](services/graphiti-local/README.md).

A short actual-model household scene:

```sh
work/profile-env/bin/python -m devsim.household_example \
  --graphiti --out runs/live/MY_NEW_HOUSEHOLD_RUN
```

Interview agents in a saved checkpoint, either over a frozen copy (no effect on the run) or in-world (a new checkpoint); see [the interview guide](docs/INTERVIEW_IMPLEMENTATION.md):

```sh
work/profile-env/bin/python -m devsim.interview diagnostic runs/live/household-live/run/world.json \
  --agent alex --agent noor --question "What happened at home this evening?" --out work/my-interview
```

Draft a scenario from a plain-language setting with the local model, review it, then compile it into a world and policy; see [the authoring guide](docs/AUTHORING_IMPLEMENTATION.md):

```sh
work/profile-env/bin/python -m devsim.author draft "SETTING TEXT" --api http://127.0.0.1:8081 --out work/my-draft
work/profile-env/bin/python -m devsim.author compile work/my-draft/scenario.json --out work/my-scenario
```

Write an evidence-linked report on a checkpoint: read-only tools gather evidence, then the local model writes typed, cited claims; see [the report guide](docs/REPORT_IMPLEMENTATION.md):

```sh
work/profile-env/bin/python -m devsim.report runs/live/author-live/compiled-graphiti/run/world.json \
  --initial runs/live/author-live/compiled-graphiti/initial.json --api http://127.0.0.1:8081 --out work/my-report
```

Open a run in the researcher cockpit, from one agent's perspective or the researcher view; `--serve PORT` instead of `--out` gives a live loopback page; see [the cockpit guide](docs/COCKPIT_IMPLEMENTATION.md):

```sh
python3 -m devsim.cockpit runs/live/author-live/compiled-graphiti/run --out work/cockpit.html
```

## Evidence and limits

The [verification manifest](runs/verification/environment-verification.json) records 241 named engineering checks across 18 suites, all run on the cluster machine, plus 12 core checks; see [BUILD_STATE](docs/BUILD_STATE.md) for which ran where. The phase guides distinguish actual 27B evidence, scripted runs and source-version boundaries.

This is an implemented research scaffold, not demonstrated human replication or measured improvement in predicting real people. Scientific coefficients, instrument mappings, factual reliability and population-scale behavior remain research questions. Preserved research reports and third-party datasets retain their original attribution and terms; their inclusion does not establish an open-source license for them or for this project.
