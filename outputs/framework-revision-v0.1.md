# Personality and social simulation: corrected core specification v0.1

Prepared 16 October 2026.

> **Status correction after reading the corrected full conversation:** This is a partial technical correction document, not the complete framework or a record of the user's final choices. The full conversation shows that several issues below had already been identified, and the numerical reconsolidation implementation was explicitly rejected. Read [the full-conversation review](full-conversation-review.md) for the design's evolution, family and spawning mechanisms, accepted ideas, and unresolved issues. The checks below remain useful for evaluating source-report examples, but must not be attributed automatically to an accepted or implemented model.

## Scope and status

This is a replacement specification for the confirmed problems in the supplied memory, reconsolidation, and life-event designs. It preserves the intended direction: agents develop through experiences, relationships, memory, appraisal, and behavioral feedback.

It is not an implemented engine, an exhaustive audit of all eight reports, or evidence that the system accurately replicates people. No runnable application was supplied in this chat. The PDF originals remain unchanged. The mathematical checks noted below were evaluated directly; the acceptance scenarios specify future engine tests and have not been executed against an application.

Sources reviewed for these changes:

- Graph DB Memory Decay Implementation, especially pages 3–8.
- LLM Agent Memory Decay Research, especially pages 11–14.
- LLM Agent Memory Reconsolidation, especially pages 8–15.
- Life-Event Engine Research Plan, especially pages 10–16.
- The visible Claude conversation, for the intended development and interaction model.

The numerical forgetting reference is the official [FSRS algorithm documentation](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm). The initial model below explicitly uses the FSRS v4 curve, not a claim that it is the latest or a validated model of autobiographical memory.

## 1. Information must reach an agent before changing its beliefs

### Confirmed issue

The reconsolidation report describes B gossiping to C and appending that conversation to dormant A's memory. No observation channel to A is required. This permits unobserved information to change A directly.

### Replacement

Separate four records:

1. **World event:** what occurred in the simulator, with time, participants, location, and communication channel. Accessible to the simulation controller, not automatically to agents.
2. **Observation:** the portion an agent received, with recipient, delivery time, source, and uncertainty.
3. **Appraisal:** the agent's interpretation of that observation in context.
4. **Memory or belief:** the subjective record formed or updated from that appraisal, linked to its provenance.

World events may alter external conditions without being observed: someone can lose access to a resource before learning why. However, a belief update must have an observation or an explicit internally generated cognitive event as its causal input.

Being the subject of a conversation does not make someone its recipient. Being in a room makes overhearing possible, not certain. Audibility, distance, language comprehension, attention, and the actual scenario determine reception. When a test explicitly says that a person is listening and understands, reception is an input fact rather than something randomly denied.

### The three-friends case

If two friends tease the third while the third listens, create observations for that listener. Appraisal may depend on relationship history, tone, audience, current state, and what the person believes was intended. Record the observed words separately from an inferred intention such as hostility. The resulting state change can affect attention, mood, trust, action choice, and subsequent memory encoding.

Do not automatically infer humiliation, a personality change, or a clinical condition. Affectionate teasing, ambiguous teasing, and hostile ridicule are different scenarios. The model must permit uncertainty and different reactions.

If the conversation occurs privately elsewhere, do not modify the target's beliefs. Later reporting creates a new observation at the time the target receives it. Changes in the friends' later behavior can also provide indirect evidence.

**Acceptance checks:** witnessed teasing can create an observation and reaction; an unheard private conversation cannot directly change the target's internal state; a later report is attributed to the reporter and received at the later time; retries do not duplicate an observation.

## 2. Use one consistent forgetting curve

### Confirmed issue

The graph report's example uses `R = 9^(-t/S)`. At `t = S`, this produces 1/9, approximately 11.1%, whereas FSRS defines stability as the interval at which recall probability is 90%.

### Replacement

For the initial baseline:

`R(t, S) = 1 / (1 + t / (9 * S))`

