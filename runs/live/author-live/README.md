# Scenario authoring evidence (16 October 2026)

The full draft → review → compile workflow with the local HauhauCS 27B model (llama.cpp server at `http://127.0.0.1:8081`, 8192-token context).

## `draft/`

```sh
python3 -m devsim.author draft "A family of three shares a small apartment. Priya is 15, has just started at a new school after a move, and is anxious about making friends. Her father Arun, 44, works evening shifts as a hospital nurse and worries he is not around enough. Her grandmother Meera, 71, lives with them, is warm but a little old-fashioned, and is usually home. In the second week of term a teacher invites Priya to join the robotics club. Simulate the first two months." \
  --api http://127.0.0.1:8081 --out runs/live/author-live/draft
```

Two model calls in 217.5 seconds. The first draft failed validation at `situations[0].options[1].progress_gain` (out of range). The field-named error went back as repair feedback, and the second draft compiled. [Requests](draft/requests.jsonl) hold both contexts. The draft has three people with caregivers, goals and listed facet percentiles, three rooms, four recurring situations (all Priya's), two interventions and six stated assumptions.

Earlier attempts with a 3500-token output budget were cut off mid-JSON. The prompt now asks for at most four situations and four interventions, and the budget is 5000 tokens.

## Review

The draft was accepted by the compiler that was current when it was written. Reading it found three problems:

1. **Intervention `month1_review` pre-writes outcomes.** It tells Priya on day 30 that she "made a few acquaintances in the club", whatever she actually chose in the simulation.
2. **The same intervention gives Arun a `testimony` observation whose source is `direct`.** Testimony has to come from someone. The compiler now rejects this, naming the field (`interventions[1].observations.arun`), and `check_author` covers it.
3. **Arun's routine is 06:00–18:00** although the setting says he works evening shifts.

[`reviewed/scenario.json`](reviewed/scenario.json) removes `month1_review`, sets Arun's available hours to 07:00–14:00 and adds a reviewer assumption. Nothing else changed.

Left as they are, and noted for any real use:
- The robotics invitation is both a day-10 intervention and a recurring situation (4/year). The vocabulary cannot tie a situation to an intervention.
- Arun and Meera have no situations of their own, so they act only as contacts.

## `compiled/` (compiler version before cognition was enabled)

```sh
python3 -m devsim.author compile runs/live/author-live/reviewed/scenario.json --out runs/live/author-live/compiled
```

Writes `initial.json`, `policy.json` and [`assumptions.json`](compiled/assumptions.json): 90 generated numbers with their JSON paths, the compiler defaults and the 7 stated assumptions. The scripted dry run covers 58.44 days: 8 resolved actions, 23 applied events, nothing pending. Running the printed `devsim.lifetime ... --scripted` command separately gave the same counts.

`compiled/run/` is the live 27B run of this policy: 37 calls (8 decisions, 29 appraisals), 236 s, no repairs, 8 resolved actions, nothing pending ([integrity](compiled/run/integrity-checks.json)). This policy had no `cognition` section, so the run made no semantic recall. The compiler now enables recall; see below.

## `compiled-graphiti/`

The same reviewed spec, compiled after the compiler started emitting `cognition: {semantic_recall, indexed_retrieval, graphiti_retrieval}`. Dry run unchanged. The live run used the local Graphiti service (installed without Docker on this machine):

```sh
python3 -m devsim.run_live --world runs/live/author-live/compiled-graphiti/initial.json \
  --policy runs/live/author-live/compiled-graphiti/policy.json --until-day 58.44 \
  --out runs/live/author-live/compiled-graphiti/run --api http://127.0.0.1:8081
```

45 calls (8 decisions, 8 semantic recalls, 29 appraisals), 293 s, no repairs, 8 resolved actions, nothing pending. Every recall used `graphiti_neo4j_local_bge_rrf`; there was no full-text fallback. [Integrity checks](compiled-graphiti/run/integrity-checks.json):
- Authored background lines stayed with their owners, in state and in every model context.
- The day-10 intervention reached Priya only.
- Earlier episodes were preserved, and JSON and SQLite checkpoints are equal.
- No facet table was sent to the model, and no event created a world fact.

Observations from the transcript:
- **Timing contradiction, seeded by the draft.** On day 5.3 Priya told Arun she "went to the robotics club meeting". The invitation arrives on day 10 and she accepts on day 17.8. The reviewed spec's `evening_check_in` success text is "I tell him about the robotics club and he listens with interest", and that rate-based situation can fire before the invitation. The controller resolved that authored outcome on day 5.3, and the model's speech elaborated it into a meeting. The engine kept the speech as an unverified utterance, not a world fact. The review missed this; outcome texts that presuppose a later event are a review item. The [report agent](../report-live/README.md) found the contradiction from the evidence.
- **Repetition.** Her day-44 and day-55 replies to her father are almost word for word the same. The run without recall had the same pattern.

## Limits

The people, backgrounds and numbers are generated scenario assumptions for a fictional world. A draft that compiles has the right shape and runs. It can still be wrong about the setting, as the review shows. The draft step is a convenience, not a substitute for reading the spec.
