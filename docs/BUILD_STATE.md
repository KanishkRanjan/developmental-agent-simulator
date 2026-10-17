# Build state

Updated 17 October 2026 (memory fixes from the v2 run; environment and authoring-gaps phase). This is the single current status file. Earlier milestone sections, with their original counts and wording, are in [the build-state log](history/BUILD_STATE-log.md) and the other [history documents](history/README.md). Where they disagree with this file or [the source-to-code audit](source-to-code-audit.md), this file and the audit win.

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