- `t` is elapsed simulated days since encoding or the last qualifying recall event.
- `S` is positive stability measured in simulated days.
- `R` is a recall-availability model, not confidence, truth, or emotional intensity.
- Reject negative elapsed time and nonpositive stability. Do not silently conceal ordering errors by clamping time.
- Name and version the curve and any parameter set in each experiment.

**Evaluated mathematical checks:** `R(0,S)=1`; `R(S,S)=0.9`; the original example instead gives approximately 0.111 at `t=S`.

**Required checks:** recall decreases as elapsed time increases at fixed stability; increasing stability does not decrease recall; reading the value repeatedly does not alter it.

The curve is a defined experimental baseline. Its success on flashcards does not establish its validity for autobiographical events or agent behavior.

## 3. Separate lookup, attention, recall, and rehearsal

### Confirmed issue

The graph report's reinforcement rule is `S_new = S * (1 + exp(2.5 * (1-R)))`. At zero elapsed time, `R=1`, so every update doubles stability. Ten immediate updates multiply stability by 1,024. The reconsolidation example separately multiplies stability by `1 + exp(0.5*P)`, which also doubles it at `P=0` if that branch executes.

### Replacement

- **Candidate lookup:** selects memories for possible use; read-only.
- **Attention:** identifies information actually processed by the agent.
- **Recall attempt:** records a modeled attempt and its outcome, distinct from supplying the answer to the language model.
- **Rehearsal or new encoding:** an explicit cognitive event eligible for an update under a registered rule.

Do not count database reads, retries, debugging, or report generation as successful recall. A single cognitive event has a stable identifier; its application is idempotent.

Remove both ad hoc exponential multipliers. In the reference baseline, keep stability fixed unless an explicit, versioned reinforcement model is enabled. A separate experimental variant may use a verified FSRS scheduler with supported ratings and calibrated parameters. Do not equate every LLM use of a supplied memory with a human correct-recall rating.

This temporary fixed-stability baseline is deliberate: it enables forgetting without claiming that reinforcement is solved. Real reinforcement remains part of the target architecture, with its own empirical evaluation.

**Acceptance checks:** duplicate delivery cannot increase stability; inspecting a memory cannot increase it; a zero-effect reconsolidation operation leaves stability unchanged; a qualifying rehearsal can change it only through the configured rule.

## 4. Give each clock one meaning

### Confirmed issues

The examples use `datetime()` despite arbitrary simulated time skips. The reconsolidation pseudocode uses epoch-style timestamps, assumes hours for affect fading, and uses the same elapsed value in a day-based forgetting formula. It also changes `last_retrieved` during no-exposure processing and after exposures that need not constitute recall.

### Replacement

Use one monotonic simulation clock. Store simulation timestamps in a documented unit and convert explicitly to days for the chosen forgetting model. Wall-clock timestamps belong only to operational logging.

Maintain distinct timestamps:

- creation or encoding time;
- last qualifying recall time;
- last exposure-processing time;
- last affect-update time;
- belief-version time.

Advancing affect or processing the exposure queue must not silently count as recall. Diagnostic queries are read-only. A recall event may reset the recall clock only after its modeled outcome is established.

**Acceptance checks:** a simulated ten-year jump produces the same result regardless of how many real seconds execution takes; representing an interval in hours or days after correct conversion gives the same result; repeated diagnostics do not preserve memories artificially.

## 5. Separate world validity from subjective accessibility

### Confirmed issue

The graph examples set `invalid_at` when memories are forgotten. The reconsolidation report separately reserves validity fields for world-state change. These are incompatible semantics. Filtering an agent's beliefs using an omniscient world-validity flag can also silently correct a false belief without an observation.

### Replacement

Keep separate concepts for:

- world fact validity;
- the interval during which an agent holds a belief;
- accessibility or recall probability;
- subjective confidence;
- emotional association;
- storage archival status.

A forgotten fact may remain true. A strongly remembered belief may be false. A building burning down changes world state, but an absent agent may still believe it stands until evidence reaches them. Preserve the historical statement that the building previously stood.

