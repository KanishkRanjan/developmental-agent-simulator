# Hippocampal buffer and sleep consolidation

Module: [`devsim/sleep.py`](../devsim/sleep.py). Config: [`devsim/policies/sleep-consolidation.json`](../devsim/policies/sleep-consolidation.json). Checks: [`checks/check_sleep.py`](../checks/check_sleep.py) (15 named checks). Design reference: the "Sleep Memory Simulator Research" report ([Google Doc](https://docs.google.com/document/d/17MVxfwvO8nnGoMbdLVewMqoeEvJdQgUcLDQMYjdlSKc/edit)), section 13. Its equations are missing from the export, so the formulas below come from the user's specification. **No number in this module is a verified effect size.**

Opt-in: a world uses the module only when its config has a `sleep` block, set by `sleep.configure(engine, overrides)` or by a `Lifetime` policy key `"sleep": {...}`. Archived worlds and policies replay unchanged.

## 1. Integration plan (step 0)

1. **Encoding and the memory schema.** `Engine.advance()` applies each due event. For every recipient it builds an immutable `Observation` (event id, day, text, source, valence, arousal, encoding stability) in `engine.world` and an `agent['memory_meta'][event_id]` record (kind, confidence, importance, meaning, encountered, provenance, stability_days, encoding_stability_days, last_recall_day, optional summary/topics). `memory_meta` doubles as the agent's *receipt* record: beliefs, development, crystallization, firsthand relationships, reminders, repeated questions and habituation all check that an event id is in it, often within the same awake period. **Choice:** with `sleep` on, the receipt is still written, tagged `tier: 'buffer'`, and a separate raw entry goes into `agent['hippocampal_buffer']`. Sleep then sets the tier to `episodic`, `gist`, `merged` or `dropped`. Removing receipts would break ~15 validators and the project rule to preserve original provenance.
2. **The time-skip resolver.** No separate resolver exists. Time moves only through `Engine.advance(day)`, which jumps straight to each due event; `Lifetime._run_events` (event-driven queues) drives it, and empty intervals cost nothing. **Choice:** `advance` calls `sleep.due(engine, day)` before each event and at the target day. An agent is due once `day ≥ wake_day + min_awake_hours`; the whole buffer is then resolved once, and `wake_day` becomes `day`.
3. **Existing state used.** Stability from arousal: the encoding formula in `advance` (`base × (1 + w_imp·importance + w_ar·arousal)`, optional mood term), stored as `encoding_stability_days`. Retrievability: `identity_state_prototype.recall_availability` = (1 + t/9S)⁻¹, called from `cognition.views` and `Engine.memories`. Mood: `Engine.mood(owner, day)` (valence −1..1). Age: `(day − birth_day)/365.25`. **The four illness dials do not exist** (the audit lists mental health as an excluded extension). **Choice:** optional per-agent `agent['dials']`, set by `sleep.set_dials()` with range checks: dysregulation 0..1, mood_baseline_shift −1..1, threat_sensitivity 0..1, reality_testing 0..1. Missing dials are neutral (0, 0, 0, 1). Transient mood is not used for Q: a mood at the start of a years-long skip should not set years of sleep, and mood already strengthens encoding (`mood_encoding_weight`).
4. **Rehearsal.** This already exists: `Engine.recall(rehearse=True)` multiplies S by (1 + `rehearsal_gain`), capped, and resets `last_recall_day`, at most once per `rehearsal_gap_days`. **Choice:** it is wired in rather than duplicated. Recalling a buffered entry increments its `rehearsal_count` and leaves S alone (rehearsal enters the trace weight instead). After promotion the existing rule applies. No new `rehearsal_multiplier`; the existing `rehearsal_gain` is that parameter.
5. **Embeddings and retrieval.** Nodes store no embeddings. With the cognition flag `semantic_matching`, `cognition.views` gets BGE vectors at query time from the local Graphiti service (`graphiti_bridge.vectors`, cached in process) and falls back to word overlap. Retrieval goes `views()` → FTS5 index (`retrieval.py`) or Graphiti (`graphiti_bridge.candidates`) → model rerank. **Choice:** gist matching reuses `vectors` under the same flag, with a participant-and-word overlap fallback.

## 2. Data flow

```
event delivered ──► Engine.advance ──► Observation + receipt (tier 'buffer') + hippocampal_buffer entry
                         │                (raw text, participants, arousal, valence, novelty,
                         │                 self_relevance, rehearsal_count = 0, source_event_id)
                         │
   live phase:  recall reaches buffer entries in full detail; retrievability = lability(age)
                a recall with rehearsal increments rehearsal_count
                         │
   next advance with day ≥ wake_day + 16 h  ──►  sleep.resolve_sleep (once, O(buffer))
        Q ─► weight w ─► lability decay ─► score s = ln w_eff + ln Q + ln age + ln capacity + σ·Logistic
                         │
        s ≥ θ_episodic ─► tier 'episodic', S = S_enc · w_eff^0.5        (normal recall from now on)
        θ_drop ≤ s      ─► similar long-term memory? ─ yes ─► its S × 1.1; entry tier 'merged' (hidden)
                         │                            └ no  ─► tier 'gist': recalled only as a summary
        s < θ_drop      ─► tier 'dropped' (hidden from all recall; receipt kept for provenance)
```

The record (`SleepResolutionRecord`: Q, thresholds, seed, counts, entry ids per outcome) is stored as `agent['sleep']['last']` and logged at debug level by the `devsim.sleep` logger.

Formulas, as specified:
- Q = clip(q_base · (1 − a_dysreg·dysregulation) · (1 − a_mood·max(0, −mood_baseline_shift)) · (1 − a_threat·threat_sensitivity) · (1 − a_stress·mean buffer arousal), q_floor, 1)
- arousal_eff = arousal · (1 + threat_gain·threat_sensitivity) if valence < 0, else arousal
- w = (1 + k_arousal·arousal_eff)(1 + k_rehearsal·ln(1 + rehearsals))(1 + k_self·self_relevance)(1 + k_novelty·novelty)
- delay_days = max(0, first sleep − encoding day) / max(Q, q_floor), with first sleep = wake_day + min_awake_hours; w_eff = w · lability(delay_days), where lability(d) = exp(−λ·d)
- age_mult = 1 up to age_decline_start, linear down to age_floor at age_decline_end; capacity = 1 − rt_strength·(1 − reality_testing)

## 3. Parameters

All are **design defaults, unverified**, tunable in the config file or via `sleep.configure(engine, {...})`. The file also holds each parameter's allowed range.

| Parameter | Default | Meaning |
|---|---|---|
| `min_awake_hours` | 16 | hours awake before the next step counts as a sleep opportunity |
| `q_base`, `q_floor` | 0.9, 0.1 | Q with neutral dials and a calm buffer; lowest Q |
| `a_dysreg`, `a_mood`, `a_threat`, `a_stress` | 0.5, 0.5, 0.2, 0.3 | Q loss at the extreme of each term |
| `threat_gain` | 2.0 | extra weight on negative arousal at full threat sensitivity |
| `k_arousal`, `k_rehearsal`, `k_self`, `k_novelty` | 1.5, 0.7, 0.5, 0.5 | trace-weight gains |
| `novelty_default` | 0.5 | novelty of a non-routine experience; a habituated repeat gets 1/(1 + exposures) |
| `lambda_lability` | 0.5 /day | buffer retrievability decay and pre-sleep decay |
| `sigma` | 0.5 | logistic noise scale |
| `theta_drop`, `theta_episodic` | 0.15, 1.4 | triage thresholds |
| `age_decline_start`, `age_decline_end`, `age_floor` | 60, 90, 0.6 | age multiplier |
| `rt_strength` | 0.3 | capacity loss at reality testing 0 |
| `promote_stability_exponent` | 0.5 | S = S_enc · w_eff^exponent (episodic and new gist) |
| `sim_threshold`, `sim_threshold_embedding` | 0.6, 0.75 | merge threshold for the overlap fallback / BGE cosine |
| `gist_stability_gain` | 0.1 | a merged gist multiplies the matched memory's S by 1.1 |
| `encoding_penalty`, `encoding_penalty_strength` | false, 0.5 | after poor sleep, new memories' S × (1 − strength·(1 − Q)) |
| `summarizer`, `llm_batch_size` | `extractive`, 16 | gist text source; memories per model call |

**How the thresholds were set.** A Monte Carlo of 40,000 entries for a typical agent: neutral dials, age 30, arousal and importance uniform on [0, 1], valence uniform on [−1, 1], novelty at its default, no rehearsals (a day's buffer is rarely recalled before sleep), encoding times uniform over the 16 waking hours. Q came out at 0.76 (stress from mean arousal 0.5). θ_drop and θ_episodic are the rounded 35th and 85th percentiles of the triage score. Result: 15% episodic, 49% gist, 36% dropped. The same agent at the dial extremes (Q 0.15): 0.6% episodic, 5% gist, 94% dropped. The scripted `Lifetime` integration check gives 12% / 50% / 38%. `threat_gain` was raised from 1.0 to 2.0 during the checks: because threat sensitivity also lowers Q (and so increases lability), at 1.0 the net gain for a high-arousal negative memory was only ~2 points of promotion probability. At 2.0 it is ~10 points (1500-seed check). The typical-agent calibration has threat 0, so it is unaffected.

## 4. Design choices without verified evidence

- The three-way triage and both thresholds (a discretization of a continuous process, as the report itself says).
- Every coefficient in the table, including the multiplicative weight form and the logistic noise.
- One sleep opportunity = 16 waking hours since the last resolution. There is no circadian clock or sleep schedule: a long event-free gap counts as one resolution covering all its nights, and an all-nighter in event time is not modeled. Sleep is placed at `wake_day + 16 h`; its timing is not sampled.
- Q is a single per-skip value. A multi-year skip uses the dials and mean buffer arousal at resolution time and the age at the skip's end.
- The dials are new optional per-agent state, neutral by default. Nothing derives them from Big Five facets (the report found no verified link).
- Self-relevance is the appraised `importance`. Novelty is `novelty_default`, or 1/(1 + exposures) for a habituated routine repeat.
- Retrieval of buffered entries uses the lability exponential as retrievability, always with full detail (exact words still follow `verbatim_days`).
- Gist matching: mean Jaccard of participants (when either has any) and content words, or BGE cosine. "Extend" means merging into a gist created in the same night; earlier memories are only strengthened. The gist boost is multiplicative, like rehearsal.
- New gist memories keep the receipt's participants (`encountered`) and topics and are recalled only as a summary, with no exact words or detail. This codebase has no temporal or contextual edges, so "dropping" them means hiding detail. The extractive summary is the appraisal's own gist when present (live runs request one), else the first sentence clipped to 25 words.
- Promoted stability = encoding stability × w_eff^0.5, capped at `max_stability_days`.
- The encoding penalty (off by default) applies to stability computed in the awake period after a resolution.

## 5. Changes outside the module

| File | Change | Why |
|---|---|---|
| `devsim/engine.py` | `advance`: call `sleep.due` before each event and at the target day; write the buffer entry after the receipt; apply the encoding-penalty multiplier. `memories`: skip hidden tiers, lability for buffered entries, summary text for gists. `recall`: buffered entries count rehearsals; hidden entries never rehearse. | Encoding path, time-skip hook, legacy retrieval path, rehearsal wiring. All behind `'sleep' in config`. |
| `devsim/cognition.py` | `views`: skip hidden tiers, lability retrievability and full detail for buffered entries, gist tier summary-only. | The main retrieval path (Graphiti and FTS candidates are built from it). |
| `devsim/graphiti_bridge.py` | `snapshot`: a gist memory keeps its participant links (`reference_ids`). | Spec: gists keep participant edges; the snapshot otherwise strips links from non-detailed memories. |
| `devsim/lifetime.py` | Validate and apply a `sleep` policy block; attach the batched model summarizer in live (non-scripted) runs when `summarizer` is `llm`. | Lets scenario policies enable the module; the summarizer needs the run's API and model. |

## 6. Awkward points and limits

- **Backstory.** The lazy life-history machinery (`biography.py`, `life_policy.expand_background`) deliberately creates no memories (`synthetic_initialization_not_episodic_recall`). Every experience arising during a skip is already a scheduled event through `advance`, so it goes through the same buffer and triage. Nothing needed rerouting.
- **Many events inside one skip.** Resolution runs at the first event after each 16-hour waking span. A skip containing N events can therefore resolve up to N times, but each entry is triaged exactly once, so total work is O(buffer + N). An event-free skip of any length resolves once.
- **Receipts stay.** Dropped and merged entries are invisible to every recall path (`views`, `memories`, Graphiti snapshots, rumination, consolidation in cognition mode). Their receipt stays for provenance and validators, and in the SQLite audit graph and `report.py`, with the tier recorded. Habituation still sees the received text of a dropped routine event (familiarity, not recall). The non-cognition `consolidate()` path does not filter tiers.
- **Gist matching cost.** O(gists × long-term memories) per night (`shortcut:` comment in code). Embeddings are batched once per night and cached.
- **LLM summarizer.** Implemented and checked with a stub; not run against the 27B model. With `semantic_matching`, the embedding path was exercised once by hand against the local service (a paraphrase merged, an unrelated event became a gist). It has no automated check.

## 7. Suggestions (not implemented)

- Preserve the report's text under `research/sources/` with a manifest entry, like the other reports, so code comments can cite page numbers.
- If household routines are present, place sleep in their unavailable hours instead of a fixed 16-hour clock.
- Use the mean of mood valence over the skip (closed form for the exponential kernel) as an optional Q term, if the user wants transient mood to count.
- Index long-term memories by participant to bound gist matching in large worlds.
- Calibrate the triage proportions against run data once a live run uses the module.
