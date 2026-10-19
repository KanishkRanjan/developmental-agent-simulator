# Build state

Updated 19 October 2026 (earth-family-3 crash fix). This is the single current status file. Earlier milestone sections, with their original counts and wording, are in [the build-state log](history/BUILD_STATE-log.md) and the other [history documents](history/README.md). Where they disagree with this file or [the source-to-code audit](source-to-code-audit.md), this file and the audit win.

## Travelling while busy no longer crashes, 19 October (earth-family-3 crash)

`runs/live/earth-family-3` crashed after 3.4 hours (168 actions) with `TypeError: 'NoneType' object does not support item assignment`, and its resume `earth-family-3-r2` hit the same error at once. A person still marked busy by the living layer set off for a group meeting. While travelling they have no room, so `household.view` returns `None`, and `engine.context` then wrote `you_are` into that `None`. Now `you_are` is set only when there is a physical environment. Check: `living` (+1: a busy person in transit gets a context without crashing). 412 named checks passed (Graphiti skipped). Left open: whether someone busy should be able to leave without first ending the activity. **Not live-verified.** The earth-family-3 checkpoint should now resume past the crash point.

## Inner thoughts no longer copy themselves, 18 October (user report)

In the `test-2` run, Kai thought the same sentence two or three times in a row ("John's silence is still sitting in my chest like a stone…"). The previous thought came back as his top memory, word for word, and with nothing new in between the model copied it. Now `cognition.think` compares each new thought with the person's last 5 thoughts, using the speech repeat test (`engine.near_repeat`, shared with `repeated_speech`: word similarity of 0.8 or more, or a shared six-word phrase). On a match it asks once more, showing the earlier words and the person's last 5 thoughts in `repeat_notice` (sampling at 0.8, as for speech). Showing only the copied thought let re-asks fall back on another recent one (earth-family-2: 1 of 10 stored thoughts). On earth-family-3, 14 of 42 thought calls were re-asks; of 28 stored thoughts, 3 shared a six-word phrase with a recent one and none were copies. A second repeat is kept. Check: `household` inner-thought case (a stub that always copies its last thought now stores no back-to-back duplicates). 410 named checks passed (Graphiti skipped). **Not live-verified.** The running `test-2` process still runs the old code.

## Shared bedrooms in the builder, 18 October (user request)

A home place's `shared` map (`{person: person whose bedroom they share}`, already read by `builder.rooms_for`) now labels the room with both names ("Vikram and Anjali's bedroom"). The control panel has no control for it yet; set it in `design.json`. Check: `builder` (+1). Used by `work/designs/earth_family` (parents share a room), run `runs/live/earth-family-3`.

## Fast-forward a live run, 18 October (user request)

