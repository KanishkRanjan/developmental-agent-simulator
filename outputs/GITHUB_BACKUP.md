# GitHub repository

The project is backed up in the private repository [KanishkRanjan/developmental-agent-simulator](https://github.com/KanishkRanjan/developmental-agent-simulator), on branch `main`.

The initial project snapshot is commit `33c3be6`. It includes 592 files: the engine, research reports, source text, experiments, checkpoints, model request traces, verification manifests, continuation guides and selected historical working scripts/data. The repository README gives installation and execution commands; `requirements.txt` records the four installed main-runtime dependency versions. Graphiti retains its separate dependency lock.

Excluded: credentials and generated service authentication, installed environments, model weights and embedding downloads, third-party repository clones, Python caches, private Graphiti outbox/logs and the derived Neo4j Docker volume. The JSON/SQLite simulation checkpoints are included; the derived graph index can be rebuilt using the preserved setup scripts. The original local files/services remain in place.

Historical paths, hashes, failed attempts and prior test results remain unchanged. This publication did not change engine code or rerun the simulation tests. See [the latest implementation and verification scope](agent_engine/HOUSEHOLD_IMPLEMENTATION.md) for what was actually tested.

New local changes need a new commit and push; this is not automatic synchronization.