An immutable subjective episode preserves what the agent experienced or encoded, which may be mistaken; it is not interchangeable with the controller's immutable world-event record. Give the agent only its permitted observations and beliefs, not a provenance shortcut into omniscient records.

**Acceptance checks:** forgetting does not rewrite world history; world changes do not automatically update uninformed agents; analyst access to truth does not grant agent access.

## 6. Reconsolidation must not become automatic agreement

### Confirmed issues

The report treats embedding distance as prediction error, accumulates changes against an unchanged gist, and then rewrites from only the last three contexts. It clears the log even when the rewrite threshold was not reached. Its illustrated acceptance criteria prescribe a particular blended memory and an unsupported improvement target.

### Replacement

Use embeddings to retrieve relevant candidates, not as the sole test of contradiction or surprise. Similar wording can negate a claim. Different wording can express the same proposition.

For the reference implementation, process received exposures in chronological order. For each exposure, explicitly distinguish corroboration, contradiction, unrelated information, and uncertainty. Preserve the speaker, original source if known, reception time, and whether apparent corroboration repeats the same underlying claim.

An exposure can produce no change, a separate competing belief, an uncertainty update, or a versioned revision. Do not force every disagreement into a blended memory. After an accepted semantic revision, update both text and embedding before processing subsequent exposures.

A pending revision below threshold must remain represented if later accumulation is part of the chosen model. Do not discard it accidentally. If a completed exposure has intentionally produced no change, retain its audit outcome without repeatedly reconsidering it as a new event.

Start with sequential processing as the reference semantics. Batch optimization is allowed only after it matches those semantics on defined tests or is explicitly labeled an approximation. One LLM call is not constant computational cost when its input grows.

**Acceptance checks:** negation is not mistaken for agreement; unrelated news does not rewrite a memory; repeated rumors retain shared provenance; each revision is traceable; behavior does not silently change because the exposure queue was flushed more often.

## 7. Do not convert every published effect size into an event rate

### Confirmed issue

The life-event report places a standardized income coefficient into the exponent of a career-breakthrough hazard. Associations with income do not by themselves estimate the timing of breakthroughs. Odds ratios, hazard ratios, correlations, and standardized regression coefficients are not interchangeable.

### Replacement

Every event-rate parameter must declare its outcome definition, unit, eligible population, observation interval, source, and interpretation. Use a relevant survival estimate only with compatible covariate scaling and event definitions. Even a compatible observational hazard estimate does not automatically identify a causal intervention effect.

For missing parameters, retain a named assumption and run sensitivity analyses. In the evidence-focused baseline, omit unsupported trait multipliers rather than presenting invented conversions as empirical findings. Experimental variants can include them with their uncertainty clearly labeled.

Keep the proposed base-rate table labeled as a design assumption until independently calibrated. Do not simultaneously fit and validate against the same cohort statistics. Stochastic variation alone does not resolve confounding or justify individual causal predictions.

**Acceptance checks:** every rate has a time unit; ineligible events have zero rate; calibration data and evaluation data are separated; an unsupported association cannot be imported as a supposedly verified hazard coefficient.

## 8. Keep lazy simulation, remove the instantaneous-exactness promise

### Confirmed issue

The reports imply that deferred processing or thinning makes decades of dependent development effectively instantaneous while preserving all causal dependencies. The actual cost includes proposed and rejected events, queue processing, and downstream dependencies. Interacting agents cannot generally be advanced independently without reconciling shared events.

### Replacement

Use analytical updates for explicitly defined passive dynamics between events. Process consequential events in simulation-time order across the affected agents. Do not generate a full private life history first when it depends on relationships or interactions whose outcomes have not been resolved.

For thinning, maintain a valid rate bound over the proposal interval; recompute after relevant state changes and split intervals at known discontinuities. A sampled hazard exceeding the proposed bound is an error to resolve, not a ratio to silently clamp. Random environmental shocks need an explicit process and sampling schedule; do not redraw them unpredictably on every rate query.

