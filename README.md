# Developmental Agent Simulator

A research prototype for persistent agents with correlated personality facets, private memory, mood, goals, developmental change, family relationships, and a shared simulation environment. Local language decisions use the selected HauhauCS 27B model through an OpenAI-compatible local API. Fine-tuning, activation steering, hosted inference and paid Zep services are outside the current setup.

Start with [the continuation guide](outputs/START_HERE.md) and [the source-to-code audit](outputs/agent_engine/source-to-code-audit.md). The latest implemented layer is [household interaction](outputs/agent_engine/HOUSEHOLD_IMPLEMENTATION.md): rooms, audibility, multi-turn dialogue and availability. Older milestone documents retain their original scope.

## Included

- `outputs/agent_engine/`: the engine, scenario policies, executable checks, preserved source reports, checkpoints and recorded model runs.
- `outputs/`: personality sampling, earlier experiments, design reviews and research notes.
- `work/`: selected research scripts, datasets, papers and intermediate experiment records. These are historical working artifacts; some contain original machine paths and should not be run indiscriminately.
- `AGENTS.md`: continuation instructions for coding agents.

Installed virtual environments, third-party repository clones, model weights, credentials, private Graphiti service configuration/outbox, and caches are excluded. JSON/SQLite simulation checkpoints are included; the derived Neo4j/embedding index can be rebuilt. Historical absolute paths and source hashes remain unchanged to preserve provenance.

## Setup

Use Python 3.12 or newer. From the repository root:

```sh
python3 -m venv work/profile-env
work/profile-env/bin/python -m pip install -r requirements.txt
```

Run a local engineering demonstration without an LLM or graph service:

```sh
work/profile-env/bin/python outputs/agent_engine/simulate.py \
  --scripted --household --caregivers 2 --years 7 \
  --out outputs/agent_engine/MY_NEW_SCRIPTED_RUN
```

Use a fresh output directory for each run. The scripted provider checks software behavior and skips model-only cognition; it is not a language-model result.

For actual-model runs, start or forward the selected local 27B endpoint to `http://127.0.0.1:18081`. The historical SSH details are in [RESUME.md](outputs/agent_engine/RESUME.md); adapt them to your own machine rather than assuming the original socket exists. Set up optional self-hosted Graphiti/Neo4j/BGE retrieval using [the graph guide](outputs/agent_engine/graphiti-local/README.md). It requires Docker and `uv`; its isolated dependencies are pinned separately.

A short actual-model household scene:

```sh
work/profile-env/bin/python outputs/agent_engine/household_example.py \
  --graphiti --out outputs/agent_engine/MY_NEW_HOUSEHOLD_RUN
```

## Evidence and limits

The saved [verification manifest](outputs/agent_engine/final-engineering-verification.json) records 185 named engineering checks across 13 suites, plus 12 core checks. The [household report](outputs/agent_engine/HOUSEHOLD_IMPLEMENTATION.md) distinguishes actual 27B evidence, scripted runs and source-version boundaries.

This is an implemented research scaffold, not demonstrated human replication or measured improvement in predicting real people. Scientific coefficients, instrument mappings, factual reliability and population-scale behavior remain research questions. Preserved research reports and third-party datasets retain their original attribution and terms; their inclusion does not establish an open-source license for them or for this project.
