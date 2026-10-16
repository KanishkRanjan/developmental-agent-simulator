# Plan execution: actual 27B results

> **Historical record.** Moved here in the October 2026 restructure; content is unchanged apart from link targets. Counts and scope are as of writing. Commands and bare file names refer to the old `outputs/agent_engine/` layout; see [the path map](README.md#old-to-new-paths).

16 October 2026. Both fixtures used the existing local HauhauCS 27B and the current checked source files. No implementation changes were necessary during this live test.

| Fixture | Outcome | Requests |
|---|---|---|
| Combined default policy | One resolved action. The task failed, the goal stayed active at progress 0, the bound step remained pending, and replanning was requested. | 7 total; 1 plan generation; 0 repairs. |
| Controlled draft/review | Two resolved actions: draft then review. Both completed steps cite received outcome events; the goal reached progress 1 and completed. | 10 total; 2 plan generations; 0 repairs. |

Both worlds saved/restored identically from JSON and SQLite, retained no pending activities, and recorded outcomes later than their intentions. Runtime source hashes match the verification manifest. Eleven local suites remain at 149 checks, plus twelve core checks.

The success fixture intentionally supplies one eligible action per stage and guarantees successful outcomes. It verifies wiring and prerequisite progression, not personality choice, planning quality or human predictive validity. The default-policy fixture offers alternatives and allows failure. An action binding remains a model judgment within controller-authored scenario actions, costs and progress rules.

[Machine-readable phase evidence](../../runs/verification/goal-plans-verification.json) · [Default-policy integrity](../../runs/live/goal-plans-live/run/integrity-checks.json) · [Success-fixture integrity](../../runs/live/goal-plans-success-live/run/integrity-checks.json) · [Current implementation map](CURRENT_STATUS.md)
