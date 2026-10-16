# Agent interviews

16 October 2026. Implements MiroFish roadmap item 4 ([roadmap](design/MIROFISH_NEXT_FEATURES.md)): a researcher question interface with two explicitly separate modes. Code: `devsim/interview.py`. Checks: `checks/check_interview.py`.

## Two modes

| | Diagnostic | In-world |
|---|---|---|
| What it is | A researcher outside the world questions a frozen copy | An explicit intervention: a committed identity asks in person |
| Effect on the run | None. The world state hash is checked before and after; the person does not remember being asked | The question and reply become received events in the person's (and a materialized interviewer's) history |
| Model path | One call per agent-question pair over the agent's own context (`task: diagnostic_interview`) | The household turn path: appraisal of the question, optional background/semantic recall/situational preparation, `propose` with *answer*/*decline*, `commit_action`, appraisal of the reply, optional consolidation |
| Batch | Any number of agents × questions | One interviewee, several questions in sequence |
| Output | Transcript records with the exact context each answer used | A new checkpoint (JSON and SQLite) plus a transcript; the input checkpoint is never modified |

Both modes label every answer `generated_account_not_causal_access`: an agent's explanation of its own behavior is a generated account, not access to the true cause. Spoken claims never become world facts.

## Guarantees

- **Information boundaries.** Answers draw only on the interviewed agent's context; a diagnostic answer that cites another agent's memory fails validation (two repair attempts, then the interview stops with no state change).
- **Frozen diagnostics.** Questions run on a deep copy. If either the copy or the original changed, the call raises instead of returning answers.
- **Atomic in-world interviews.** All questions in one interview commit together; a failure on a later question restores the state from before the first question, and the interview id stays usable.
- **Distinguishable records.** In-world events and actions use `@interview:<id>:<n>:question|answer|reply` ids. Reusing an interview id is rejected.
- **Eligibility.** Dead agents and infants (under two years; no verbal self-report) cannot be interviewed. The interviewer must be a committed identity distinct from the interviewee; only a materialized, living interviewer receives the replies. Household routines gate in-world interviews.
- **Resumable.** An in-world interview does not advance the simulated day, so the new checkpoint resumes under the run's own archived policy and provider.

## Run it

From the repository root (the local server here is on port 8081; the historical forward used 18081):

```sh
# Diagnostic: repeat --agent and --question for a batch
python3 -m devsim.interview diagnostic CHECKPOINT.json \
  --agent alex --agent maya --question "What happened this evening?" \
  --api http://127.0.0.1:8081 --out runs/live/NEW_DIAGNOSTIC

# In-world: needs the checkpoint's own archived policy
python3 -m devsim.interview in-world CHECKPOINT.json --policy POLICY-USED.json \
  --agent alex --interviewer maya --id checkin-1 \
  --question "How are you feeling about school?" \
  --api http://127.0.0.1:8081 --out runs/live/NEW_INTERVIEW
```

Add `--scripted` to an in-world interview of a scripted run (deterministic engineering provider). Every run writes `source-hashes.json`, `requests.jsonl`, `transcript.json` and `summary.json`; in-world runs also write `world.json` and `world.sqlite`. From Python, `diagnostic(engine, owners, questions, api=..., model=...)` and `in_world(lifetime_controller, owner, interviewer, questions, interview_id)` return the same records.

## Verification

- [Check suite](../checks/results/interview-engineering-checks.json): 14 named checks with stubbed transport. Three deliberate mutations (no rollback, no memory-id validation, diagnosing the live engine) each fail the suite.
- [Live evidence](../runs/live/interview-live/README.md) on the preserved household scene with the actual HauhauCS 27B model. Batch diagnostic: four agents × two questions, 8 calls, no repairs; Noor, who was in the closed room, reported no memory of the conversation. In-world: Maya asked Alex two questions, 14 calls; questions and replies reached only Alex and Maya, answers resolved as actions, no world facts changed, checkpoints restore identically and resume. Graphiti was unavailable on this machine, so recall used the recorded private full-text fallback.
- [Manifest](../runs/verification/interview-verification.json) with per-suite counts and source hashes.

## Interviews inside a running scenario (16 October 2026)

A household conversation can now be an interview: it names an `interviewer` and 1–10 `questions`, with the interviewer listed first. The interviewer's turns are the fixed questions, with no model call, committed as actions. The interviewee answers in their own words, declines, or ends it, through the normal decision path. Because it runs as a conversation:

- **Scheduled in policy:** add it to `household.conversations` with a day and a room or channel.
- **Time cost:** each turn waits the speaker's response interval and reserves both calendars.
- **Overheard:** room routing applies, so someone in an audible adjacent room receives the questions and answers as testimony. Over a channel, only members read them.
- **Agent-initiated:** a situation option with a `contact` can carry `conversation: {topic, questions}`. When the option succeeds, the actor interviews the contact in their shared room, or over a channel they both belong to.

See [the environment guide](ENVIRONMENT_IMPLEMENTATION.md) and `checks/check_environment.py`.

## Limits

- The checkpoint interviews above (diagnostic and in-world) still take no simulated time and are private. Use the conversation form for timed, overheard interviews.
- In the conversation form the questions are fixed in advance; the interviewer does not adapt follow-up questions to the answers.
- Answering is not treated as a developmental exposure (no crystallization hook).
- Diagnostic questions are independent; there is no multi-turn diagnostic dialogue.
- Generated answers can sound coherent while restating earlier unverified claims. They are not evidence of human-like self-report or improved prediction.
