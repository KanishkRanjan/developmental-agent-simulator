# Environment: places, groups, channels, invitations and interviews

16 October 2026. Extends the [household layer](HOUSEHOLD_IMPLEMENTATION.md) toward MiroFish roadmap items 2–3 ([roadmap](design/MIROFISH_NEXT_FEATURES.md)): school and work groups, written channels, invitations and commutes. It also adds interviews that run inside a scenario. Code: `devsim/household.py` (routing and turns) and `devsim/lifetime.py` (queue and dispatch). Checks: `checks/check_environment.py`.

Everything here is optional `household` policy. Policies without these keys behave exactly as before, so archived runs and fingerprints are unaffected.

## What a policy can declare

```json
"household": {
  "rooms": {"kitchen": {"label": "the kitchen", "audible_to": ["hall"]}, "hall": {"label": "the hallway"},
            "bedroom": {"label": "Priya's bedroom"}, "lab": {"label": "the school lab"}},
  "locations": {"priya": "bedroom", "meera": "kitchen", "okafor": "lab"},
  "routines": {"priya": {"available_hours": [[7, 22]], "response_minutes": [2, 10]}},
  "routes": [{"a": "bedroom", "b": "lab", "minutes": 20}],
  "channels": {"family": {"label": "the family chat", "members": ["priya", "arun", "meera"]}},
  "groups": {"robotics": {"label": "the robotics club", "place": "lab", "members": ["okafor"],
             "meetings": {"first_day": 10, "start_hour": 15.5, "duration_hours": 1.5, "every_days": 7,
                          "topic": "Build the robot arm.", "max_turns": 6}}},
  "invitations": [{"id": "club", "day": 8.5, "group": "robotics", "invitee": "priya", "inviter": "okafor"}],
  "conversations": [
    {"id": "texts", "day": 3.75, "channel": "family", "participants": ["arun", "priya"], "topic": "How was school?"},
    {"id": "checkin", "day": 30.8, "room": "kitchen", "participants": ["meera", "priya"], "topic": "School.",
     "interviewer": "meera", "questions": ["How is school going?", "Have you made friends?"], "max_turns": 4}]
}
```

| Key | Meaning |
|---|---|
| `rooms` | Any places, not only rooms at home. A school lab is a room with no audibility to home. |
| `routes` | Travel time between two places, 1–600 minutes, both directions. Places without a route are reached instantly, as before. |
| `groups` | Institutions and clubs: a label, a meeting place, members, and optional recurring `meetings`. |
| `channels` | Written messaging among fixed members, such as a family chat. |
| `invitations` | On `day`, `inviter` invites `invitee` into a group. |
| `conversations` | As before, now with either a `room` or a `channel`. Adding `interviewer` and `questions` makes it an interview. |

A situation option with a `contact` can also carry `conversation: {topic, max_turns?, questions?}`. When the option succeeds, the actor starts that conversation or interview with the contact.

## How it behaves

- **Commutes.** A person taking a route sets off, and the people in the room they leave notice. For the route's minutes they are in transit: located nowhere, unable to be overheard or met, and with that time reserved on their calendar. On arrival, the people present notice them come in. A busy person cannot set off.
- **Group meetings.** At `first_day` + `start_hour`, every current member who is available for the whole meeting sets off for the place (so `start_hour` is the departure time, and `duration_hours` counts from arrival). Once everyone who set off has arrived, the attendees hold a conversation on the meeting topic. When the meeting ends, each attendee travels back to where they came from, retrying every 30 minutes while busy. Fewer than two attendees means no meeting, and the scheduler trace records why.
- **Channels.** Members take turns regardless of where they are. A message is read directly (`kind: direct`), but it is not a physical encounter, so it cannot create a firsthand relationship. Non-members receive nothing.
- **Invitations.** The invitee receives the invitation and decides, using the model, whether to accept or decline. The choice is a committed action. Acceptance adds them to the group and commits the fact `member_<group> = true` on the reply event; declining commits `false`. The inviter receives the reply. An unavailable invitee is retried hourly for up to 72 hours.
- **Interviews.** The interviewer's turns are the fixed questions in order, with no model call, committed as actions. The interviewee answers in their own words, declines, or ends the interview. Each turn waits the speaker's response interval and reserves both calendars. Room routing applies, so someone in an audible adjacent room overhears the questions and answers as testimony. The interview closes when the questions are answered.
- **Agent-initiated conversations.** These run in the shared room if the contact is present, otherwise over a channel both people belong to. If neither applies, the scheduler trace records that the contact was not reachable.

All of these are scheduler queue events (`trip`, `group`, `invite`, alongside `conversation`) with the same atomic rollback and checkpointing as other events. A run resumed from a checkpoint saved mid-commute or mid-meeting ends in the same state as an uninterrupted run.

## Verification

- [Check suite](../checks/results/environment-engineering-checks.json): 9 named checks on a scripted fixture. They cover channel isolation, invitation decisions and membership facts, timed commutes and returns, meeting privacy, interview order, time cost and overhearing, agent-initiated interviews, mid-commute resume, and a rejection table. Five deliberate mutations each fail the suite:
  - channel messages leak to non-members
  - teleporting instead of commuting
  - acceptance without a membership fact
  - members never return home
  - free model turns in place of the fixed questions
- The authoring checks compile and run an authored scenario that uses all of this (see [authoring](AUTHORING_IMPLEMENTATION.md)).
- **Live 27B evidence: pending.** A scenario drafted from a plain-language setting by the actual model is in progress in `runs/live/environment-live/`.

## Limits

- Routes are fixed travel times. There is no transport mode, traffic or cost.
- Meeting schedules are fixed intervals; no weekdays, holidays or cancellations.
- Group membership changes only through invitations, and nobody leaves a group.
- Channels have fixed members. There is no read-later delay beyond response intervals, and no unread state.
- Interview questions are fixed in advance; the interviewer does not ask follow-ups.
- Places carry no other properties (capacity, noise, privacy) beyond audibility.
