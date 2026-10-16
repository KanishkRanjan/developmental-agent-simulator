# Further MiroFish lessons: proposed additions

16 October 2026. These are recommendations following code inspection at upstream commit `7657031ac01184afe2cb220f5ee3545573b5e843`. Update: items 2–3 now have a bounded household implementation; see [the implementation and evidence](../HOUSEHOLD_IMPLEMENTATION.md). Items 1, 4, 5 and 6 are implemented ([authoring](../AUTHORING_IMPLEMENTATION.md), [interviews](../INTERVIEW_IMPLEMENTATION.md), [reports](../REPORT_IMPLEMENTATION.md), [cockpit](../COCKPIT_IMPLEMENTATION.md)). The remaining recommendations are **not implemented additions or evidence of missing previously completed mechanisms**. Existing memory, mood, development, goal execution and local Graphiti layers remain in place. No subscription is needed to build these adaptations.

1. **Scenario authoring — implemented.** See [the implementation](../AUTHORING_IMPLEMENTATION.md). Adapt MiroFish's requirement-to-configuration workflow into a compiler for our own validated policy schema. A researcher's setting, people, institutions, constraints and intervention should produce a reviewable scenario. Generated coefficients remain labeled assumptions; generated claims cannot silently become verified facts. We currently write scenario policies manually.

2. **An environment that routes information — implemented for places, groups, channels and invitations.** See [the environment guide](../ENVIRONMENT_IMPLEMENTATION.md). Build explicit rooms, households, school/work groups and communication channels. These determine who can encounter or receive a message before an agent chooses how to respond. Existing code enforces explicit recipients; the extension would select those recipients through environment rules. MiroFish's OASIS-backed social platforms are a useful interaction-environment pattern. Configured recommender/echo-chamber fields are not, by their presence alone, proof that every advertised coefficient drives its runner.

3. **Daily availability and response timing — implemented, including commutes.** Extend our elapsed activity calendars and opportunity hazards with sleep/work availability and individual response latency. MiroFish's runner actually consults active hours. Its defaults are illustrative social-media schedules, not universal developmental or cultural laws. Availability should change whether an interaction can happen without changing personality or awarding activity outcomes.

4. **Agent interviews — implemented.** See [the implementation](../INTERVIEW_IMPLEMENTATION.md). MiroFish has command/response support for individual and batch interviews. We could add a researcher question interface over a frozen copy, alongside explicitly in-world interviews that become received events. Those modes must be distinguishable: a diagnostic interview should not alter the main run, and a real question can affect the person. An LLM's explanation is a generated account, not guaranteed access to the true cause of behavior.

5. **An evidence-linked report agent — implemented.** See [the implementation](../REPORT_IMPLEMENTATION.md). Our graph tools are primitives; they do not yet generate an entire study report. Adapt MiroFish's outline/tool/section workflow to report episodes, changes, unresolved contradictions and actual tool outputs with event IDs. Preserve its useful discipline of separating executed tool results from model-generated text. The report should distinguish observed simulation outcomes, agent interpretations and researcher inference.

6. **A researcher cockpit — implemented.** See [the implementation](../COCKPIT_IMPLEMENTATION.md). Adapt its staged setup and live action timeline into views of individual histories, current accessible memories, mood, relationship changes, pending plans and raw event evidence. Select one agent's perspective or an explicitly labeled researcher view. We have logs and JSON artifacts, not a comparable interactive application interface.

Recommended implementation order: **environment information routing → daily availability → scenario authoring → interviews → evidence-linked reports → richer visual interface**. Scenario authoring can initially expose a small supported world vocabulary. Graph cache compaction remains a separate known scaling task before long live population runs.

## Primary code inspected

- [Scenario/activity configuration](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/simulation_config_generator.py)
- [Runtime activation/environment](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/scripts/run_twitter_simulation.py)
- [Individual/batch interview commands](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/simulation_ipc.py)
- [Reporting tools and result handling](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/report_agent.py)
- [Simulation timeline interface](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/frontend/src/components/Step3Simulation.vue)

These are software patterns worth adapting. Generated personas, plausible narratives, activity parameters and polished reports do not independently establish accurate human simulation. Keep the user's correlated trait/developmental design and information boundaries; evaluate predictive claims separately later.

## Implemented scope after this roadmap

`household.py` now supplies rooms/audibility and multi-turn private dialogue; calendars/routines govern response intervals, and `Lifetime` checkpoints the queues. `household_example.py` and `simulate.py --household` are executable entry points. Broader groups/channels, automatic invitations/commutes, scenario authoring, reports and the GUI remain separate proposals. `interview.py` now implements item 4 with separate diagnostic and in-world modes ([implementation](../INTERVIEW_IMPLEMENTATION.md)). Do not interpret these updates as all six roadmap items being completed.
