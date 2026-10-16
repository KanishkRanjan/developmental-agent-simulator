# Actual 27B integration run

**Historical pre-audit run.** The subsequent [source-to-code audit](source-to-code-audit.md) confirmed that this run used a numerical personality table, did not connect actual-use recall or gist consolidation, and used a fixed-step opportunity process. Preserve it as evidence of the earlier prototype operating, not implementation of the full research design. The corrected small integration trace is in `audited-live-example/run`.

Completed 16 October 2026 after the user restored SSH. The cluster connection and local inference API both worked. The selected model was `HauhauCS Qwen3.8-27B Uncensored Aggressive Q4_K_P`, as reported by the server; the exact model metadata is retained in [server-model.json](live-example/server-model.json).

| Result | Observed value |
|---|---:|
| End of scenario | Simulated age 22 |
| Controller ticks | 89 |
| Actual model action responses | 30 |
| Actual model appraisals | 36 |
| Resolved actions saved | 30 |
| Action responses citing supplied memory IDs | 29 of 30 |
| Stored memories | Alex 30; Maya 6; Bea 0 |
| Runtime | About 7 minutes |
| Final checkpoint restored | Yes |

The controller supplied age-eligible opportunities and available actions. The model chose actions and plans using its current profile, mood and accessible memories. The controller resolved consequences under the scenario policy, then the model separately appraised what each recipient perceived. Those subjective appraisals entered subsequent memories and mood. Successful events also triggered the scenario's bounded trait updates.

The model chose caregiver help six times, private adolescent drafting fourteen times and private adult note revision ten times. Bea received no observations because Alex did not select the options involving Bea. This is one trajectory under one synthetic profile, not evidence that these choices are human-accurate or that each mechanism improved performance.

## Artifacts

- [Summary](live-example/summary.json): actual request counts, runtime and completion status.
- [Saved world](live-example/world.json): events, agent state, memories, goals, plans and development history.
- [Model requests and responses](live-example/requests.jsonl): agent context and parsed output for every successful call.
- [Exact scenario policy used](live-example/policy-used.json): retained separately from later edits; its fingerprint matches the saved controller state.
- [Checkpoint integrity results](live-example/integrity-checks.json): restored state and resolved outcomes checked after completion.

## Scope and one scenario correction

The source goal said “prepare and deliver” while all available adult actions only prepared material. The run credited completion after preparation. It did **not** simulate delivering a presentation. The current scenario goal has therefore been corrected to preparing notes and materials; the original run and its original policy remain unchanged for inspection. Resume an archived run with its own `policy-used.json`, not a modified scenario file.

Initial traits are synthetic. Event rates, success probabilities, strength/affect rules and trait effects are provisional assumptions. The scenario omits early infancy and most life experiences, uses coarse 90-day steps, and offers only a few activities. It demonstrates operational integration with a real model. It does not establish improvement over another system, predictive validity or completion of the full research design.

The remaining major work includes richer and grounded developmental/attachment policies, gist consolidation, constrained biography expansion and broader social/world behavior. The live connection and inference integration are no longer blockers.
