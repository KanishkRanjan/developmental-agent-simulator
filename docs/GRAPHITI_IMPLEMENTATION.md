# Local Graphiti implementation and MiroFish adaptations

16 October 2026. The local index is implemented and verified. No Zep Cloud subscription or hosted embedding/reranking service is used. This supersedes the earlier review's “not installed” status, not its source distinctions or empirical limits.

## Implemented

| Component | Runtime behavior |
|---|---|
| Graphiti / Neo4j | Graphiti 0.31.1 SDK typed nodes/edges and actual hybrid `search_` over Neo4j. The dedicated container has a persistent volume and loopback-only ports. |
| Embeddings | Pinned BAAI BGE-small-en-v1.5 runs on local CPU; existing 27B remains the language model. Graphiti/HF/Neo4j usage telemetry is disabled. |
| Runtime recall | `cognition.semantic_recall` obtains graph candidates, verifies current owner/access membership, then asks the existing local model to select memories. Only explicit recall can rehearse or affect mood. |
| Background updates | `Engine.save` publishes current private representations to a durable local SQLite outbox. A worker builds immutable view graphs with deterministic IDs; retries upsert rather than duplicating events. |
| Isolation / forgetting | Each view is scoped by simulation, owner, view time and representation contents. Old views cannot resurrect lost original detail in current runtime retrieval. Testimony/source/interpretation remain separate from world truth. |
| Researcher tools | Quick search; local-model subquestion/deep search and rank fusion; current/prior interpretation panorama; relationship-chain output. They inspect one private checkpoint view without creating cognitive events. |
| Recovery | Queue survives a stopped service; startup waits and explicit private-FTS fallback avoid losing simulation checkpoints. Every fallback is recorded in retrieval diagnostics. |

These adapt patterns from [upstream MiroFish's search tools](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/zep_tools.py) and [graph-memory updater](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/zep_graph_memory_updater.py). They are original integrations into this engine, not wholesale copies of MiroFish or its public/shared graph policy. Failed experiences are retained. Researcher visibility is not agent knowledge.

## Evidence

- Twelve suites: **161 named checks**, plus the **twelve-check core demonstration**. [Manifest](../runs/verification/final-engineering-verification.json).
- [Graph checks](../checks/results/graphiti-engineering-checks.json): actual local Graphiti/Neo4j/BGE search, namespaces, hidden detail exclusion, durable publication, duplicate reuse, read-only tools, runtime gist behavior, outage fallback, foreign-ID rejection and startup waiting. Model selection/deep-query structure are stubbed in this suite; actual model evidence is separate.
- [Final 27B fixture](../runs/live/graphiti-live/run-verified/integrity-checks.json): **five requests, one resolved action, 35.846 seconds, zero repairs, no graph fallback**. Alex selected the seeded dismissal and supportive conversation memories; Bea's private episode stayed out of Alex's model context. The action outcome was later than its intention; earlier episodes survived and JSON/SQLite restored identically.
- [Restart probe](../runs/probes/graphiti-restart-probe-final/integrity-checks.json): checkpoint/outbox written while service was stopped; queued view was indexed after restart. This is an intentional idle stop/start, not a mid-write crash injection.
- [Deep search example](../runs/live/graphiti-live/deep-search.json), [panorama](../runs/live/graphiti-live/panorama.json), [chains](../runs/live/graphiti-live/chains.json): actual local research-tool outputs. The deep example called the 27B model for query decomposition. These earlier tool examples precede the final simulated-view-time refinement; the final graph suite tests the current version.
- `graphiti-live/run-final` records a service-start race causing a disclosed private-FTS fallback. Bounded 503-startup waiting was added and checked, and the final replay used the graph successfully. `graphiti-live/run` preserves the earlier successful graph wiring before later refinements. Initial SDK setup errors remain in local logs/outbox history.

The final live fixture uses seeded adult memories, neutral synthetic traits, omitted childhood, one eligible activity and guaranteed success. It is wiring evidence, not personality discrimination, a full live lifespan or measured improvement in human prediction.

## Boundaries retained

SQLite/JSON remains the canonical transactional history and checkpoint. Graphiti is a derived retrieval index. Typed writes preserve supplied engine IDs and meanings; autonomous Graphiti extraction, automatic belief invalidation, global communities and identity merging are not enabled. Source event day, simulated view day and physical indexing time remain distinct; a revised meaning is not retrodated as an original belief.

Panorama reports checkpoint interpretation history; it does not reconstruct an arbitrary historical cognitive state. Graph connections are not proof of causation. Local embedding context is finite. Immutable view caches trade storage for simple rollback isolation. Lease-aware compaction (16 October 2026; [setup guide](../services/graphiti-local/README.md#cache-compaction)) deletes superseded views, which are re-derived on demand; it has not been profiled at population scale, and the embedding cache is not compacted. No performance or accuracy gain is claimed by these engineering checks.

## Run / continue

[Setup and commands](../services/graphiti-local/README.md). New live `simulate.py` scenarios enable and start the graph service. `--no-graphiti` uses the earlier private FTS route; scripted scenarios skip graph cognition/indexing. Existing saved policies keep their original fingerprints. The local graph daemon/container remain running; no language-inference test client remains active.

[Machine-readable phase report](../runs/verification/graphiti-verification.json) and [current status map](history/CURRENT_STATUS.md) are the continuation entry points.