Generate shared events once and update each participant consistently. Stop future live-agent events after death. Enforce eligibility for marriage, divorce, employment transitions, and other event types.

State the actual scaling in terms of proposals, accepted events, dependencies, and exposure records. A long empty interval can be cheap. A dense interacting history may not be.

**Acceptance checks:** partners share the same relationship event; downstream changes occur after their causes; no post-death actions; replay with a fixed event stream is deterministic; alternate time-step or batching strategies preserve the specified distribution or report their approximation error.

## 9. Keep state changes separate from trait development

One social observation may alter current appraisal, mood, or trust without rewriting a stable trait. Encode these as distinct updates with explicit dependencies. Avoid counting the same experience repeatedly as independent evidence simply because it appears in an episode, a summary, and a self-narrative.

The same teasing event can legitimately influence several states. The requirement is to define the separate pathways and their joint calibration rather than stack several independently borrowed effect sizes as though they were independent causes.

Distinguish personality-level Stability from memory stability; they are different quantities with different units. A proposed relationship between them needs a named, calibrated mapping. Do not present an inferred mapping as a published numerical law.

Do not add diagnostic labels as deterministic outputs of a single experience or a handful of sliders. Any claim about reproducing a clinical condition requires separate evidence and evaluation. This revision specifies no new clinical coefficients.

## 10. Replace circular success criteria

The reports include targets such as a particular misinformation trajectory or forty-percent improvements. Treat those as proposed engineering goals, not results established by the cited literature.

Maintain three separate test layers:

1. **Internal correctness:** invariants, units, temporal ordering, information access, idempotency, and replay.
2. **Behavioral validity:** predictions against independent human observations, including uncertainty and individual variation.
3. **Practical value:** improvement against a strong simpler agent under comparable model, evidence, and resource budgets.

Before examining test outcomes, declare metrics and a practically meaningful improvement threshold. Report repeated-run variation and failures. Compare the core with individual mechanisms removed to measure their contribution. Preserve a straightforward persona-plus-memory baseline.

For replicating particular people, use consenting participants and withheld responses. A famous-person demonstration can be useful, but the model's prior exposure to public biographies prevents it from serving as decisive validation on its own.

## 11. Remove the privacy shortcut

The memory-decay report suggests that adding Laplacian noise to retrieval scores provides differential privacy. Noise alone does not establish that guarantee. Noisy recall also does not enforce access permissions.

This specification makes no differential-privacy claim. Access rules control who may retrieve private observations; psychological forgetting is separate. Any future formal privacy mechanism requires an explicit neighboring-dataset definition, sensitivity, privacy parameters, and accounting across releases. This is a correction to a specific claim in the source report, not an added requirement to implement differential privacy now.

## 12. Implementation order and unresolved evidence

Implement the corrected event/observation boundary, clocks, and memory invariants first. Then add explicitly configured rehearsal, belief revision, and state-dependent life-event processes one at a time. Keep the reference baseline available throughout.

Outstanding empirical work includes initialization of memory strength, rehearsal effects, appraisal variation, trait-change rates, relationship updates, event-rate estimates, and any clinical mechanisms. The absence of calibrated values is visible model uncertainty, not something to hide behind more precise-looking constants.

### Decisions adopted in this revision

- Overhearing is supported; subject-of-conversation status alone is insufficient.
- Subjective experience is separated from objective history.
- A consistent FSRS-v4-shaped decay curve is the provisional baseline.
- Automatic lookup-based reinforcement and both runaway multipliers are removed.
- Passive updates do not reset recall timestamps.
- Unsupported effect-size-to-hazard conversions are removed from the evidence-focused baseline.
- Sequential exposure processing defines the reference behavior; batching must justify equivalence or approximation.
- Decades-long skips remain an optimization goal, without a constant-cost or universal exactness claim.
- Psychological and predictive performance remain to be measured; none is inferred from passing software invariants.
