# Graphiti and MiroFish storage/retrieval review

**Implementation follow-through:** the recommendation below has now been implemented in a bounded private-view index. Read [the current implementation report](../GRAPHITI_IMPLEMENTATION.md). This review retains its original pre-implementation wording and source findings.

16 October 2026. This is a source-code review and architectural recommendation, not an implemented migration or measured improvement. User decision: **no Zep Cloud, paid subscription, or hosted inference dependency**.

## Findings

Upstream MiroFish HEAD checked against the existing local checkout: `7657031ac01184afe2cb220f5ee3545573b5e843`. Its dependency manifest includes Zep Cloud and CAMEL OASIS. Its runner uses SQLite simulation files; its graph service builds/queries Zep Cloud graphs. Therefore MiroFish's “GraphRAG construction” wording is not evidence of a second database named GraphRAG or use of Microsoft's GraphRAG package. These findings refer to upstream, not independent self-hosted forks.

Primary code:

- [Dependencies](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/pyproject.toml)
- [SQLite runner](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/scripts/run_twitter_simulation.py)
- [Search tools](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/zep_tools.py)
- [Graph ingestion](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/zep_graph_memory_updater.py)

Graphiti is the open-source temporal graph framework; a backend such as Neo4j or FalkorDB stores its graph. Zep Cloud is a managed offering and is not required to self-host Graphiti. GraphRAG describes a graph-based retrieval approach and is also the name of Microsoft's separate library. Microsoft's library extracts graph/community summaries for corpus-level and entity-level questions; it is not a database engine. See [Graphiti overview/backends](https://help.getzep.com/graphiti/getting-started/overview), [repository/license](https://github.com/getzep/graphiti), and [Microsoft GraphRAG](https://microsoft.github.io/graphrag/).

## What could improve our engine

Our current `retrieval.py` rebuilds an in-memory FTS5 index over currently available private representations for each cognitive event, uses model query expansion, and then bounded model selection. `graph_store.py` preserves checkpoints and normalized provenance, but its graph is an audit facility rather than the runtime recall engine. No vector index, runtime graph traversal or Graphiti integration is currently installed.

| Candidate | Expected benefit; not yet measured here |
|---|---|
| Persistent hybrid retrieval | Combine lexical matches with embeddings and graph neighbors, rather than relying on paraphrases to make related experiences share keywords. |
| Relationship-aware expansion | Follow agent-known people, events, places and evidence links to find related episodes. Graph proximity may suggest relevance; it does not establish causation. |
| Temporal fact versions | Preserve changing jobs/relationships and source episodes. Keep historical facts distinct from current claims. |
| Separate analyst search tools | MiroFish's quick search, question decomposition/entity-chain search, and current-versus-historical panorama are useful patterns for a research interface. Global analyst visibility must not become agent knowledge. |
| Background indexing discipline | Adapt queueing, bounded batches, event timestamps, ingestion status and explicit failures. Use stable event IDs and a durable outbox so graph failure cannot lose or duplicate canonical events. |

MiroFish already performs query decomposition and cross-encoder-backed search; our engine already has limited query expansion. The substantive additions would be persistent embeddings/graph traversal, temporal queries and an analyst-facing search interface—not simply renaming our existing retrieval “GraphRAG.” See [Graphiti search recipes](https://help.getzep.com/graphiti/working-with-data/searching).

## Recommended local architecture

Keep SQLite/JSON as the canonical transactional simulation record and checkpoint. Add Graphiti over one self-hosted graph backend as a derived, rebuildable retrieval index. Keep the 27B API for language operations and use an explicitly configured local embedding endpoint. No Zep account is needed. Graphiti's defaults include hosted providers, so all clients must be configured explicitly; its generic OpenAI-compatible chat client can use local services. Compatibility, structured outputs, latency and memory use still need checking against our actual llama.cpp setup. See [provider configuration](https://help.getzep.com/graphiti/configuration/llm-configuration).

The graph service, embedding model and additional extraction work consume local resources. This is subscription-free infrastructure, not zero computation cost. There is no demonstrated retrieval accuracy or performance gain in our engine yet.

Required adaptation to preserve this design:

- Derive a private graph namespace from simulation/branch/agent IDs. Application code controls every query scope; namespace filters are not authorization by themselves. See [Graphiti namespacing](https://help.getzep.com/graphiti/core-concepts/graph-namespacing).
- Keep canonical world events separate from subjective received accounts, beliefs and interpretations. A testimony edge is a claim, not automatic world truth; graph extraction must not merge conflicting people solely by name.
- Retain stable source IDs and version provenance. Record event time, agent learning time and physical ingestion time separately; do not substitute the real clock for simulated time.
- Index accessible representations/gists appropriately and reapply current access rules before any retrieved content reaches a model. Neither graph edges, summaries, embeddings nor reranking may expose another person's memories or resurrect lost original detail.
- Temporal fact expiry is not psychological forgetting. Likewise a later reinterpretation must not erase immutable earlier observations or silently resolve uncertainty as truth.
- Preserve failed attempts as experiences. MiroFish's public activity updater skips unsuccessful activities; copying that behavior would discard psychologically relevant failed experiences in this engine.

Recommendation: adopt local Graphiti as a candidate retrieval infrastructure upgrade, preserving our developmental/mood/memory policies and canonical checkpoints. Use Microsoft's GraphRAG separately only if corpus-wide research analysis becomes a concrete need. Installing both is not currently justified. No service or dependency was installed by this review.
