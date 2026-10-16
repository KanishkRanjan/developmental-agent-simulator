# Current implementation status

## Latest: household environment and conversation layer

[Household implementation](HOUSEHOLD_IMPLEMENTATION.md) is the newest phase. Explicit rooms/audibility, private multi-turn conversation, waking windows/response intervals and elapsed calendar reservations now connect to the existing scheduler, memory/mood and optional cognition/development paths. Use `household_example.py` for a short scene or `simulate.py --household` for fresh combined policies; archived policies remain unchanged.

Thirteen suites pass **185 named checks plus twelve core checks**, including 24 new household checks. The actual HauhauCS 27B scene completed four independent turns/23 calls with no Graphiti fallback; a closed-room person received none of it. The final seven-year scripted combined run completed 61 actions including 16 conversation turns. [Verification](household-verification.json) and the implementation guide record the source-version boundary: optional crystallization/sample-clock refinements are locally checked, while the preserved live trace precedes them. These are engineering results, not measured human fidelity. Automatic scenario authoring, interviews, report generation and a GUI remain proposed.

Earlier milestone sections below are historical and keep their original scope.

This is the current overview. Older milestone notes preserve historical missing-work lists; those lists do not describe the current code.

| Requested layer | Current implementation | Remaining limit |
|---|---|---|
| Semantic recall, gist-only access, interference | `cognition.views` / `semantic_recall`, local Graphiti/Neo4j/BGE hybrid retrieval and explicit private-FTS fallback; access threshold and topic-fan penalty remain in force. | Retrieval is bounded and not guaranteed exhaustive; thresholds are provisional. |
| Evidence-based reinterpretation and self-narrative | `cognition.reflect`: retain/defer/revise with received evidence, preserved originals/versions, optional narrative updates. | Evidence-ID validity does not prove semantic correctness. |
| Autonomous recall, replanning, budgets, habits | Scheduled `cognition.ruminate`, reflection plan versions, `calendar_time.py`, `life_policy.py`; new `goal_plans.py` binds ordered steps to canonical actions and received outcomes. | The new goal-execution layer has local/scripted checks and actual 27B failure/success fixtures. Scenario action libraries and progress amounts remain controller-authored. |
| Constrained family/history generation and social questions | Parent-first/inherited initialization, lazy activation, open structured biography constraints, listener-local references and transmitted probe questions. | Generated prose has no unrestricted coherence guarantee; asking does not establish truth or acquaintance. |
| World transitions, births, newborn opportunities | `life_policy.apply_effects`, persistent world/hazard queues, `Lifetime._register_births` and dynamic newborn opportunities/hazards. | Explicit scenario processes, not calibrated demography/economics/clinical laws. |

All five have runtime paths. They are not five absent modules waiting to be started. Having runtime paths is also not a claim that every proposed scientific detail is settled.

## Latest phase: plans that can execute

A goal's subjective prose plan is now separate from its executable step ledger. With `planning.grounded_plans: true`, the local model can bind up to four ordered intended steps to offered controller actions, or decline with an empty plan. New combined scenarios enable it; archived policies retain their previous behavior.

Only the next unfinished bound step is eligible for execution progress. Committing an intention earns nothing. A matching action must resolve successfully and its outcome must be received before the ledger completes the step or the controller awards the configured goal progress. Failed attempts request replanning; revised plans preserve previous versions. Stale bindings cannot finish steps in a new plan. Off-plan actions remain possible without pretending they completed the planned step. Resource costs and canonical world consequences still apply to actual actions.

This is bounded action grounding, not an unrestricted planner. The model does not invent actions, capabilities, money, success probabilities or world facts. The action library's usefulness for each arbitrary goal remains a scenario/model judgment; a completed simulation goal is not proof of real-world achievement. The report does not prescribe this exact algorithm: it is a documented engineering extension of the accepted planning loop.

See [goal-plans phase evidence](goal-plans-verification.json), [current engineering manifest](final-engineering-verification.json), and [the earlier integrated test report](LATEST_TEST_REPORT.md).

## Actual 27B completion

[Live report](GOAL_PLANS_LIVE_REPORT.md): the default-policy failure left its goal unfinished and requested replanning; the controlled draft/review fixture completed two outcome-linked steps. Both checkpoints restored identically from JSON/SQLite with no pending activities. This short engineering coverage does not establish unrestricted planning quality.

## Storage review and subscription decision

[Graphiti implementation](GRAPHITI_IMPLEMENTATION.md): the subscription-free local index is now integrated and checked with the 27B model. It uses Neo4j and local BGE embeddings; SQLite/JSON remains canonical and private FTS is an explicit fallback. Current verification is 161 named checks plus twelve core checks. Earlier review recommendations are historical; cache compaction/population scale and semantic guarantees remain limitations.
