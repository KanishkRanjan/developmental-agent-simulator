# Living world (game-style needs, places, free time and surroundings)

Added 18 October 2026 at the user's request, after the environment-v5 run: Meera said she was worried about Priya but never went to her room. Nobody in 62 days chose to go anywhere, and the world itself never did anything. The model for this layer is a life-sim game (The Sims). The world runs on deterministic, seeded rules; the model is used only for minds (thoughts, choices, speech, appraisal) and an optional TV news sentence.

Code: `devsim/living.py` (needs, map, whereabouts, menu, carrying out choices, bedtime), `devsim/surroundings.py` (happenings, weather, creatures), catalog and rates in `devsim/policies/living.json`. Checks: `checks/check_living.py`.

## Turning it on

Policy key `living` (`{}` for the defaults; top-level keys of `living.json` can be overridden). It needs event-driven sampling and household rooms. The scenario compiler adds `living: {}` when every room has a `kind` and a `site`; the draft prompt asks for both. Free-time choices ride on `inner_thoughts` (compiled default every 20 minutes). Worlds without the key are unchanged.

## Map

| Room field | Meaning |
|---|---|
| `kind` | bedroom, kitchen, living_room, bathroom, classroom, cafeteria, lab, office, ward, outdoors, other. Decides the furniture and everyday happenings. |
| `site` | The building: a family's home, school, a workplace. Rooms of one site are within walking reach (moves are instant, as before). |
| `objects` | Optional extra or replacement furniture, same shape as the catalog. |

- A route between any rooms of two sites joins the sites. Without one, the other site is unreachable: `household.travel` returns `None` (it used to teleport).
- Rain multiplies route minutes by `rain_travel_factor`; a late bus adds minutes for a while.
- A site with home rooms (bedroom, kitchen, living room, bathroom) is private to the people whose starting room is there; public sites are open to all.
- Someone's bedroom furniture is used only by the people who sleep there (visiting them there to talk is fine).
- Nobody walks into an occupied bathroom to chat.
- Each person's starting room is their home room (where they sleep). Near the end of their last waking window (`bedtime_minutes_before`) they go back there, travelling home if needed.

## Needs

Five needs in [0, 1] (1 = fully met): hunger, energy, social, fun and hygiene.
- **How they fall:** at a per-hour rate while awake (inside `available_hours`) and another while asleep; energy refills during sleep. Values are computed lazily from the last update, so nothing ticks, and reading them changes nothing.
- **What raises them:** finishing activities (catalog deltas), conversation turns (`social_per_turn` for the speaker and everyone who heard) and playing with a pet. The surroundings can lower them, as when someone slips.
- **What the model sees:** low needs only, as words in every context (`how_your_body_feels`: "hungry", "exhausted", "lonely"); never numbers.
- **Attention:** below half energy, attention's fatigue signal rises.

## Knowing where others are

`agent.last_seen[person] = [room, day]` is updated only from perception:
- seeing someone enter a room;
- hearing someone leave (their whereabouts become unknown);
- hearing them speak, even from a room within earshot;
- watching a pet.

People in one's own room are always known. Sightings older than `whereabouts_hours` are forgotten.

## Choosing what to do

At each inner thought, if awake and not in a conversation, a person gets a menu:
- **Stay**, scored `stay_score`, more while busy with something.
- **The best activities in reach** (`menu_size - 1` of them). Each scores Σ need gain × 2(1 − need)² − 0.2 × need cost − `travel_penalty_per_minute` × minutes.
- **People they know the whereabouts of** (up to five): talk to them, go and talk to them, message them over a shared channel, or play with a pet in the room. People are always offered, because a reason to seek someone out, such as worry, lives in the thought, not in the need scores.

The thought call (`cognition.think`) returns the thought plus `choice` and `about`. A scripted run takes the top-ranked option (Sims-style autonomy). Then:
- **do / play:** walk there; on arrival start if the object is usable (others in the room see "Mum started cooking."); after its minutes, needs change and the doer notes "I finished cooking.". Leaving first means it never completes.
- **talk:** walk to where you believe they are. On arrival, start a conversation about `about` (cap 40 turns; it ends on a silent round), or notice "I went to find Priya, but Priya was not there / asleep / busy talking with someone."
- **message:** a written-channel conversation.
- **go:** walk back to your own room.

Activities do not use the calendar or the daily task budget, so a leisure activity never blocks school or a scheduled talk.

## Surroundings

- **Happenings:** listed per room kind in the catalog, plus the scenario's own (`household.happenings` with a `room`). Each has `{id, kind, text, hours, rate_per_day, audible, effects, self_text}`, recurring at a seeded rate inside its hours. Only awake people in the room perceive it, and for audible ones also people in rooms within earshot. Atmosphere is delivered as routine (repeats reuse the earlier reaction, with no model call).
- **Incidents:**
  - `disable_powered` (site or room) puts powered objects out of order for `minutes`, then announces `restore_text`;
  - `route_delay_minutes` slows journeys from or to the site;
  - `close_conversations` (a fire drill) interrupts talks on the site and frees their reserved turns;
  - a `{name}` happening picks someone present, who gets `self_text` and `target_needs`.
- **Off-stage people:** a delivery, a relative's call.
- **News:** in live runs the model writes one TV news sentence on a topic from `news_topics` (purpose `news` in `requests.jsonl`); scripted runs use the fixed text.
- **Weather:** one seeded chain (clear, cloudy, rain) with mean `mean_hours` between changes. People in rooms whose kind is listed in `windows` notice changes.
- **Creatures** (`household.creatures`: id, name, kind cat or dog, rooms, starting room): a rule-based routine. A creature moves among its rooms and does one of its behaviours within its active hours. People present notice it, and it can be played with.

## Watcher

The people pane shows each person's current activity and low needs. The feed interleaves thoughts ("(thinks) …"), activities, happenings, weather and the pet with speech.

## Limits

- **Every rate, delta, threshold and catalog entry is a provisional design default [D], not a measurement.** Happening draws that fall outside their hours are moved into the window, which keeps the daily count but not the exact process.
- **Moves within a site are instant**, as before; the plan's one-minute walk was not needed.
- **Scripted runs talk to the cap.** Scripted conversation turns always speak, so scripted conversations run to 40 turns; the compile dry run therefore skips inner thoughts.
- **Not live-verified with the 27B model.**