A paced run can skip ahead: key `f` in the watcher (also in the control panel's Watch), `/skip 2` in the cockpit or a typed line, or `python3 -m devsim.visit RUN --skip 2`. The skip reaches the run at its next event boundary (`deliver_inbox`, note kind `skip`, 0–168 hours) and sets `runtime.skip_until`. Real-time waiting stops until then. Nothing is summarized or invented: every event in the skipped hours (thoughts, free-time choices, conversations, happenings, meetings) still happens through the model, as fast as the model replies. Needs, hormones, sleep and mood advance as they always do. At `skip_until` pacing resumes. Each skip is logged in `runtime.skips`. The watcher header shows "fast-forwarding to HH:MM" while it lasts. The cost is the model calls the skipped hours would have made anyway. A night of sleep skips almost instantly; a busy afternoon with conversations can take minutes.

Also fixed: a run resumed into a new folder kept the previous folder's inbox position, so the first ~80 bytes typed into the new run (a call, edit or skip) were silently skipped or misread. `run_live` now starts a new folder's inbox at 0.

Checks: `household` (+1: an 18-hour skip plays without waiting and ends in the same world as an unpaced run; bad hours are rejected). 410 named checks passed (Graphiti skipped). The inbox-position fix has no check. **Not live-verified.**

## Phone calls ring for a while and can be hung up, 18 October (user request)

A researcher's phone call used to be settled at once: answered, let ring or missed in the same instant, with no way to hang up before an answer, and the watcher's bar kept saying "calling …". Now, in a paced run, the phone rings for up to 30 real seconds (`controller.ring_seconds`; 0 in an unpaced run, so fast runs and checks keep their timing). A few rings pass before the person reaches it, then they decide. "Let it ring" rings out the rest of the 30 seconds, and asleep or busy means it rings out to a missed call. The caller can hang up at any time while it rings: Tab → End the talk in the watcher, `/bye` in the cockpit, Ctrl-C in `devsim.visit --call`. Hanging up before an answer leaves the person a missed call and makes no pickup model call. Lines typed into a ringing phone are not heard. Simulated time still waits during the ringing, as it does during a call. The watcher's bar now shows how the call ended.

Silence on a call or face-to-face talk (user request): you used to have 5 real minutes, with the person waiting silently and the whole world paused. Now, after 15 seconds of quiet (`SILENCE_SECONDS`), the person checks in with one model decision ("Hello? Are you still there?", or they hang up or turn away). After a second 15-second silence the talk ends. While you type they wait up to 60 seconds (`TYPING_GRACE_SECONDS`). The watcher's `t` prompt and the cockpit's box send a `typing` note; `devsim.visit --call` sends one with every prompt, because a terminal cannot see keystrokes. Also fixed: the "So far" recap in the person's own call prompts named the caller ("Kanishk: …") even when they knew them only as an unknown number. It now uses the name the person knows. Checks: `household` (3 new cases: ring-out timing, hang up before pickup, hang up while asleep). 409 named checks passed (Graphiti skipped). **Not live-verified.**

## Skill acquisition module, 18 October (user spec)

`devsim/skills.py` adds open-ended skills: there is no skill list, and a skill is created when first practised, keyed by its normalized label. The model is the same for everyone:
- reads in closed form, which never change state;
- an exponential approach within a learner and skill;
- gamma-distributed rates, so power-law averages emerge (E2);
- strategy shifts with a dip;
- stability that grows with spacing and retrieval;
- decay ordering by attributes (E12);
- savings, including pruned savings records;
- near transfer only;
- performance lowered by sleep pressure and stress without touching stored skill;
- a competence gate that decides outcomes outside the model, with a directive that describes not knowing;
- self-assessment calibrated to r = .29;
- emergent abandonment through the hormone module's learned value.

All randomness comes from the 7 allowed seeding purposes, and the module makes no model calls.

It is wired into situation options (`skill` field: the check decides success), the living-world catalog (cooking, homework, robot work, paperwork as practice), the free-time menu (practice wanting) and every prompt (`your_skills`). The evidence ledger is `docs/research/skill_acquisition_ledger.md`; parameters are in `docs/PARAMETERS.md`. The report (placeholders, mismatches with the spec, the aptitude flag) is [skills_report.md](skills_report.md). Turn it on with `skills: {}`.

In the control panel, the character card shows skills, the Characters tab can set a skill's level (logged as an intervention; the replay record restarts there), and the builder and start dialog offer the module, which is on by default in new designs. Checks: new suite `skills` (16). These include replay equal to stored state, the E2 AIC test (individual curves fit exponential better, the population mean fits a power law better), determinism by seeding purpose, zero idle computation and no added model calls. **Not live-verified.**

## Control panel app, 18 October (user request)

`python3 -m devsim.app` is one terminal application to see, start, stop, resume, watch, design and steer simulations; see [COCKPIT_IMPLEMENTATION.md](COCKPIT_IMPLEMENTATION.md).
- New modules: `devsim/tui.py` (widgets, logo, Pip the mascot, loading animation; `choose` and `ask` moved here from the watcher), `devsim/runs.py` (run control), `devsim/builder.py` (designs to compiled worlds) and `devsim/app.py`.
- **Live edits and notifications.** New inbox notes `edit` and `notify`, applied by `visit.apply_edit` and `deliver_inbox` at event boundaries, all-or-nothing, and logged as interventions in `runtime.researcher_edits` and `runtime.notifications`.
- **Builder limits.** `author.compile_scenario(limits=…)` lets builder designs go past the one-draft limits; the draft limits are unchanged.
- **Your name is set in the app.** It asks once on first start (Enter keeps your login name), remembers it in `work/control-panel.json`, shows it in the top bar, and `y` changes it. The `--name` flag is gone from `devsim.app`, `devsim.watch` and `devsim.visit`; the watcher and the visit command use your login name.
- **The builder fills one person at a time.** This replaces the one-shot draft, whose repair ran out of the 8k context on 18 October.

- **Fixes after the user could not create a world (18 October).** Tab now cycles Runs → Watch → Characters → New (before, every sub-screen returned to Runs, so Tab only ever reached Watch). `n` lists "Design a new world…" first (before, it only offered already-compiled worlds), and the footer names `4 new world`. A rebuild goes to the next free `compiled-N` folder instead of refusing with "already holds a build"; earlier builds are kept because runs point at them by path. Verified by driving the app in a pseudo-terminal (n → design → build → rebuild; Tab to New) and one new `builder` check. The user's original failing keystrokes were not seen, so these are the dead ends found, not a confirmed match.

Checks: new suites `tui` (4), `runs` (4) and `builder` (5), plus 1 in `household`. 391 named checks plus 12 core checks passed (Graphiti skipped). Pseudo-terminal walk-throughs covered the runs list, a character card with sliders, and a full builder build. **Not yet used to start a live run.**

## Bug fixes from a second pass over the v5 text, 18 October

No simulation was running (only the Graphiti service, left alone), so the finished environment-v5 run was re-read. Six bugs were fixed:
- **Relationships never changed.** With reflection off (as in every compiled policy), nothing moved trust or closeness: after 62 days every tie was still at 0.5 and 0, although beliefs showed clear opinions ("Arun's pattern of reading my messages without replying…").
  - New `society.learn`, run from `Engine.advance` for each received interaction with a known person: each attended contact adds a little familiarity, and its appraisal valence moves closeness and trust toward 1 or 0. GIST counts half; an unattended event counts nothing.
  - Policy key `relationship_learning` (compiled default `{}`; gains 0.05, 0.005 and 0.03 are `[D]`). Reflection, when on, owns this instead.
- **Society news at night.** 53 of 125 society-layer messages reached a sleeping person. `bridge.sync` now holds a person's news until their next waking time (`household.next_waking`).
- **Invented contact between main characters.** 18 messages said one simulated character "got in touch" with another without any such interaction. The society layer no longer reports deaths, fights or contact between two bound characters; their tie still shows in "people in your life".
- **"Family" cue in every conversation.** School and club talk was cued `family`, and 5 of 156 lines argued about "family stuff" nobody had raised. The cue is now added only when the speaker talks with their own family.
- **Own silence appraised every time.** 209 model calls (about 26 minutes) appraised "I listened quietly." at about −0.6 each, pulling the quiet people's mood down through their own silence. Silent and leave turns are now routine notes: appraised once, then reused with fading weight.
- **Invitation before the inviter's day began.** The club invitation went out at 07:00 while the teacher's hours were 8–18. Invitations now wait for both people.

Checks: 4 new, plus 2 extended (population bridge). 376 named checks plus 12 core checks passed (Graphiti skipped). Not live-verified.

## Watcher: character panel, surroundings graph, menus, 18 October (user request)

`devsim.watch` gains:
- **`p` character panel**, sliding in from the right: a generated ASCII face with an expression from mood, stress and sleep pressure, description, mood, hormone and need bars, goals, closest people, latest thought and line, and recallable memories.
- **`m` room map and relationship web.**
- **Menus on `t`.** Talking, phoning, introducing a new character (name, who, age, whom they meet, relationship, confirm), resending a character and speaking to the group are all chosen from lists. `Tab` offers "let the model play" and "end the talk".

Faces use shape-matched ASCII after Alex Harri's method (`devsim/ascii_art.py`, glyph table `devsim/data/ascii_shapes.json`). An introduced character's facets and background are synthesized from the description in one model call (none in scripted runs). A stated relationship becomes a fact for both people at the first meeting, plus one introduction memory marked `researcher_introduced`; no shared past is invented. Details: [COCKPIT_IMPLEMENTATION.md](COCKPIT_IMPLEMENTATION.md).

Checks: new suite `ascii` (5), plus 2 in `watch` and 1 in `household`. The watcher was also driven in a pseudo-terminal through the panel, map, web and the full introduce-a-character menu on a scratch run. 372 named checks plus 12 core checks passed (Graphiti skipped). **Not used with a live model yet.**

## Hormone-state module, 18 October (user spec)

Exactly three lazily advanced variables per person: stress (`stress_x`, phasic, with a closed-form baseline anchored to waking), sleep pressure (Process S gated by the sleep module's night) and tonic dopamine (a leaky integral of reward prediction error). Per-target expectations V(target) are memory, not hormone state. Bonding comes from society-layer closeness in the wanting score, so there is no fourth variable. Design: [hormone_design.md](hormone_design.md); every constant is tagged in [hormone_evidence.md](hormone_evidence.md).
- **Wiring, using existing interfaces only:**
  - one hook per delivered event in `Engine.advance` (stress increment, Rescorla-Wagner step weighted by attention tier);
  - mood (negative impulses scaled by stress, a baseline offset from dopamine and stress);
  - attention (fatigue = sleep pressure, plus an arousal capacity factor that is off by default);
  - the sleep module (night quality times sleep efficiency);
  - a style line in the existing prompt;
  - wanting and initiative in the living-world menu.
- **Constraints met:** no added model calls (checked with a stubbed household run), O(1) per event (timing flat from 5 to 400 agents, and no access to the agents table), seeded draws, no type, role or sex identifiers, and safe defaults without household, attention or sleep.
- **Evidence (read 18 October):**
  - `[V]`: awakening-rise timing (Stalder 2016); lower speech complexity with stress reactivity (Saslow 2014).
  - `[U]`: Process S time constants (seen only as software defaults); more pauses under stress (secondary report of Buchanan 2014).
  - Not found: "more total words", so stress never shortens speech by default.
  - Deviation, recorded `[D]`: the attention tier weights the learning step, not the reward, so an unattended outcome teaches nothing.

Checks: new suite `hormones` (15) and a calibration report `checks/results/hormone-calibration.json` (300 seeded agents: awakening peak at 39 min; declared inputs explain 0.98 of stress reactivity and all of wanting, a nuisance fact none). 364 named checks plus 12 core checks passed (Graphiti skipped). **Not live-verified.** Turn it on with `hormones: {}` in the policy; the compiler does not add it.

## Living world, 18 October (user request)

In v5 Meera kept saying she was worried about Priya but never went to her room: nobody chose to go anywhere in 62 days, and the world never did anything by itself. The user asked for a game-like world (The Sims as the model) that runs on rules, with the model only in people's minds. Guide: [LIVING_IMPLEMENTATION.md](LIVING_IMPLEMENTATION.md).
- **Map:** room `kind` and `site`, with furniture from a catalog by kind. Moving to another site needs a route; that fixes a teleport gap, since `household.travel` used to move instantly when no route existed. Other families' homes and other people's bedroom furniture are off limits.
- **Needs:** hunger, energy, social, fun and hygiene, computed lazily by waking and sleeping hours and raised by activities, conversation and pets. They reach the model as words only, and low energy feeds attention's fatigue signal.
- **Whereabouts:** known only from what a person saw or heard.
- **Free-time choices:** at each inner thought the person picks from a ranked menu (activities in reach, plus people to talk to, go and see, message or play with), in the same model call. A scripted run takes the top option. Choices are carried out by walking, activities with durations, visits that open a conversation (or find the person gone, asleep or busy), messages and bedtime returns.
- **Surroundings without the model:** happenings by room kind (atmosphere, incidents such as a power cut, late bus, fire drill or a slip, off-stage callers), a seeded weather chain, and pets with their own routine. The only model use is an optional TV news sentence.
- **Authoring:** the vocabulary asks for kind, site, homes for everyone and pets. When rooms carry kinds the compiler adds `living: {}`, requires everyone to start in a home room, and requires a route from each group member's home to the meeting site. The dry run skips inner thoughts for speed.
- **Watcher:** each person's current activity and low needs; thoughts, activities and happenings in the feed.

Checks: new suite `living` (15), plus 1 in `author`. 349 named checks plus 12 core checks passed (Graphiti skipped). The stubbed check reproduces the motivating case: a worried thought makes the grandmother walk to the child's room and open a conversation there. **Not live-verified.** All rates and catalog entries are provisional design defaults. The v5 compiled scenario has no room kinds, so it would run without the living world; a recompile from `setting.txt` is needed.

## Real time and inner thoughts, 18 October (user request)

The user wants the world to run at their pace. v5 covered 62 days in 8.1 hours because the engine jumped straight from one event to the next, and a conversation turn took a random 1–5 minutes whatever was said.
- **Real-time pacing.** `Lifetime(..., pace=1)` and `devsim.run_live --pace` (default 1 = one simulated second per real second; 0 is the old as-fast-as-possible mode). Before each event the controller sleeps until the wall clock reaches it. The clock is re-anchored after every event, so time spent waiting on the model never counts: the world stands still while the model writes. Pacing is not in the policy and never changes what happens; a researcher line arriving during a wait advances the world to "now" and is delivered then. At pace 1, the 62-day scenario takes at least 62 real days.
- **A line takes as long as it takes to say.** After each turn the next one starts after the line's own duration (2.5 spoken or 0.67 typed words a second, about 150 and 40 a minute; fixed population averages) plus the reply pause. Compiled scenarios now keep face-to-face reply pauses in seconds (default 3–12 s, capped at 15–30 s); v5 had 1–5 minutes.
- **Inner thoughts** (`policy.inner_thoughts.mean_minutes`, compiled default 3 since 18 October at the user's request; was 20). Each awake person who is not in a conversation thinks to themselves at exponentially spaced moments: one model call (`cognition.think`, purpose `thought`) returns one to three first-person sentences plus valence, arousal and importance, stored as their private internal memory (`@thought:<person>:<n>`). Nobody else perceives it and it establishes no world fact. Live runs only (scripted runs have no words). The rate is an engineering choice; at 7 people and 16 waking hours that is roughly 2,200 calls a simulated day (340 at the old 20 minutes).

Checks: 2 new (paced run waits on the wall clock and ends in the same world as an unpaced one; inner thoughts are private, internal, only while awake and out of conversation); pinned values updated for line durations and reply pauses. 333 named checks plus 12 core checks passed (Graphiti skipped). **Not yet live-verified.** Thoughts do not yet lead to actions by themselves; actions still come from situations and conversations.

## Fixes, 18 October: conversations from the environment-v5 run

`runs/live/environment-v5/` completed 62.09 days (403 actions, 8.1 hours). Its conversations were short and deaf:
- **Every one of the 79 held conversations ended at its turn limit**, 62 of them after 4 turns (the school class: one line each, once per 6.5-hour school day). None ended naturally.
- **Listeners heard 6% of others' conversation turns in full** (82 of 1,371; 58% GIST, 36% NONE). The calm-arousal inverted U halved capacity, classmates' arrivals stayed open as competing "streams" for 15 minutes, and nothing marks group speech as addressed to its participants.
- **GIST threw away meaning.** Kiara's own appraisal gist of Priya's first line was "Priya asked where the robotics room was…", but attention stored "Half-noticed: Priya, something about everyday things." (39% of allocations had no keyword, so the generic 'social' label won). Kiara answered a question she never heard, then mocked "everyday things" for weeks; Ms. Okafor scolded Priya for an "everyday things tangent" she never said.
- **Rohan repeated himself** because his context held his own bragging (FULL) and others' turns as the same gist line. He took no action outside conversations in 62 days, so his "I ran simulations last night" lines are model invention.
- **Meera's kitchen talk (the scenario's day-28 event) never happened**: `day: 28` is midnight, Priya sleeps 22:00–07:00, and room conversations did not bring participants to the room.

Changes:
- `attention.coarse_text`: GIST uses the listener's own appraisal gist; without one and with no keyword it says "something" rather than inventing a topic.
- `attention.allocate`: one-off events (arrivals, room changes) open no competing stream.
- `policies/attention.json`: `arousal_shape` default is now `monotone`. Replayed on the v5 conversation turns, these two changes alone move FULL from 6% to about 69% (GIST 24%, NONE 6%).
- `household`: a conversation ends on its own after a full round with no speech (`everyone fell silent`); `max_turns` is now a safety cap. A group meeting's talk is followed by another after a 1–2 hour break (new topic from its list) until the meeting ends, so a school day holds several talks. Authored room conversations bring available participants to the room and send them back after. Validation rejects a scheduled conversation that starts when fewer than two participants are awake.
- **Invented activities.** `author._check_rooms_and_roles` now requires every person with goals to be the actor of at least one situation; talking in conversations or group meetings no longer counts. The draft prompt says so. The conversation instructions now say to claim having done or seen something only if it is in one's memories, and otherwise to share opinions, plans, questions or feelings. The prompt line is guidance, not enforcement. The v5 compiled scenario fails the new rule (only Priya has situations), so a new run needs a recompile from `setting.txt`.
- `author.compile_scenario` sets every non-interview talk (scheduled conversations, group meetings, option conversations) to the 40-turn safety cap, whatever the draft says; the prompt no longer asks for `max_turns` there and explains a conversation's day fraction as its time of day. Interviews keep two turns per question.

Checks: 5 new (talk-only people rejected, gist text, silent-round end with travel to and from the room, follow-up talks inside a meeting, compile-time rejection of a sleeping conversation); two attention checks now name the inverted U explicitly and the crowd check asks only for fewer traces. 331 named checks plus 12 core checks passed (Graphiti skipped). **Not yet live-verified.** Expect many more model calls per simulated day: each turn costs roughly 6–7 calls. Left open: speaker order is still a fixed round robin (the person addressed does not reply next).

## Latest phase: environment, event-driven authoring, in-scenario interviews, cache compaction

This phase closes the remaining software gaps listed after the cockpit:
- **Environment** ([guide](ENVIRONMENT_IMPLEMENTATION.md)): places beyond home, timed `routes` (commutes with in-transit periods), `groups` for institutions and clubs with recurring meetings, written `channels`, and `invitations` whose acceptance is a committed membership fact.
- **Authoring** ([guide](AUTHORING_IMPLEMENTATION.md)): starting facts, intervention `sets_facts`, situation `requires_facts` (a situation can follow an event or an earlier choice), option effects (facts, relationship roles, conversations), the full environment vocabulary, a reachability check for required facts, and a model review of each draft against its setting that must cite real fields. Draft repairs now return the previous draft. The daily rate cap is 365.
- **Interviews inside scenarios** ([interviews](INTERVIEW_IMPLEMENTATION.md)): scheduled in policy, started by an agent's option, taking simulated time on both calendars, and overheard from audible rooms.
- **Graphiti cache compaction** ([setup](../services/graphiti-local/README.md#cache-compaction)): lease-aware deletion of superseded view caches, a stats endpoint, automatic compaction every 25 indexed views. On this machine it cut Neo4j from 1,855 to 203 nodes.

Verification: all 18 suites ran here, 241 named checks plus 12 core checks, including Graphiti ([manifest](../runs/verification/environment-verification.json)). The new and changed suites are:
- `environment`: 9 checks, 5 mutations caught
- `author`: 13 checks, 3 fact-gating mutations caught
- `graphiti`: 16 checks, 3 compaction mutations caught

**Live 27B evidence for the environment and extended authoring is in progress.** Two drafts of an environment-rich setting used the full vocabulary but failed validation (a rate cap set too low, then a 0-year horizon and an overnight availability window). Those led to the clearer vocabulary, an actionable overnight-window error and repairs that keep the previous draft.

## Fixes, 17 October: repetition loop, personal reactions to repetition, habituation, memory collisions and recall crash from the overnight run

The overnight environment run (`runs/live/environment-overnight/`) failed at day 315.7 after ~5 hours. Its transcript showed Ms. Okafor asking Priya for the same power-budget numbers in ~20 consecutive weekly sessions; 43 of 130 spoken lines were verbatim repeats of the speaker's own earlier words. Six changes:

- **Conversation working memory.** Conversation memories were ranked by word overlap with a situation text identical for every turn, so "Priya listened quietly." ranked 76th of 100 and never reached her context. `household.conversation_memory()` now adds `conversation_so_far` to each participant's action and appraisal context: their own received turns of the current session (last 8) and the end of the previous same room/topic session (last 4, forgetting applied).
- **Repeat check.** `Engine.repeated_speech()`: if a proposed line is ≥80% similar to one of the speaker's own last 10 spoken lines (3+ words), `propose` asks once more with `repeat_notice` showing the earlier words. A second repeat is kept, never fatal. On the overnight actions it would have fired for 47 of 130 lines (one extra action call each).
- **Recall crash.** Semantic recall now accepts ids from the context's own accessible `memories` as well as `memory_candidates`; ids never shown are still rejected.
- **Consolidation by default.** Compiled scenario policies set `consolidation_batch_size: 8` (it was absent, so the overnight run made 0 consolidation calls).

- **Inhibition of return (Memory Decay Research report p.10).** Ms. Okafor recalled one memory 61 times; each rehearsal raised its stability (to 70.6 days), so it kept winning retrieval. `cognition.views()` now divides a memory's ranking score by `1 + boredom_weight × recent recalls` (recalls weighted `exp(-age/boredom_days)`, defaults .5 and 3 days, 30-day window). This is memory mechanics, like forgetting, and is the same for everyone. Stored stability is unchanged. Exposed per memory as `boredom_factor`.
- **Repeated questions are detected and remembered.** When a question arrives from another person, the listener's appraisal sees their last 5 questions from that speaker and returns `asked_before` (an id or null), so rewordings are caught by the model rather than by text similarity (word overlap could not separate them). The link is stored as `repeat_of` with a running `times_asked_before`. Later decisions that day get `repeated_question` (count and first-asked days ago), stated as a fact without prescribing a feeling.
- **Personal reactions to repetition come from the existing situational-personality layer.** Compiled policies now enable `situational_personality` (it was off in the overnight run). Signature generation requires one of each person's five if-then signatures to cover repeated situations (boredom, irritation, going quiet, arguing back, leaving, as their tendencies suggest), and situation construal sees `repeated_question` and `conversation_so_far`, so that signature can activate and shift temporary state and the decision. Conversation menus already offer speak, listen and leave.

- **Routine habituation (fewer model calls).** 1,624 of the overnight run's 2,094 appraisals (2.7 of 5.0 hours) were travel notes. Travel, room-change and conversation-opening deliveries are now marked routine; an identical routine observation (same text and source) reuses the person's own most recent full appraisal within `routine_reappraisal_days` (default 30) without a model call, with valence, arousal and importance scaled by 1/(1+n) over n reuses (`habituated_reuse_v1`, after the Lifestyle Policy in Affordable Generative Agents, arXiv 2402.02053). Replayed on the overnight observations: 1,574 of 1,712 routine appraisals reused (~2.6 hours saved).
- **Memory collision handling.** Identical memories (same text and source) are linked at retrieval, never merged or deleted: the person's context view (`Engine.memories`) shows the best-ranked copy with `times` and `first_day`. Ms. Okafor's top six went from six copies of one opening to six distinct memories, including "I'm counting on that power budget…" ×7. Internal lookups still see every memory. Design follows Graphiti/A-MEM linking; Mem0's merge/delete resolver was avoided because it deleted facts still needed. Paraphrased collisions (different words) are handled only for questions (`asked_before`); a general embedding-based pass with the installed bge-small-en model is the next step.

Checks: 8 new (household working memory, repeat re-ask, repeated-question linking, repetition reaching construal, routine habituation; extended recall citation, inhibition of return, memory collision) plus compiler-default assertions; mutations of collapse, habituation and re-appraisal each fail a suite. All 19 suites ran here: 256 named checks plus 12 core checks, including Graphiti. **Not yet live-verified** with the 27B model. Left as decisions: the model-returned plan still overwrites the stored plan, and mood keeps the provisional power-law kernel (on Priya's overnight appraisals it stays between −0.76 and −0.96; the exponential option recovers to about −0.1 between sessions).

## Fixes, 17 October (continued): scenario plausibility, situation windows, calibration and robustness

An audit of the overnight run found that most failures came from a thin, partly wrong authored world. Only Priya had situations: Arun took 0 actions in 315 days and Meera 2. "Lunch with a group of students" fired while Priya was in the kitchen, at hours such as 07:12. Priya never attended school, and the students did not exist. "Feel comfortable at school" was completed through chatting with her father. The run went to day 315 of a 62-day scenario. 63% of appraisals had |valence| > 0.9 (Arun ≈ +0.9 for every commute, Meera ≈ −0.55 whenever Priya entered or left a room).

- **Authoring checks** (`author._check_rooms_and_roles`): a room labelled as one person's ("Priya's Bedroom") cannot be another person's starting room, except an infant's caregiver; every person with goals must have a way to act on them (situation actor, conversation participant, invitee, or member of a group that meets with someone else). Both reject the overnight scenario. Draft and review prompts now also ask for own rooms, school and work routines as groups, peers as real people, chats as channels, situation place and hours, and goals that fit their situations; these are model-dependent.
- **Situation place and hours.** Situations accept optional `room` and `hours`; an occurrence outside them is postponed to a random time in the next window (rate preserved) and skipped after 14 tries at an unreachable place.
- **Face-to-face reply speed.** Routines accept `in_person_response_minutes` (at most 10), used for room conversations; `response_minutes` stays the written-channel delay. The compiler defaults it to 0.25–2 minutes.
- **Horizon guard.** Compiled policies carry `horizon_days`; `run_live` refuses `--until-day` beyond it unless `--beyond-horizon` is passed.
- **Appraisal calibration anchors.** The appraisal prompt anchors routine events near 0 (within about 0.2) and reserves values beyond 0.8 for rare, major events. Not yet live-verified.
- **Skip, don't crash, for optional steps.** `validated_json` raises `InvalidModelOutput`; semantic recall, reflection, consolidation, signature generation and situation construal record the skip in `runtime.skipped_model_steps` and continue with no state change. Actions and appraisals stay strict; a model server outage still stops the run.
- **Correction:** `run_live --world` accepts any checkpoint, so a failed run can be resumed into a fresh output directory.

- **Travel bug (found by the v2 dry run).** Someone already travelling who was sent somewhere else teleported there (no route or calendar check), and the old arrival later moved them back, mid-meeting. `household.travel` now turns an interrupted traveller back from the walk's recorded origin, cancelling the pending arrival and its calendar slot; group meetings send them afterwards to where they had been heading. Legs from older checkpoints (no origin) cannot be interrupted.
- **Window retries:** only moves to another day count toward the 14 tries; short same-window retries no longer use them up (the club situation had burned all 14 in four days and never fired). The horizon guard allows 0.001 days for the compiler's three-decimal rounding.
- **Environment v2 live run (in progress).** `runs/live/environment-v2/`: new setting with own bedrooms, a daily school class, a family chat channel, and three classmates (Kiara: popular, quick-tempered, dismissive; Rohan: arrogant, takes credit; Dev: shy, kind). The 27B draft's repair overflowed the 8192-token context, so the draft was fixed by hand (`reviewed/`, edits listed in its assumptions); the scripted 62-day dry run exercised school, club (8 meetings, all four members speaking), weekly chats and both windowed situations. Live run started 17 October 04:01 UTC to day 62.093.

- **Watcher engine view.** `devsim.watch` now has `l` (engine view: every model call with what it was asked and what came back: perceived text and scores, situation and options, chosen action and speech, recalled memories out of N candidates, search terms, situation reading and fired personal rules, gists, repairs), `v` (full text), `s` (calls per type, average seconds, repairs, habituated reuses, skipped steps) and a status line (call in flight, sim days per hour, time left to the horizon). `run_live` writes the call in flight to `current.json` (removed when the call ends), so the "now" display appears for runs started after this change; earlier runs show seconds since the last call. The call log is read incrementally.

- **Visitor participation.** `devsim.visit` (and watcher key `t`, `@name` to pick a person's conversation, `--name` for your name) appends lines to the run's `inbox.jsonl`. `run_live` gives the controller that inbox; at each event boundary `Lifetime._visitors` delivers complete lines, atomically with rollback, into the active conversation (lines wait while none is active). Participants and room listeners (or channel members) hear "<name> said: …" from a `visitor-<name>` entity; it uses no turn, enters their conversation memory and is appraised like any speech. The event is labelled a researcher intervention and `runtime.visitor_log` records it; the offset is checkpointed so nothing is delivered twice.
- **Re-asks sample at temperature 0.8** (other calls stay at 0.4): Rohan had repeated a line verbatim even after the repeat notice. Paraphrased repeats still need the planned embedding check. `run_live` now records Ctrl-C as status `stopped`.
- **v2 run resumed.** The first v2 run was stopped at day 7.37 (its `summary.json` was annotated with the stop reason, since Ctrl-C left the status blank) and resumed from its checkpoint into `runs/live/environment-v2/run-2` with the inbox enabled.

Not done: classmates as agents beyond these three, the model's advisory review of the edited v2 scenario (stopped to free the model server for the live run), and live verification of today's mechanisms (pending the v2 run). All 19 suites ran here: 259 named checks plus 12 core checks, including Graphiti; mutations of the window gate, horizon guard, room check and recall skip each fail a suite.

## Fixes, 17 October (memory): exact words fade, sampled recall, rumination by neuroticism, mood at encoding

From the live v2 run (`runs/live/environment-v2/run-2`, inspected at day 32.6 while still running) and the Hopfield/RNN reading (`research/sources/Hopfield Networks is All You Need (blog).*`, `…Neural Memory Machines (TDS).*`):

- **Exact words fade; the gist stays** (Graph DB Memory Decay Implementation p.9, fuzzy-trace theory). Priya was shown a 12-day-old Rohan line word for word, and Rohan his own old lines, which he copied. With cognition `verbatim_days`, each appraisal must also return a ≤25-word `gist` (stored as the memory's summary). `views()` shows exact words only within that window, then the gist. The episode stays accessible and rehearsable, and originals are stored unchanged. Reflection was off in this run, so 0 of Priya's 426 memories had a summary before this.
- **Repeat-check bug.** `repeated_speech` compared characters with difflib autojunk, which ignores common characters in lines over 200 characters: near-copies scored ~0.06 and the check fired 0 times in run-2. It now compares words with autojunk off. Replayed on run-2, it would re-ask 5 of Rohan's 42 lines.
- **Sampled recall (modern Hopfield, Ramsauer et al. 2020 Eq. 22).** With `recall_beta` β, memories are drawn with P ∝ exp(β·score) without replacement, via Gumbel keys hashed from seed, owner, memory, day and query. The draw is reproducible, and inspection stays read-only. `ruminate` uses the same draw.
- **Rumination by neuroticism** (Memory Decay Research "phantom" access; Mood and Memory: neuroticism → rumination). `rumination_neuroticism` k scales each person's background-recall rate by exp(k·n) and leans selection toward negative memories. Compiled policies had never set `rumination_per_year`, so background recall was off in run-2.
- **Mood strengthens encoding** (Mood and Memory pathway 1). `mood_encoding_weight` w: computed stability × (1 + w·|mood valence at the event|). `Engine.mood` takes an optional day.
- **Visitor addressee.** A visitor line with `to` is delivered as "kanishk said to Rohan: …". In run-2 Priya had answered a question meant for Rohan with his project details.
- **Defaults.** New policies (`author` compile, `full_scenario`) take `cognition.MEMORY_DEFAULTS`: `verbatim_days` 1, `recall_beta` 2, `mood_encoding_weight` .5, `rumination_per_year` 12, `rumination_neuroticism` 1. All are engineering choices, listed in the compiler's assumptions. Archived policies lack these keys and behave as before.

Checks: 4 new in `extended` (gist requirement and window; sampling: greedy at high β, wandering at low β, deterministic and read-only; neuroticism rate and lean; mood-strengthened encoding) and a >200-character near-copy in `household`. Undoing each of the six changes fails a suite. All 18 suites ran here: 250 named checks plus 12 core checks. **`check_graphiti` was skipped** so as not to load the service the live run is using. The v2 scenario recompiled with the new defaults, and its 62-day scripted dry run completed (`work/memory-v3-compile/`). Scripted runs make no appraisals, so the gist path is exercised only by the stubbed checks. **Not yet live-verified.** Run-2 was stopped by the user at checkpoint day 33.37 of 62 (status `stopped`; 204 actions, 720 appraisals over 6.7 hours), to improve the engine from its data before any new run.

Not done: meaning-based (BGE embedding) scoring inside `views()`. The engine's Python has no `torch`, so it needs an embedding endpoint on the Graphiti service, and restarting that service would interrupt run-2. Also not done: personality-derived `affect_parameters` (all empty in v2), and catching catchphrase reuse below the 0.8 similarity cut-off. In v2 every class session opens on "School Day", which feeds Rohan the same stimulus daily; that is scenario authoring, not engine code.

## Fixes, 17 October (run-2 review): Graphiti backlog, mood saturation, meaning-based recall, traits → mood, topics, turn length

A review of the stopped run-2 (no new simulation) found:

- **Graphiti never worked in run-2.** Every checkpoint save (one per event) queued a re-index of all 7 people's views. ~24,000 jobs piled up, and 178 of 179 recalls waited 45 s behind them, then fell back to FTS: **2.3 of the run's 6.7 hours.** Fix: the service serves search-requested views first, newest first, and each save drops views queued only by earlier saves. 23,777 stale and 191 abandoned queued jobs were removed (caches only). Measured afterwards: 34 s for a fresh recall over Priya's ~440-memory view, 4.5 s for an unchanged one. The full re-index per view still grows with memory count.
- **Everyone's mood was pinned at the limit** (arousal 0.91–0.96 for all 7, including calm Arun and Meera). Summed power-law impulses with α = 0.5 never level off, so they always reach the 2.0 budget. The report's reference code shares this. Added an opt-in `mood_kernel: 'average'` (an arousal²-weighted average of recent affect, 1-day half-life × inertia, baseline weight 1). Replayed on run-2's events it gives Priya −0.44, Kiara −0.66, Arun +0.01, Meera +0.02, with arousal ≤ 0.43. **Not made the default:** the mood kernel is a standing user decision.
- **Meaning-based recall** (`semantic_matching`): a new service `/embed` endpoint (cached BGE vectors) and a cosine term in `views()`, so "shouted" can cue a memory about "yelled" (measured cosine 0.69). If the service is unreachable, results are flagged `lexical_fallback`.
- **Mood reactivity from traits** (`affect_from_traits`): Mood and Memory's N/E mappings for inertia, reactivity and rumination, computed from current facets and normalized so an average person is unchanged. All `affect_parameters` in v2 were empty.
- **Turn length:** Kiara and Rohan averaged 56–63 words a turn. The speak option now says one spoken turn is usually one to three sentences (guidance only).
- **Rotating topics:** a group meeting `topic` may be a list, used one per meeting. Previous-session memory follows the group. Draft vocabulary updated; `work/environment-v3/scenario.json` is v2 with varied class and club topics (not compiled: compiling runs a scripted dry run, and no runs were to be started).
- `MEMORY_DEFAULTS` now also turns on `semantic_matching` (off in scripted dry runs) and `affect_from_traits`.

Other run-2 observations, not acted on: Priya listened on 47 of 65 turns; Kiara and Rohan never listened; Dev and Arun reused the same content week to week (the word-level repeat check now catches exact repeats); Arun and Meera act about weekly.

Checks: 5 new (meaning cueing and ranking with fallback, traits → reactivity, average kernel, topic rotation with group continuity, /embed, stale-publish supersede). Undoing each change fails a suite, except the queue ordering inside the service worker and the turn-length wording, which have no automated check. **All 19 suites ran here, including Graphiti:** 273 named checks plus 12 core checks. The Graphiti service was restarted on the new code (log `work/graphiti-data/service.log`).

## Phone calls, token logging and watcher graphs, 17 October (user request)

- **Phone calls instead of joining as a character.** `python3 -m devsim.visit RUN --call priya --name Kanishk` (or watcher `c`, then `t` to speak and `/bye` to hang up) rings the person at the next event boundary. They decide whether to answer from their own situation (someone mid-conversation may step away). Unknown callers show as an unknown number; asleep means a missed call; the room hears only their side. The world waits during the call: no simulated time passes. Replies are in `RUN/calls.jsonl`. The older speak-into-a-conversation `say` is kept.
- **Token logging.** Each model call's record in `requests.jsonl` now has `usage` (prompt and output tokens, cached tokens, prompt and generation ms, generation tokens/s, from the llama.cpp server's usage/timings) and a wall-clock `finished`. One live check of the server: ~31 output tokens/s.
- **Watcher graphs (`g`).** Output and prompt tokens per minute and calls per minute (last hour), generation speed and seconds per call (last 60 calls), how each person's days felt (mean appraisal valence per simulated day), the call in flight and the next 5 scheduled events. Runs started before this change have no token or clock data and say so. On run-2 the per-day chart shows Rohan's days turning negative from about day 16.

Checks: phone calls (answer mid-conversation, step away and back, room hears one side, unknown caller, let it ring, missed when asleep, silence timeout; 4 mutations caught), usage recording, graph helpers and the call transcript view. The full-screen watcher was also driven in a pseudo-terminal (graphs and call keys, no errors). All 19 suites: 278 named checks plus 12 core checks. Not live-verified with the 27B model.

## Unique identity handles, 17 October (user request)

Two people can now share a name. In newly compiled worlds (`identity_handles`), each person gets an Instagram-style handle (`@priya0123`, seeded and unique) and is perceived as "Priya (@priya0123)". Testimony that only says "Priya" stays ambiguous between the two, and an @handle resolves exactly. Visitors can address a handle. Archived worlds have no handles and are unchanged. Check: two Priyas in one household scene (distinct handles and lines, ambiguous vs resolved references, visitor addressing, forced handle collision, duplicate rejection). All 19 suites: 274 named checks plus 12 core checks.

## Society layer, 17 October (user request)

Built from "MiroFish Society Layer: Corrected and Improved Design (v2)" in its build order ([guide](SOCIETY_LAYER_IMPLEMENTATION.md), package `devsim/population/`, config `devsim/policies/society-layer.json` with 92 tagged parameters: 5 V, 8 U, 79 D).
- **The implicit population:** 360,000 people by default, each a pure function of (seed, id), with a degree-corrected latent-space edge model and a pair hash, so a neighborhood query costs the same at any population size.
- **Ties:** decay on the memory forgetting curve; contacts are drawn path-independently.
- **Demography:** competing-risk hazards with NFHS-5 anchors, plus a job chain.
- **Joint events:** marriages as joint facts under a commit and rollback protocol.
- **Opinions and spread:** composition-rejection event selection, Deffuant updates with a mean field, and complex contagion.
- **Institutions:** lazy institutions, roles, one sanction formula and collective action.
- **Economy:** a multiplicative opportunity engine.
- **Isolation feedback:** isolation into mortality, grief and threat sensitivity.
- **Model-boundary guards:** opinion clamping, post-checks, fixed personas, conflict floors and a variance monitor.

Engine characters bind into the population (families share a household). Their circle reaches them as received observations through an event-driven Lifetime check, their context gains `social_world`, and spoken turns move opinions by the rule only.

Validation, never counting inputs as results:
- Contact gap falls with closeness (Spearman −0.62), shorter for kin.
- Median first marriage 19.7 (input 19.6); 25% married before 18 (NFHS-5 21.9%).
- **Period total fertility 2.11, running high against NFHS-5's 1.7** because the parity factors are unverified (not tuned, to stay non-circular).
- Heavy-tailed degree and capital.
- Consensus vs fragmentation, agreeing between realized people and the mean field.
- Chunked and reversed resolution give the same statistics.

Checks: new `population` suite, 11 named checks (about 2 minutes). All 21 suites ran here, including Graphiti: 308 named checks plus 12 core checks. Not live-verified with the 27B model.

## Hippocampal buffer and sleep consolidation, 17 October (user request)

Opt-in module ([guide](SLEEP_IMPLEMENTATION.md), `devsim/sleep.py`, config `devsim/policies/sleep-consolidation.json`). With a `sleep` policy block, received experiences go into a per-agent raw buffer (receipt tagged `tier: 'buffer'`). Recall reaches them in full detail with an exponential lability retrievability; a rehearsing recall counts toward their weight. Once an agent has been awake 16 h, the next `advance` step resolves the whole buffer once, in O(buffer) whatever the skip length. The steps are: sleep quality Q from new optional dials (dysregulation, mood-baseline shift, threat sensitivity, reality testing; neutral by default) and mean buffer arousal; a multiplicative trace weight; lability decay before first sleep; a logistic-noise score with age and reality-testing capacity; then promote (stability = encoding S × w_eff^0.5), merge into a similar memory (its S × 1.1) or start a summary-only gist, or drop (hidden from all recall; receipt kept for provenance). Determinism comes from an RNG seeded by (world seed, agent, skip). An optional batched model summarizer and an encoding penalty after poor sleep are both off by default. **Every parameter is a design default, unverified.** Thresholds were set by Monte Carlo so a typical agent promotes ~15%, gists ~49% and drops ~36% of a mixed-arousal day. Archived worlds and policies are unchanged.

Checks: new `sleep` suite, 15 named checks: each step function; many-seed monotonicity in threat sensitivity, reality testing, age and near-floor Q; seed determinism including a checkpoint round trip; a single O(B) resolution for a 50-year skip; the encoding penalty; the batched summarizer; no agent-type branches; and a scripted 2-year `Lifetime` skip (12% episodic, 50% gist, 38% dropped). Embedding-based gist matching was exercised once by hand against the local service, with no automated check. All 20 suites ran here, including Graphiti: 293 named checks plus 12 core checks. Not live-verified with the 27B model; the dials are not yet authorable in `author.py`.

## Face-to-face talks with a person, 17 October (user request)

In environment-v2 run-2 the researcher's lines, spoken into class conversations (days 9–11), were heard and appraised as important but not answered. Three causes: hearers were not told who was addressed (since fixed: the line reads "Kanishk said to Priya: …"); the line did not change whose turn it was; and each 6-turn session closed before the next line arrived (about one model turn per 40 s), so every line landed in the next day's class. New `devsim.visit RUN --talk priya --name Kanishk`, or `t @priya hello` in the watcher, walks up to the person. The world waits, as during a phone call. Every line gets that person's own reply turn (speak, stay quiet or end it), and the decision sees the exchange so far (phone calls now do too). Someone in a group conversation steps aside and comes back afterwards. Others in the room see the visitor arrive and leave, but do not appraise each line, which keeps a reply to about 3 model calls. An asleep, busy or travelling person is not met. Whether the person engages is still their own decision. Checks: one new `household` check and one extended `watch` check. All 20 suites: 294 named checks plus 12 core checks. Not live-verified with the 27B model.

**Person-cued recall and sent characters (same day).** Run-2 Priya remembered Kanishk (acquaintance, 3 memories, beliefs about him), but a talk context built from her checkpoint showed only the label: topic matches outranked her memories of him. Before each talk or call decision, up to 4 of the person's earlier memories involving the other party now go to the top of recall (`retrieval_focus`, policy `person_cued_recall`). `devsim.visit RUN --send Kabir --to priya --who "a new classmate" --age 15` sends the researcher's own character. It is created on first use as a full agent (sampled personality, committed age), introduced by `--who` on a first meeting, and it remembers both sides of every talk. The researcher types its lines, or with `--goal` (or `/auto GOAL` mid-talk) the model plays it toward that aim; typing takes it back, and `/bye` or `--recall` recalls it. It can be asked later how it went (`--talk kabir`, which works wherever it is). People of the simulated world cannot be voiced this way. Check: one new `household` check covering each of these. All 20 suites: 295 named checks plus 12 core checks. The interactive `--send` terminal loop and the 27B behavior are not verified.

**Talking from the cockpit (same day).** The live cockpit (`python3 -m devsim.cockpit RUN_DIR --serve 18090`) now has a "Talk to someone" box read exactly like the watcher's `t` key (shared `visit.talk_line`): `@priya hello` walks up to Priya, plain text continues, `/bye` ends, `/call priya` phones, `/send Kabir @priya a new classmate, 15` sends your character, and `/auto GOAL` lets the model play it. The transcript refreshes every 1.5 s. The watcher's `t` gained `/call` and `/send` the same way. Over SSH with no port forwarding, the terminal watcher (`python3 -m devsim.watch RUN_DIR`) is the way to talk: key `h` opens a talk guide that lists the run's people and gives examples, and it was driven in a pseudo-terminal (guide opens at its top, closes again). It writes to the run's inbox through `devsim.visit`, so the run validates and decides everything. It accepts only JSON requests from its own loopback origin, so another site open in the browser cannot post into a simulation. Static exports and checkpoint-file cockpits stay read-only. Check: one new `cockpit` check. The page was also driven in headless Chromium (start, reply shown, say, character fields, end; light and dark; no sideways scroll at 390 px; no script errors). All 20 suites pass. Not used against a live 27B run yet.

## Fix, 17 October: an open researcher call swallowed later inbox notes

Found with a researcher-tools harness: random calls, talks, conversation lines, hang-ups and sent characters, with and without sleep and attention, across 60 scripted household runs. While a call or talk was open, every later inbox note was read as part of it. A line meant for a group conversation was spoken on the phone, and a second queued call vanished without a record. A note of another kind now ends the open call ("caller hung up") and stays in the inbox for normal delivery. New `household` check, which fails without the fix. All 24 suites: 346 named checks plus 12 core checks.

## Fix, 17 October: a checkpoint split changed when sleep fell

Found with a society-layer resume harness (24 seeded worlds with bound characters, sleep and attention mixes, 30 to 400 days, random split points). Without a household routine, sleep resolved at the first time step after 16 hours awake. That included the closing `advance(until)` of each `Lifetime.run` call, so splitting a run for a checkpoint moved a sleep resolution: 3 of 16 resumed worlds ended with different memory tiers than an unbroken run. The controller's closing advance now passes `sleep_at_target=False`; sleep resolves before the next event instead. Direct `Engine.advance` calls are unchanged. After the fix all 24 harness worlds resume byte-identical, and a new `sleep` check (three split points, no routine) fails without the fix.

All 24 suites: 345 named checks plus 12 core checks.

## Fix, 17 October: coarsened events regained full detail after load or rollback

Found with a randomized invariant harness (1,000 synthetic worlds mixing sleep, attention, cognition, dials, routines and caregiver links, plus 60 scripted household lifetimes with mid-run resumes). `Engine.load` and the controller's rollback rebuild each received memory from the event log, which holds the original text. So every GIST and NONE event regained its full original wording after any resume or failed event. The receipt now records the encoded text (`attention.encoded_text`), and the rebuild uses it. The `attention` resume check now also compares the rebuilt memory cache, and fails without the fix. The harness is now the `invariants` suite (500 seeded worlds, about 9 s). After the fix, every invariant held in all runs:
- mood bounds; no hidden memory in recall, views or context;
- one receipt per received memory; trust and closeness in [0, 1];
- attention tiers consistent with their thresholds; buffer entries tagged as buffered;
- save/load reproduces state, memories and mood exactly.

All 24 suites: 344 named checks plus 12 core checks.

## Fixes, 17 October: fourth review pass (reports, interviews, resume)

- **Reports quoted forgotten memories as current interpretations.** The `checkpoint_memory_view` evidence tool listed every memory's meaning, including dropped, merged and unattended ones (the latter's meaning is a placeholder). Hidden tiers are now skipped, and the tool indexes received memories once instead of scanning per memory.
- **Diagnostic interviews had the same strict memory-citation rule as decisions.** They now share `engine.cited_memories`: ids shown as beliefs or relationship evidence are dropped, not repaired.
- **Verified, no change needed:** a checkpoint resumed mid-run ends byte-identical to an uninterrupted run, with sleep and attention on (new `attention` check) and on the real environment-v4 scenario. There, the only difference is the deliberately random Graphiti cache namespace of a fresh start. A scripted 14-day pass of the v4 scenario runs without errors. Recompiling the v4 scenario now gives the parents a `child` relationship to Priya.

All 23 suites: 343 named checks plus 12 core checks.

## Fixes, 17 October: third review pass (model-output repairs, family links)

- **Wasted repair calls.** environment-v4 had 17 repair calls: 11 action, 5 consolidation and 1 appraisal. All 11 action repairs cited ids the prompt really showed (15 ids in total), belief keys or a relationship's evidence, just not memories. Such ids are now dropped (no recall) instead of costing a repair call; an id never shown is still rejected. All 5 consolidation repairs cited memories shown in the context's `memories`. Those are received evidence and are now accepted; only the batch is marked consolidated. The appraisal repair (arousal out of range) was a genuine one.
- **Parents had no relationship to their child.** `Engine.caregiver` recorded only the child's side. Without it, a parent could not resolve the child's name in a written message, could not revise trust or closeness toward the child in reflection (targets come from context relationships), and was scored as a stranger by attention. The link now also creates the adult's relationship (role `child`), including when the adult is materialized later. Archived worlds are not backfilled.

Checks: 3 new `continuity` checks. All 23 suites: 341 named checks plus 12 core checks.

## Fixes, 17 October: second review pass

- **Grief was skipped** for any character without scenario-set dials (all of environment-v4's): the bridge only shifted `mood_baseline_shift` when a `dials` record already existed. It now creates one. The new `population` check fails without the fix.
- **Attention treated family as strangers:** authored worlds leave closeness at 0, and v4's parents had no relationship record for their daughter. Default closeness now gives caregivers, children and biological parents (from identity facts) `closeness_family` = 0.6 [D].
- **Cockpit agent view showed forgotten memories** when nothing was accessible (it filtered only on a non-empty accessible set), and always without the cognition policy. Hidden tiers are now never shown.
- **SQLite checkpoint save was O(memories × events)** (an event search per memory). It now builds one index.

Open, not changed (design questions):
- A bound character's population twin draws its own dials (used for contact and conflict), while the engine character stays neutral (used for sleep and attention).
- Attention and sleep compound: in a scripted 120-day household run, the child could still recall 14 of 254 experiences (83 unattended, 138 dropped, 19 merged).
- The environment-v4 world ran on the power-law mood kernel, which BUILD_STATE records as a standing user decision. Every character ended at |valence| ≈ 0.9 and arousal ≈ 0.95.

All 23 suites: 338 named checks plus 12 core checks.

## Fixes, 17 October: environment-v4 run review (repetition, consolidation, sleep timing, run robustness)

Found by reviewing the stopped environment-v4 run (11.6 days, 649 model calls):

- **The children's consolidation stopped after day 3.** Each batch took the oldest unconsolidated memories. Dropped ones were never marked consolidated, so they blocked the front of the queue. By day 3 all eight picks were dropped, and consolidation stopped. The hidden-memory fix below removes this; replaying the v4 state confirms that eight usable memories are picked again.
- **Belief feedback loop, the main cause of the daily repetition.** Consolidation wrote lessons about the agent's own conversational habits ("I use servo calibration to pivot conversations"). These went into every action prompt, were followed like a script, and piled up as near-duplicates (Rohan 14, Kiara 19, with word-for-word copies). They also crowded out memories: beliefs took 36% of a prompt, and the trimmer cut memories to two first. The fixes:
  - consolidation now asks for lessons about people and events, not one's own speaking tactics;
  - a near-duplicate lesson (BGE cosine ≥ 0.85, measured: duplicates 0.88–1.0, distinct ≤ 0.80) reinforces the existing belief, with history kept;
  - a prompt shows explicit beliefs plus at most four inferred lessons, situation-related first;
  - beliefs are trimmed to two before memories.

  The merge removes only close duplicates: on v4's beliefs, 57 become 49.
- **People could not see their own words from yesterday.** Sleep had dropped most of their own turns. The previous-session view now includes the gist of what the person said then (first sentence, up to 25 words, from their committed actions). The repeat check also catches a reused run of six words with three content words. On v4's speech that flags 11 of 50 lines, all verbal loops (e.g. Kiara's daily "Wow, the silence is so loud").
- **Sleep happened mid-afternoon.** It now resolves at the end of the routine's night (see the sleep guide).
- **Habituation broke under attention.** Coarsened routine events kept a placeholder as their text, so repeats were re-appraised. Fixed: the original wording is kept for habituation only.
- **One transient model failure ended a whole run.** Timeouts, dropped connections and unreadable JSON are now retried twice (after 5 s and 20 s), with a warning logged each time.

Checks: new `continuity` suite (6 named checks), plus new `sleep`, `context` and `attention` checks. All 23 suites: 336 named checks plus 12 core checks. Not live-verified with the 27B model.

Open risk: `Engine.mood` with the power-law kernel rescans the whole history on every call (cost grows with history²). It dominates the attention suite's 25 s, and it will slow long runs.

## Fix, 17 October: forgotten memories reached the model again

Sleep-dropped and merged memories, and unattended ones, were hidden from recall but still reached the model through four other paths:

- `Engine.consolidate` sent them for reflection and gist building.
- `Engine.appraise` showed them as earlier questions from the same speaker.
- `household.conversation_memory` listed them as recent turns. Without the cognition policy, it also showed them as the previous session.
- `cognition.reflect` could run on them.

A reminder of a dropped memory also replayed its feeling (`Engine.recall`). Every one of these readers now skips the tiers in `sleep.HIDDEN`. Runs made with the sleep policy before this fix (environment-v4) may have consolidated dropped memories. New `sleep` check: one scenario covers all five paths, and it fails without the fix. All 22 suites: 328 named checks plus 12 core checks.

## Attention allocation, 17 October (user request)

Opt-in module ([guide](ATTENTION_IMPLEMENTATION.md), [evidence tags](attention_evidence.md), `devsim/attention.py`, config `devsim/policies/attention.json`). With an `attention` policy block, every delivered event gets a per-listener weight `a` and a tier: FULL, GIST or NONE. The weight comes from four parts:

- **Top-down drive:** trait topic affinity, closeness to the speaker and to people mentioned, and goal match.
- **Bottom-up capture:** surprise, threat scaled by threat sensitivity, and being addressed or named. It is combined with the top-down drive by a soft OR.
- **Capacity:** arousal (inverted U), fatigue, the load of other open streams, and dysregulation. Competing streams and mind-wandering share it.
- **Seeded noise and drift:** logistic noise, and mind-wandering drift within long streams, resolved when the next event arrives.

The effects:

- `a` scales the encoding weight. With sleep on, it scales the buffer's trace weight instead.
- GIST encodes a coarse who/topic/valence line. NONE leaves a hidden `unattended` receipt.
- Mood impulses scale with `a`, in full when the event is captured.
- NONE events are left out of the model context, and GIST events are shown as one line.
- The optional felt-ignored tie penalty is off by default.

There are no model calls and no per-tick work: one allocation per (listener, event), from `Engine.advance` only. **Every parameter is a design default, unverified.** Without the block, or with `enabled: false`, the world is byte-identical (golden check). Built in four committed phases.

Checks: new `attention` suite, 19 named checks:

- spec sanity values and monotonicity with the noise held fixed;
- config validation, the golden regression, and order-independent determinism;
- addressed events captured, and asleep/wake behaviour;
- NONE/GIST encoding and context, emotion scaling;
- 2000-agent dysregulation and threat-sensitivity effects;
- drift (bored vs interested), felt-ignored, and crowded-scene trace reduction with addressed events kept;
- cost (W allocations per W listeners, a single call site), and no agent-type branches.

All 22 suites ran here, including Graphiti: 327 named checks plus 12 core checks. Not live-verified with the 27B model, and no parameter is calibrated.

## Previous phase: researcher cockpit

[Cockpit implementation](COCKPIT_IMPLEMENTATION.md) adds `devsim/cockpit.py`, a local web view of a run built with only the standard library. An **agent perspective** shows one person's current mood, goals and plans, relationships, calendar, own actions and outcomes, and the memories accessible to them now (gist only when faded). It is built only from what that person received. A labeled **researcher view** shows the model-call timeline and every raw event and action. It can write a static HTML file, or `--serve` a loopback page that polls the run and streams the timeline while a live run is in progress.

- **Checks:** 7 new named checks covering read-only loading, perspective isolation, gist-only faded memories, script-safe embedding, the pre-checkpoint live timeline and the loopback-only server ([results](../checks/results/cockpit-engineering-checks.json)). Five deliberate mutations each fail the suite.
- **Browser:** the static cockpit of the authored Graphiti run rendered in headless Chromium in light and dark themes at 1280 and 390 px with no script errors or overflow. A browser-driven live test streamed new calls and switched to full views when the checkpoint appeared ([evidence](../runs/live/cockpit-live/README.md)).
- **Not yet:** mood history, recall reconstructed at earlier days, a staged setup wizard and side-by-side run comparison. (Mid-run state works: checkpoints are written after every event. A terminal watcher, `devsim.watch`, was added for machines without port forwarding.)

## Earlier phase: evidence-linked reports

[Report implementation](REPORT_IMPLEMENTATION.md) adds `devsim/report.py`. Deterministic, read-only **tools** turn a checkpoint into numbered evidence items: observed outcomes (controller events, resolved actions, utterances labeled unverified, state changes since the initial world) and agent interpretations (current memory meanings and prior versions, optional Graphiti searches). The local model then **outlines** sections and **writes** typed claims (observed, agent interpretation, researcher inference). Each claim must cite evidence of the matching category or it is repaired or rejected. `report.md` labels every claim and keeps the executed tool results in a separate appendix.

- **Checks:** 9 new named checks, including read-only tools, category assignment, citation discipline, repair, rendering separation and logging graph failures as tool errors ([results](../checks/results/report-engineering-checks.json)). Four deliberate mutations each fail the suite.
- **Actual HauhauCS 27B:** a report on the authored scenario's Graphiti run, with 5 calls, no repairs, 65 evidence items and 23 claims. Unprompted, it flagged the day-5 club claim that contradicts the day-10 invitation ([evidence](../runs/live/report-live/README.md)).
- **Not yet:** deterministic contradiction detection, cross-run or cross-seed comparison, reconstructing what someone knew at an earlier time, and paging for runs with more evidence than the 8192-token context allows.

## Earlier phase: scenario authoring

[Authoring implementation](AUTHORING_IMPLEMENTATION.md) adds `devsim/author.py`. The local model **drafts** a `scenario.json` from a plain-language setting in a small supported vocabulary (people, household, recurring situations, interventions, assumptions); the draft is accepted only if it compiles, with field-named repair feedback. The researcher reviews it, then a deterministic **compile** step (no model) builds `initial.json`, `policy.json` and `assumptions.json` (every generated number with its path, the compiler defaults and the stated assumptions) and dry-runs the policy with the scripted provider.

- **Checks:** 9 new named checks: compiled people/caregivers/goals/facets, background as labeled private day-0 experience, intervention recipients, the assumptions report, the dry run, determinism, resume from the saved world, a 19-case field-named rejection table, and model-draft repair ([results](../checks/results/author-engineering-checks.json)). Three deliberate mutations each fail the suite.
- **Actual HauhauCS 27B:** the draft compiled after one field-named repair (2 calls, 218 s). Review found a pre-written outcome, a testimony with no person as its source (the compiler now rejects this) and a routine contradicting the setting. The reviewed spec dry-ran for 58 days: 8 resolved actions, nothing pending. A live run with Graphiti recall made 45 calls with 8 graph recalls, no fallback and no repairs; Priya claimed a club meeting before her invitation, seeded by an authored outcome text that mentions the club and can fire early; the speech stayed an unverified utterance ([evidence](../runs/live/author-live/README.md)).
- **Graphiti on the cluster machine:** installed without Docker or root (Neo4j 5.26.32 tarball, JRE 21, pinned Python 3.12 lock); `start.py` gained `--llm-url` and a local-Neo4j path ([setup](../services/graphiti-local/README.md)). `check_graphiti` now runs here.
- **Not yet:** situations triggered by interventions, an effects vocabulary, institutions/groups/channels, checking a draft against its setting.

## Earlier phase: agent interviews

[Interview implementation](INTERVIEW_IMPLEMENTATION.md) adds `devsim/interview.py` with two explicitly separate modes. A **diagnostic** interview questions a frozen copy of the world, in batches of agents × questions, and leaves the run unchanged (checked by state hash). An **in-world** interview is an explicit intervention: a committed identity asks in person, each question is an appraised received event, each reply a committed action, and the result is a new checkpoint. Answers in both modes are labeled generated accounts, not access to true causes.

- **Checks:** 14 new named checks, including information isolation, frozen diagnostics, atomic rollback, id reuse, eligibility, JSON/SQLite restoration and resume under the archived policy ([results](../checks/results/interview-engineering-checks.json)).
- **Actual HauhauCS 27B:** a batch diagnostic of the household scene (4 agents × 2 questions, 8 calls) in which the closed-room agent reported no memory of the conversation, and an in-world interview of Alex by Maya (2 questions, 14 calls) that reached only them and changed no world facts ([evidence](../runs/live/interview-live/README.md)). Graphiti was unavailable on this machine, so recall used the recorded private full-text fallback.
- **Not yet:** interviews scheduled inside scenario policies, agent-initiated interviews, time cost and overhearing for in-world interviews.

## Earlier phase: household environment and conversation

[Household implementation](HOUSEHOLD_IMPLEMENTATION.md) is the newest layer. It adds explicit rooms and audibility, private multi-turn conversation, waking windows and response intervals, and elapsed calendar reservations. These connect to the existing scheduler, memory/mood and optional cognition/development paths. Use `python3 -m devsim.household_example` for a short scene or `python3 -m devsim.simulate --household` for fresh combined policies. Archived policies keep their original behavior.

- **Recorded verification:** 13 suites, **185 named checks plus 12 core checks**, including 24 household checks ([manifest](../runs/verification/household-verification.json)).
- **Actual HauhauCS 27B scene:** four independent turns, 23 calls, no Graphiti fallback; a closed-room person received none of it ([summary](../runs/live/household-live/run/summary.json), [transcript](../runs/live/household-live/transcript.md)).
- **Seven-year scripted combined run:** 61 resolved actions including 16 conversation turns, six agents, matching restored checkpoints ([integrity](../runs/scripted/household-lifetime-final/integrity-checks.json)).
- **Source-version boundary:** optional crystallization and sample-clock refinements are locally checked; the preserved live trace precedes them.

These are engineering results, not measured human fidelity. Scenario authoring, reports and a researcher cockpit have since been implemented.

## Implementation map

| Layer | Implementation | Remaining limit |
|---|---|---|
| Personality, mood, private memory, provenance | `devsim/engine.py`, `personality.py`, `identity_state_prototype.py`, `expression.py`, `references.py` | Facet-to-behavior language and coefficients are provisional. |
| Situational variability | `situation.py` (CAPS-style signatures, construal, bounded temporary offsets; infant sensory triggers) | Domain modifiers and recovery half-life are assumptions. |
| Development, attachment, inheritance | `development.py`, `temperament.py`, `profile_population_v1.py` | Adult-to-child extrapolation is labeled; no child norms. |
| Semantic recall, gist-only access, interference | `cognition.views` / `semantic_recall`, `retrieval.py`, local Graphiti/Neo4j/BGE retrieval (`graphiti_bridge.py`, `graphiti_service.py`, `graph_tools.py`) with explicit private-FTS fallback | Retrieval is bounded and not guaranteed exhaustive; thresholds are provisional. |
| Society layer (opt-in) | `devsim/population/`: implicit graph, ties, demography and joint events, opinions, institutions, economy, isolation feedback, guards, engine bridge | 79 of 92 parameters are design defaults; total fertility runs about 0.4 high; mean field is well-mixed; not live-verified. |
| Attention allocation (opt-in) | `attention.py`: one allocation per (listener, event) in `Engine.advance`; coarse GIST / hidden NONE encoding; attention-scaled mood; tier-aware `views`/`memories`/`conversation_memory` | All parameters are unverified design defaults; surprise, fatigue, asleep and goal-match providers return neutral defaults; runs after the LLM appraisal, so it saves no calls. |
| Hippocampal buffer and sleep consolidation (opt-in) | `sleep.py`: raw buffer at encoding, one O(buffer) triage per sleep opportunity in `Engine.advance`, buffer-aware `views`/`memories`, rehearsal counting | All parameters are unverified design defaults; no circadian schedule; optional dials are not derived from traits. |
| Evidence-based reinterpretation and self-narrative | `cognition.reflect`: retain/defer/revise with received evidence, preserved originals/versions | Evidence-ID validity does not prove semantic correctness. |
| Autonomous recall, planning, budgets, habits | `cognition.ruminate`, `calendar_time.py`, `life_policy.py`, `goal_plans.py` (ordered action-bound steps, received-outcome completion) | Action libraries and progress amounts remain controller-authored. |
| Families, histories, social questions | Parent-first/inherited initialization, lazy activation, `biography.py`, `society.py` | Generated prose has no unrestricted coherence guarantee. |
| World transitions, births, newborn opportunities | `life_policy.apply_effects`, `lifetime.py` world/hazard queues and birth registration | Explicit scenario processes, not calibrated demography or economics. |
| Household rooms and dialogue | `household.py`, `calendar_time.py`, `lifetime.py` queues | Topics, placements and latencies are scenario assumptions; spoken claims are not verified facts. |
| Places, groups, channels, invitations | `household.py` routes/groups/channels/invitations; `lifetime.py` `trip`/`group`/`invite` queue events | Fixed travel times and meeting intervals; membership only grows through invitations; no transport, capacity or weekday model. |
| Researcher interviews | `interview.py`: frozen diagnostic copies and in-world interviews; household conversations in interview mode (scheduled, agent-initiated, timed, overheard) | Answers are generated accounts; questions are fixed in advance with no follow-ups. |
| Scenario authoring | `author.py`: model draft, field-cited model review against the setting, deterministic validated compile with fact gating, effects and environment, assumptions report, scripted dry run | Review is advisory; reachability does not guarantee timing; trust, closeness and resources are not authored. |
| Evidence-linked reports | `report.py`: read-only evidence tools, model outline and sections with typed, category-checked citations, separated rendering | Claims are checked for citation type, not truth; contradictions are found by the model; one checkpoint per report. |
| Researcher cockpit | `cockpit.py`: agent perspectives (accessible memories, mood, goals/plans, relationships, calendar, own actions) and a labeled researcher view; static HTML or loopback live polling | No mood history or past-day recall reconstruction; live view streams calls, not mid-run state. |
| Storage | JSON and SQLite checkpoints (`graph_store.py`); Graphiti index is derived, not canonical, with lease-aware compaction | The embedding cache is not compacted; no population-scale profiling. |

`devsim/lifetime.py` is the scheduler that ties these together; `devsim/full_scenario.py` builds the combined policy that `simulate.py` launches.

## Verification

Run every suite and the core demo from the repository root:

```sh
python3 -m checks.run_all            # add --skip graphiti without the local Graphiti service
```

**Cockpit phase (16 October 2026):** all 17 suites ran here with 224 named checks, including the 7 new cockpit checks and `check_graphiti`; all 12 core checks passed ([manifest](../runs/verification/cockpit-verification.json)).

**Report agent phase (16 October 2026):** all 16 suites ran here with 217 named checks, including the 9 new report checks and `check_graphiti`; all 12 core checks passed ([manifest](../runs/verification/report-verification.json)).

**Scenario authoring phase (16 October 2026):** all 15 suites ran here with 208 named checks, including the 9 new authoring checks and `check_graphiti` against the newly installed local service; all 12 core checks passed ([manifest](../runs/verification/author-verification.json)).

**Interview phase (16 October 2026):** 13 suites ran with 187 named checks, including the 14 new interview checks, and all 12 core checks passed. `check_graphiti` was not run because the Graphiti service is not configured on this machine; with its last recorded 12 checks, 14 suites now record 199 named checks ([manifest](../runs/verification/interview-verification.json)).

**Restructure re-verification (16 October 2026).** After moving the code into the `devsim` package:

- 12 suites passed with 173 named checks, and the core demo passed all 12 core checks. The regenerated `checks/results/*.json` match the committed results exactly.
- `check_graphiti` needs the local Graphiti service, which is not configured on the machine where the restructure ran (`work/graphiti-data/service.json` is missing). It failed the same way before and after the move. Its last recorded pass (12 checks) remains in `checks/results/graphiti-engineering-checks.json`.
- A three-year scripted household simulation produced byte-identical `world.json`, `summary.json`, `policy.json` and `initial.json` before and after the move. So did the sampled demo, `initialize_life --integrated --inherited` and the scripted household scene.
- The live launcher was wiring-checked only: the `run_live` child process starts and stops at the unreachable model API. No actual-model run was repeated.

## Key evidence runs

All recorded runs live under [`runs/`](../runs/README.md). Their contents are unmodified, so internal paths refer to the pre-restructure layout.

| Run | What it shows |
|---|---|
| [`runs/live/cockpit-live`](../runs/live/cockpit-live/README.md) | Static cockpit of the authored Graphiti run, browser screenshots and the live-mode test (above). |
| [`runs/live/report-live`](../runs/live/report-live/README.md) | 27B report on the authored scenario's Graphiti run (above). |
| [`runs/live/author-live`](../runs/live/author-live/README.md) | Live 27B scenario draft, the human review edits, the compiled result, and live runs of it without and with Graphiti recall (above). |
| [`runs/live/interview-live`](../runs/live/interview-live/README.md) | Batch diagnostic and in-world interviews of the household scene with the 27B model (above). |
| [`runs/live/household-live`](../runs/live/household-live/run/summary.json) | Household dialogue with the 27B model (above). |
| [`runs/live/graphiti-live/run-verified`](../runs/live/graphiti-live/run-verified/integrity-checks.json) | Five calls and one action with graph-based recall, no fallback, privacy preserved, JSON/SQLite restoration matched. |
| [`runs/live/goal-plans-success-live`](../runs/live/goal-plans-success-live/run/summary.json), [`goal-plans-live`](../runs/live/goal-plans-live/run/summary.json) | Controlled fixture completing two outcome-linked plan steps; default-policy failure left its goal unfinished and requested replanning. |
| [`runs/live/full-build-live`](../runs/live/full-build-live/run/integrity-checks.json), [`full-build-infant-live`](../runs/live/full-build-infant-live/run/integrity-checks.json) | Seeded adult (18 calls, two actions) and infant (17 calls, two actions, two safe output repairs) fixtures. |
| [`runs/scripted/full-lifespan-final`](../runs/scripted/full-lifespan-final/integrity-checks.json) | 85-year scripted lifecycle: 209 resolved actions, a new generation, three deaths. |
| [`runs/live/development-lifetime-live`](../runs/live/development-lifetime-live/report.md) | Birth-to-22 developmental scenario completed across a resume (31 resolved actions). |
| [`runs/live/integrated-live-example`](../runs/live/integrated-live-example/report.md) | Short integrated fixture: semantic recall, biography slots and evidence-linked reinterpretation. |

Scripted runs skip model-only cognition. Short seeded live fixtures do not exercise every branch and are not full live lifespans.

## Remaining scope

The accepted software paths exist. Empirical coefficients, child norms, instrument/TGA mapping, semantic truth and consistency of generated prose, population/economic/clinical calibration, and Graphiti performance at population scale remain open (lease-aware compaction exists; it is not profiled at that scale). Comparative evaluation is paused until the integrated system is complete. See [the source-to-code audit](source-to-code-audit.md) for mechanism-level status and [RESUME.md](RESUME.md) for checkpoints and reconnecting to the model server.
