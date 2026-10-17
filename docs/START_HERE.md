# Start here

GitHub: [private project repository](https://github.com/KanishkRanjan/developmental-agent-simulator). The repository-root [README](../README.md) has setup and run commands.

## Read in this order

1. [BUILD_STATE.md](BUILD_STATE.md): current phase, implementation map, verification and key evidence runs.
2. [source-to-code-audit.md](source-to-code-audit.md): implemented, partial, missing and unresolved mechanisms. This is authoritative over older completion claims.
3. [research/sources/README.md](../research/sources/README.md): the ten preserved research reports, searchable text and mechanism references.
4. [development-notes.md](development-notes.md): developmental mechanisms, equations, checks and explicit limits.
5. [RESUME.md](RESUME.md): saved checkpoints, model-server connection and continuation commands.
6. [integrated-build-notes.md](integrated-build-notes.md): cognition, history, planning and world policies, assumptions and source-version boundaries.

Phase guides: [environment](ENVIRONMENT_IMPLEMENTATION.md), [cockpit](COCKPIT_IMPLEMENTATION.md), [reports](REPORT_IMPLEMENTATION.md), [scenario authoring](AUTHORING_IMPLEMENTATION.md), [interviews](INTERVIEW_IMPLEMENTATION.md), [household](HOUSEHOLD_IMPLEMENTATION.md), [sleep consolidation](SLEEP_IMPLEMENTATION.md), [society layer](SOCIETY_LAYER_IMPLEMENTATION.md), [local Graphiti](GRAPHITI_IMPLEMENTATION.md) (setup in [services/graphiti-local](../services/graphiti-local/README.md)), and the [engine reference](engine.md). Design background is in [docs/design/](design/): the [design coverage ledger](design/design-coverage-ledger.md), the [conversation review](design/full-conversation-review.md) and the [source manifest](source-audit-manifest.json). Earlier milestone documents are in [docs/history/](history/README.md), along with a map from old to new file paths.

The source material need not be reread in full for every session; revisit the relevant passages when an interpretation is uncertain.

## Decisions to preserve

- Build the integrated social simulation system first, then perform comparative evaluation. Continue basic correctness and integration checks during implementation.
- Use the existing local 27B model API. Fine-tuning, LoRA, activation steering and 9B comparisons are excluded by the user's later decisions.
- Keep numerical personality facets internally; send selected behavioral language to the model.
- Preserve explicit information flow, private subjective memories, original event provenance, and distinctions between testimony, acquaintance and verified events.
- Do not restore the numerical reconsolidation design the user rejected.
- Label developmental rates and thresholds as provisional. Do not invent improvement percentages or claim faithful human replication.
- Fix clear equation errors during implementation, document the correction and source, and retain the uncertainties around empirical coefficients.

## Continuing safely

Read the relevant code and source section before changing a mechanism. Check actual connectivity to the model server; an old successful connection is not proof it remains active. Preserve existing run directories and archived policies: write new runs to a fresh directory, and resume a checkpoint only with its own archived policy and provider. Update [BUILD_STATE.md](BUILD_STATE.md) and the audit after meaningful changes, with what ran and what remains unfinished.

The project-root `AGENTS.md` directs coding agents here. A session opened in a different folder will need this guide supplied explicitly.
