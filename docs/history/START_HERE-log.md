# Start here: continuing the agent simulator

> **Historical record.** Moved here in the October 2026 restructure; content is unchanged apart from link targets. Counts and scope are as of writing. Commands and bare file names refer to the old `outputs/agent_engine/` layout; see [the path map](README.md#old-to-new-paths).

GitHub: [private project repository](https://github.com/KanishkRanjan/developmental-agent-simulator). [Backup scope](../GITHUB_BACKUP.md) records included artifacts and runtime exclusions; the repository-root README gives fresh-clone setup commands.

## Latest: household environment and conversation layer

[Household implementation](../HOUSEHOLD_IMPLEMENTATION.md) is the newest phase. Explicit rooms/audibility, private multi-turn conversation, waking windows/response intervals and elapsed calendar reservations now connect to the existing scheduler, memory/mood and optional cognition/development paths. Use `household_example.py` for a short scene or `simulate.py --household` for fresh combined policies; archived policies remain unchanged.

Thirteen suites pass **185 named checks plus twelve core checks**, including 24 new household checks. The actual HauhauCS 27B scene completed four independent turns/23 calls with no Graphiti fallback; a closed-room person received none of it. The final seven-year scripted combined run completed 61 actions including 16 conversation turns. [Verification](../../runs/verification/household-verification.json) and the implementation guide record the source-version boundary: optional crystallization/sample-clock refinements are locally checked, while the preserved live trace precedes them. These are engineering results, not measured human fidelity. Automatic scenario authoring, interviews, report generation and a GUI remain proposed.

Earlier milestone sections below are historical and keep their original scope.

Updated 16 October 2026.

## Current implementation map

[CURRENT_STATUS.md](CURRENT_STATUS.md) is the current five-layer map and executable-planning phase status. All five formerly missing categories now exist. Current verification is 161 checks plus twelve core checks, including the local Graphiti retrieval layer and actual 27B runs. See [the live report](GOAL_PLANS_LIVE_REPORT.md).

## Latest storage implementation

[Local Graphiti implementation and MiroFish adaptations](../GRAPHITI_IMPLEMENTATION.md) is the newest phase. Read [the setup guide](../../services/graphiti-local/README.md) for local services, commands, privacy boundaries and scale limits. No Zep subscription is used.

## Latest verification

Read [the fresh test report](LATEST_TEST_REPORT.md): 139 regression checks, twelve core checks, current infant capability fix, fresh 27B traces and a separate 100-year scripted run. Older 136-check milestones below are preserved history.

## Read first

The latest software pass is [Full build state](FULL_BUILD_STATE.md); the [review-later guide](REVIEW_LATER.md) has the one-command launcher and evidence. Earlier integrated/developmental notes retain their historical scope.

1. [Persistent build state](BUILD_STATE-log.md): verified results, decisions and runnable files.
2. [Source-to-code audit](../source-to-code-audit.md): implemented, partial, missing and unresolved mechanisms. This supersedes older broad completion claims.
3. [Engine README](../engine.md): usage and example scope.
4. [Preserved sources and reference guide](../../research/sources/README.md): all ten reports and searchable text, with original hashes retained. The full raw Claude transcript is not archived locally; its correct share link and review are recorded here.
5. [Developmental continuation](../development-notes.md): attachment, crystallization, maturation, inheritance, lazy activation, event-rate policies and context guards, including their assumptions and actual-model checks.
6. [Latest live completion and continuation steps](../RESUME.md): the resumed scenario reached age twenty-two; the final checkpoint and remaining scope are recorded.

Consult [the design inventory](../design/design-coverage-ledger.md), [conversation review](../design/full-conversation-review.md), and [source manifest](../source-audit-manifest.json) for the relevant mechanism before extending it. The source material need not be reread in full for every session; revisit the relevant passages when an interpretation is uncertain.

## Decisions to preserve

- Build the integrated social simulation system first, then perform comparative evaluation. Continue basic correctness and integration checks during implementation.
- Use the existing local 27B model API. Fine-tuning, LoRA, activation steering and 9B comparisons are excluded by the user's later decisions.
- Keep numerical personality facets internally; send selected behavioral language to the model.
- Preserve explicit information flow, private subjective memories, original event provenance, and distinctions between testimony, acquaintance and verified events.
- Do not restore the numerical reconsolidation design the user rejected.
- Label developmental rates and thresholds as provisional. Do not invent improvement percentages or claim faithful human replication.
- Fix clear equation errors during implementation, document the correction and source, and retain the uncertainties around empirical coefficients.

## Current scope

The accepted developmental-engine layers now have connected software paths, including full available-corpus indexed retrieval, ambiguous references and heard reminders, open-value structured biographies, actual elapsed activities, configurable temporary variability/cultural expression, self-set goal opportunities, conserved transfers, exogenous hazards, newborn opportunities/hazards and SQLite provenance/checkpoint storage. `simulate.py` initializes and runs the combined policy from infancy onward. It uses the existing local HauhauCS 27B, with no smaller fallback.

Ten check suites (136 named checks) and the twelve-check core demo pass. An 85-year scripted lifecycle completed with 209 resolved actions and a new generation. Separate adult and infant 27B fixtures completed. [Full build state](FULL_BUILD_STATE.md) distinguishes provider/fixture/source versions and gives exact evidence. These are implementation checks, not human-realism or predictive-improvement results.

Empirical coefficients, child norms, instrument/TGA mapping and learned psychological/cultural/economic laws remain research boundaries. Structured chronology is implemented; unrestricted semantic consistency is not guaranteed. Do not claim a fitted clinical simulator, missing research report or every scientific proposal has been validated. User choices and source uncertainty remain authoritative.

## Continuing safely

Read the relevant code and source section before changing a mechanism. Use the saved build state for cluster connection details, then check actual connectivity; an old successful connection is not proof it remains active. Preserve existing snapshots and archived policies. Update the build state and audit after meaningful changes, with what ran and what remains unfinished.

The project-root `AGENTS.md` directs agents working in this folder here. A session opened in a different folder will need this guide supplied explicitly; these files do not provide automatic memory across unrelated chats.
