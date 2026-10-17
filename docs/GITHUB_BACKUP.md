# GitHub repository

The project is backed up in the **public** repository [KanishkRanjan/developmental-agent-simulator](https://github.com/KanishkRanjan/developmental-agent-simulator), on branch `main`. Earlier versions of this file called it private; on 16 October 2026 GitHub reported it as public, and the owner chose to keep it public. Everything committed (code, preserved research reports, run traces) is visible to anyone.

The initial project snapshot is commit `33c3be6`. It includes 592 files: the engine, research reports, source text, experiments, checkpoints, model request traces, verification manifests, continuation guides and selected historical working scripts/data. The repository README gives installation and execution commands; `requirements.txt` records the four installed main-runtime dependency versions. Graphiti retains its separate dependency lock.

Excluded: credentials and generated service authentication, installed environments, model weights and embedding downloads, third-party repository clones, Python caches, private Graphiti outbox/logs and the derived Neo4j Docker volume. The JSON/SQLite simulation checkpoints are included; the derived graph index can be rebuilt using the preserved setup scripts. The original local files/services remain in place.

Historical paths, hashes, failed attempts and prior test results remain unchanged. This publication did not change engine code or rerun the simulation tests. See [the latest implementation and verification scope](HOUSEHOLD_IMPLEMENTATION.md) for what was actually tested.

The repository was later restructured into `devsim/`, `checks/`, `docs/`, `runs/`, `research/`, `services/` and `archive/`; the 592-file description above refers to the original `outputs/` and `work/` layout. See [the path map](history/README.md#old-to-new-paths).

New local changes need a new commit and push; this is not automatic synchronization.

On the cluster machine, `git` pushes over HTTPS with the `gh` login (`gh auth setup-git`), and commits use the repository-local identity Kanishk Ranjan. The restructure and the authoring, report, cockpit, environment and compaction work were pushed as `9a9dfec` on 16 October 2026.
