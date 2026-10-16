# Household environment and conversations

16 October 2026. Implemented the next two applicable MiroFish/OASIS lessons: an explicit interaction environment and daily activation/response timing. The implementation extends our developmental engine; it adds no OASIS dependency, hosted model or subscription.

## What runs

`household.py` defines rooms, explicit audible connections, committed locations, daily availability, response intervals and bounded conversations. `Lifetime` queues movements, conversation starts and individual turns alongside world events, autonomous recall, opportunities and activity completions. A checkpoint can fall midway through a reply interval without repeating the time reservation or earlier speech on resume.

Each speaker calls the existing local-model decision path with their own behavioral-language personality, mood, relationships, accessible memories and goals. There is no shared transcript in an agent prompt. A previous utterance reaches another agent through an actual received observation and its private retrieval path. Optional semantic recall, situational appraisal, reflection and consolidation use their existing policy flags. Resolved conversation actions also feed the existing crystallization evidence gate when enabled; merely overhearing is not enacted behavior.

Agents can speak/ask questions, listen, stop participating, or leave for a configured exit room. Infants have nonverbal signals and empty speech/plans. The controller selects a bounded round-robin turn order and samples each speaker's declared response interval; it does not script the model's words. Calendars reserve the attending participants during that interval. Unavailable or occupied invitees cannot be silently double-booked. A person who leaves, dies or becomes unavailable cannot deliver a pending reply.

Normal speech reaches available people in the same room and any explicitly listed audible room. A bystander can acquire a memory and a subjective mood reaction even when not addressed. A closed-room or absent person receives nothing. Hearing across rooms retains source provenance but does not create a firsthand relationship. Speaker identification across an audible connection is a scenario assumption; acoustic ambiguity/voice recognition is not modeled. Directed links are one hop and need not be reciprocal.

The world records that someone spoke. It does **not** promote the content of their claim into a canonical event, resource change, biography or verified fact. Direct observations mean firsthand perception of the words/behavior, not proof of every assertion in them. Original episodes remain immutable. JSON and SQLite preserve locations, conversation state, calendars and received provenance; private Graphiti views index received representations as before.

## Run it

From the repository root, with the existing SSH connection/forward active:

```sh
work/profile-env/bin/python -m devsim.household_example \
  --graphiti --out runs/live/NEW_HOUSEHOLD_RUN
```

This creates a short initialized adolescent/caregiver scene, not a simulated childhood. Use `--scripted` without `--graphiti` for a deterministic engineering provider.

To include scheduled household scenes in a fresh combined lifespan policy:

```sh
work/profile-env/bin/python -m devsim.simulate \
  --household --caregivers 2 --years 7 \
  --out runs/live/NEW_COMBINED_HOUSEHOLD_RUN
```

Add `--scripted` for the engineering provider. Existing archived policies keep their original behavior. `--household` is explicit because introducing waking windows changes which opportunities are eligible; it is not a harmless rewrite of an old policy fingerprint. Resume using the checkpoint's own archived policy and provider.

## Policy vocabulary

`policy.household` contains:

| Field | Meaning |
|---|---|
| `rooms` | Room IDs with public `label` and optional directed `audible_to` room IDs. |
| `locations` | Initially materialized agent → room. Current locations live separately in checkpoint state. |
| `routines` | Agent → sorted, nonoverlapping `available_hours` windows and `[min,max]` `response_minutes`. Split overnight windows at midnight; `[]` means unavailable. Omitted routines allow the whole day. |
| `moves` | Explicit controller transitions: `id`, `day`, `actor`, `room`. Departure/arrival is observed locally. Movement is instantaneous at the declared event time. |
| `conversations` | Explicit `id`, `day`, `room`, 2–12 `participants`, public opening `topic`, `max_turns` (1–40), optional distinct `exit_room`. |

Conversation topics, placements, schedules and latencies are visible scenario assumptions. Fractional simulated days define a shared 24-hour clock. The sample combined policy places four bounded family conversations near ages 1, 6, 16 and 21; this is not continuous household life. Availability also gates ordinary elapsed reservations. Optional `room_contact: true` on an existing contact action requires co-location both at initiation and completion; its older bounded request/reply path retains explicit recipients. General contact actions are not silently reinterpreted as physically local conversations.

## Verification

[Verification manifest](../runs/verification/household-verification.json) records **13 suites, 185 named checks plus 12 core checks**. The new household suite contributes 24 checks, including privacy, overhearing, calendar conflicts, waking boundaries, movement/death cancellation, infant constraints, failed-appraisal rollback/retry, mid-response restoration, physical contact prerequisites and developmental exposure wiring.

[Actual 27B trace](../runs/live/household-live/run/summary.json): **four alternating turns, 23 API calls, 133.303 seconds, zero output repairs**. Alex and Maya independently spoke, Bea overheard, and Noor's closed bedroom excluded all conversation updates. Graphiti retrieval was ready with no fallback. [Integrity checks](../runs/live/household-live/run/integrity-checks.json) confirm private-state boundaries, received-prior-turn context, unchanged canonical facts and JSON/SQLite equality. [Readable transcript](../runs/live/household-live/transcript.md) preserves what was said.

The model invented specific history/biology assignments and deadlines that were absent from initialization. They remain unverified utterances; coherent conversation does not establish factual fidelity. Automatic verification of personal assertions is still unresolved.

[Final seven-year scripted run](../runs/scripted/household-lifetime-final/integrity-checks.json): six retained agents, 61 resolved actions, four completed household conversations/16 turns, no pending activities and matching restored checkpoints. It exercises the final developmental exposure hook but skips model-only cognition. No birth occurred in this fixture.

The live trace preserves its original source hashes. Afterwards, the optional crystallization hook was added (disabled in that live policy), sample combined-scene clock times were corrected in `full_scenario.py` (not imported by the live runner), and checks were extended. The final local/combined evidence applies to those refinements. Do not describe every final branch as actual-model tested.

## Boundaries and next work

This implements physical room routing and bounded household dialogue, rather than a general OASIS social-media platform. Conversation starts/participants remain scenario-declared; there are no autonomous invitations, interruptions, whispering, attention competition, mishearing, automatic work/school commutes or learned routines. Newly generated people/newborns need explicit room placement and future conversation rules; they do not acquire an invented daily social life. General school/work groups, digital channels and recommender feeds remain extensions.

The other proposed MiroFish adaptations—automatic validated scenario authoring, frozen/in-world interviews, an evidence-linked report agent and a researcher GUI—have all since been implemented (see [authoring](AUTHORING_IMPLEMENTATION.md), [interviews](INTERVIEW_IMPLEMENTATION.md), [reports](REPORT_IMPLEMENTATION.md) and [cockpit](COCKPIT_IMPLEMENTATION.md)); they remain bounded engineering layers in [the roadmap](design/MIROFISH_NEXT_FEATURES.md). The local Graphiti cache still has the previously documented scale/compaction limit. No measured human-prediction improvement follows from these engineering checks.

## Reference

MiroFish upstream commit `7657031ac01184afe2cb220f5ee3545573b5e843`: [runtime activation/environment](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/scripts/run_twitter_simulation.py) and [activity configuration](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/simulation_config_generator.py). We adapted the environment/activation patterns into our own information boundaries; this does not claim MiroFish already implements this household development design.
