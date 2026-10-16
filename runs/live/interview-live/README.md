# Interview evidence (16 October 2026)

Both runs question the preserved [household scene](../household-live/run/world.json) (day 0.8, after the family conversation) with the local HauhauCS 27B model. The source checkpoint was not modified.

## `diagnostic/`

```sh
python3 -m devsim.interview diagnostic runs/live/household-live/run/world.json \
  --agent alex --agent maya --agent bea --agent noor \
  --question "What happened at home this evening, and who was there?" \
  --question "How do you feel about asking other people for help?" \
  --api http://127.0.0.1:8081 --out runs/live/interview-live/diagnostic
```

Eight model calls, 50.7 seconds, no output repairs. Alex, Maya and Bea described the homework conversation from their own received memories. Noor, who was in the closed bedroom, said she had no memory of the evening's events and cited only her own private thought. [Transcript](diagnostic/transcript.json) holds each answer with the exact context the model saw.

## `in-world/`

```sh
python3 -m devsim.interview in-world runs/live/household-live/run/world.json \
  --policy runs/live/household-live/run/policy-used.json --agent alex --interviewer maya --id evening-checkin \
  --question "How are you feeling about the biology lab now?" \
  --question "Why didn't you tell me sooner that you were worried?" \
  --api http://127.0.0.1:8081 --out runs/live/interview-live/in-world
```

Fourteen model calls (8 appraisals, 2 retrieval queries, 2 semantic recalls, 2 decisions), 88.3 seconds. Alex chose to answer both questions; the replies are in the [transcript](in-world/transcript.json). [Integrity checks](in-world/integrity-checks.json): both questions and replies reached Alex and Maya only (Bea and Noor received nothing), each answer is a resolved action, no world facts changed, the day did not advance, JSON and SQLite checkpoints restore identically, and the result resumes under the archived policy. Alex's mood valence moved by −0.30.

Graphiti is not configured on this machine, so semantic recall used the private full-text fallback; the checkpoint records `fallback_private_fts`. The preserved household trace used the graph index.

## Limits

Answers are generated accounts, not access to the true causes of simulated behavior. Specific claims (deadlines, the Wednesday target) repeat what the agents said earlier in the scene; they remain unverified utterances, not world facts. This is a short engineering fixture, not evidence of human-like self-report.
