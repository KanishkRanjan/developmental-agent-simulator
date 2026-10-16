# Local Graphiti setup and use

This project now uses **Graphiti 0.31.1 + self-hosted Neo4j + local BGE embeddings** as an optional private retrieval index. There is no Zep Cloud account, subscription, hosted embedding endpoint or hosted reranker. The 27B language model remains on the user's cluster. Graphiti/embedding dependencies live in an isolated Python 3.12 environment; the engine itself keeps its earlier environment.

## Start

From the project root:

```sh
work/profile-env/bin/python outputs/agent_engine/graphiti-local/start.py
```

For a clean installation with Docker and uv available:

```sh
python3 outputs/agent_engine/graphiti-local/start.py --setup
```

First-time setup needs the authorized local 27B endpoint at `127.0.0.1:18081` to choose its model ID. The existing configuration can start graph retrieval without that endpoint; language decisions/deep query decomposition still need the cluster. Setup pins dependencies and BGE model revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`. The local embedding model is `BAAI/bge-small-en-v1.5`, CPU-only, 384 dimensions. Its limited token window is not exhaustive understanding of very long memories.

The dedicated Docker Compose project is `developmental-graphiti`. Neo4j Bolt and Browser bind only to `127.0.0.1:17687` and `127.0.0.1:17474`. The browser is at http://127.0.0.1:17474. Authentication is disabled for this loopback-only development database; it is not a multi-user security boundary. The separate HTTP bridge binds only to `127.0.0.1:18082` and requires a generated local bearer token. Graphiti/HF/Neo4j usage telemetry is disabled by configuration. Initial package/image/model downloads need internet; runtime graph/embedding operations stay local.

Private configuration/token, durable outbox, embedding cache, service PID and logs live under `work/graphiti-data/`; do not copy that token into model context, checkpoint policy or chat. Neo4j data lives in the dedicated Docker volume. Local paths can be relocated by regenerating setup/configuration. `AGENT_GRAPHITI_CONFIG` may point an engine client to another explicit local configuration file.

## Simulation

New live combined scenarios enable the graph path and start the existing service automatically:

```sh
work/profile-env/bin/python outputs/agent_engine/simulate.py \
  --years 22 --out outputs/agent_engine/MY_GRAPH_RUN
```

Use a fresh output directory. `--no-graphiti` selects the earlier private FTS retrieval. `--scripted` skips language cognition and deliberately disables graph indexing to avoid producing unused background view caches. Existing archived policies retain their original behavior; do not change a saved fingerprint to retrofit this layer into an old trajectory.

For a newly authored policy, set `cognition.graphiti_retrieval: true`. The controller assigns a persistent simulation namespace. On checkpoint save it publishes current private views into a durable SQLite outbox without waiting on the graph service. The background worker builds each immutable view with stable IDs, cached local embeddings and Graphiti's typed node/edge classes. Real Graphiti `search_` combines BM25, cosine similarity and BFS using reciprocal-rank fusion. The existing local 27B then selects relevant supplied memories; the engine performs actual recall separately.

Graph startup responses are retried within the indexing deadline. If the graph is unavailable or indexing fails, semantic recall may use the prior private FTS route, recording `fallback_private_fts` and its reason in `retrieval_focus.graph_retrieval`. It never falls back to another person's graph, a hosted service or a smaller language model. An indexing failure does not undo an already saved canonical checkpoint. Each failed job retains its error; an explicit repeat request can retry deterministic upserts.

## Researcher tools inspired by MiroFish

```sh
work/profile-env/bin/python outputs/agent_engine/graph_tools.py CHECKPOINT.json \
  --owner alex --mode quick --query 'support after an employment setback'

work/profile-env/bin/python outputs/agent_engine/graph_tools.py CHECKPOINT.json \
  --owner alex --mode deep --query 'How do earlier experiences connect to this goal?'

work/profile-env/bin/python outputs/agent_engine/graph_tools.py CHECKPOINT.json \
  --owner alex --mode panorama

work/profile-env/bin/python outputs/agent_engine/graph_tools.py CHECKPOINT.json \
  --owner alex --mode chains --query 'work and friendships'
```

`--out NEW_FILE.json` saves a result without overwriting earlier evidence. These tools do not trigger recall, rehearsal or mood changes and do not modify checkpoints. Quick/chain tools use the real graph. Deep mode uses the local 27B for bounded subquestions, scoped graph search and rank fusion. Panorama inspects current accessible meanings and retained prior interpretation versions from the canonical checkpoint. It does not reconstruct what the agent knew at an arbitrary past time, and researcher output is not automatically given to agents. Relationship chains are associations, not demonstrated causes.

## Representation and fidelity boundaries

Unlike MiroFish's public activity graph, this index stores a separate private view for each agent. Only currently available detail/gists and allowed reference/topic links enter a snapshot. Retrieved event IDs are checked against the engine's current private view before any text is sent to an LLM. Older graph snapshots cannot be searched by the normal client simply to restore forgotten detail. Snapshot namespaces also include simulation scope, owner, view time and representation content, isolating rollback/fork states.

Source event day, simulated view day and physical ingestion time remain separate. Graphiti validity/reference timestamps describe the indexed view time; attributes retain the source event day. A newer interpretation is not retrodated as an earlier belief. Source and subjective meaning remain explicit; a testimony representation does not become a world fact. Failed attempts remain legitimate experiences.

The service deliberately uses existing engine IDs and typed graph writes rather than letting unrestricted extraction merge identities or overwrite beliefs. Graphiti's autonomous LLM extraction, global community summaries and automatic claim invalidation are not enabled. World truth and the complete resumable history remain in SQLite/JSON.

Current ceiling: immutable view graphs duplicate nodes/edges as histories grow. Embeddings are cached, but a long live population run will need lease-aware cache compaction and profiling. The service serializes indexing/search to protect a small local deployment; it is not a production multi-user service or a population-scale performance claim. Stopping the service must be done when not expecting live graph recall; `docker compose -p developmental-graphiti -f outputs/agent_engine/graphiti-local/compose.yaml stop` stops only this project's graph database and retains its data volume.

[Implementation evidence](../GRAPHITI_IMPLEMENTATION.md) records exact tests, source versions and live traces.
