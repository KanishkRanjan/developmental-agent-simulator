# Report evidence (16 October 2026)

## `author-graphiti/`

A report on the [authored scenario's Graphiti run](../author-live/README.md) (day 58.44) with the local HauhauCS 27B model. The local Graphiti service was running for the two graph searches.

```sh
python3 -m devsim.report runs/live/author-live/compiled-graphiti/run/world.json \
  --initial runs/live/author-live/compiled-graphiti/initial.json \
  --focus "How did Priya's first two months at the new school unfold, and do people's accounts match what the simulation resolved?" \
  --graph-query priya "robotics club" --graph-query arun "Priya at school" \
  --api http://127.0.0.1:8081 --out runs/live/report-live/author-graphiti
```

5 model calls (1 outline, 4 sections) in 100 s, no repairs. 65 evidence items: 17 controller events, 8 resolved actions, 6 utterances, 29 memory meanings, 3 state changes and 2 Graphiti searches. The report has 4 sections with 12 observed claims, 7 agent-interpretation claims and 4 researcher inferences. Read it in [`report.md`](author-graphiti/report.md).

What it got right:
- **Timing contradiction.** Without being prompted, the first section notes that Priya talks about a club meeting on day 5.31 while the invitation is recorded on day 10 (E11, E18, E19), and lists it as an open question. The cause is in the authored scenario: the check-in outcome text mentions the club and can fire before the invitation.
- **Repetition.** It notes that Priya's day-44 and day-55 reports are identical and asks whether anything changed between them.
- **Category discipline.** Spoken claims are reported as "stated", not as events, and interpretations cite memory meanings.

Where to be careful:
- The last section infers "social integration was achieved without forming deep interpersonal bonds" from closeness values of 0.0. That is a model inference, correctly labeled as one, but likely an over-reading: these situations never update closeness.
- "Arun interpreted Priya's reports as ... her first robotics club visit" restates Arun's memory meaning, which itself absorbed Priya's unverified claim.

The checkpoint was not changed (state hash in `report.json`). Claims were checked for citation and type, not for truth.
