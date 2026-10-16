# Integrated agent engine: audited prototype

## Household continuation, 16 October 2026

[Household implementation](HOUSEHOLD_IMPLEMENTATION.md) documents the new room routing, multi-turn interaction, availability/calendar timing, private observations and optional existing cognition/development hooks. `simulate.py --household` enables it in a fresh combined policy. Latest verification is 185 named checks plus twelve core checks, a four-turn actual 27B fixture and a seven-year scripted combined run. Read the guide for source-version boundaries, commands, explicit assumptions and remaining proposals; older figures below retain their historical scope.

**Read the [source-to-code audit](source-to-code-audit.md) first.** It records confirmed implementation departures, repairs, and the full remaining coverage map. The earlier successful live run did not implement the full research architecture.

**Current entry point:** [Review later](history/REVIEW_LATER.md), [full build state](history/FULL_BUILD_STATE.md), and `simulate.py`. The accepted engine layers now include indexed recall, open histories, reference resolution, elapsed activities, state variability/culture, autonomous goal opportunities, world/newborn hazards and JSON/SQLite persistence. Ten suites pass (136 checks), plus the core demo; separate 27B adult/infant runs and an 85-year scripted lifecycle are saved. Scientific calibration and predictive validity remain unresolved.

This is the first connected implementation of the design. It runs locally, saves its state and can request appraisal, actions and plans from the existing 27B model's local API. An automatic controller now generates age-eligible opportunities, resolves chosen actions and applies bounded developmental updates under an explicit scenario policy. It does not yet model the full range of human development or a society.

The project decision is **build the connected system, then evaluate and improve it**. Comparative benchmarks are paused. Engineering checks remain part of implementation so clock errors, leaked knowledge and lost state do not accumulate.

The latest [developmental continuation](development-notes.md) now connects caregiver-derived expectations, repeated state-conditioned lasting changes, elapsed-age maturation, optional inherited dispositions, interaction-driven lazy activation and bounded state-dependent opportunities. The current default scenario enables maturation/crystallization. These are explicit provisional policies; full biography generation and other gaps remain in the coverage audit.

The local transport now checks the served llama.cpp template/tokenizer and context window before inference. Optional context is bounded without deleting original records. Structured outputs are validated and can be repaired twice before an event is rolled back; malformed fields are never silently accepted. Appraisal inputs omit controller score hints. The selected server must provide the template/tokenizer endpoints.

The current default policy additionally enables provisional situational personality before each local-model action: generate reusable if-then signatures once, interpret the situation using private context, select signatures whose full conditions match, and express bounded temporary state changes in behavioral language. State recovery is based on elapsed simulated days; it does not change when context is inspected or checkpoints are inserted. Enduring facets are separate. Scripted demonstrations skip the model-based preparation. See `situation.py`, `check_situation.py`, and the [preserved source guide](../research/sources/README.md). Domain modifiers and the configured one-day recovery half-life are assumptions, not measured rates.

The actual 27B trace in `situation-live-example/run` contains one complete opportunity with signatures, construal, action, two appraisals and consolidation. No full signature trigger matched that particular situation, which correctly left the temporary offsets zero. This is a wiring check, not evidence of improved human prediction.

## Automatic childhood-to-adult run

From the repository root:

```sh
python3 -m devsim.initialize_life --save work/lifetime/initial.json
python3 -m devsim.lifetime work/lifetime/initial.json \
  --policy devsim/policies/development-demo.json --until-day 8035.5 \
  --save work/lifetime/live-age22.json --api http://127.0.0.1:8081
```

The default uses the local model for action choices, plans and each recipient's subjective appraisal. The controller supplies eligible opportunities, allowed actions and world consequences. No activation steering or fine-tuning is involved.

For a zero-inference engineering demonstration, add `--scripted` and use a different output filename. The included `runs/scripted/lifetime-example/age22.json` is such a demonstration: **89 automatic ticks and 27 resolved actions from birth to age 22**, with childhood support, adolescent projects and an adult goal. All choices are explicitly scripted. Sparse scenario events are generated automatically; unmodeled developmental experiences are omitted.

Each event saves a checkpoint when `--save` is supplied. Restart by passing that checkpoint as the input world, keeping its archived policy and provider. A failed model request rolls the current opportunity back and preserves completed opportunities. Resuming in several intervals produces the same scripted event history as one run. Old archived examples retain their legacy scheduler.

`devsim/policies/development-demo.json` exposes all event rates, age bounds, action-success probabilities, progress gains and trait effects. They are **illustrative assumptions**, not literature-calibrated values. Its new default samples continuous event times for constant-rate age-window opportunities; empty intervals do not require ticking. General state-dependent hazard models remain unfinished. Trait changes have an absolute per-facet budget per simulated age-year. `step_days` applies only to archived legacy-discrete policies.

## Run the connected example

From the repository root:

```sh
python3 -m devsim.demo --out work/demo-example
```

The standard-library example writes `world.json`, `trace.json` and `engineering-checks.json` (the preserved copy is `runs/core/example/`). The trace contains Alex's context before hearing gossip, after directly hearing teasing, and after an explicit rehearsal outcome. The action is clearly marked as scripted; no model response is fabricated.

The existing population sampler is connected as an option:

```sh
work/profile-env/bin/python -m devsim.demo --sampled --out work/example-sampled
```

The sampler was fitted on adult self-report data. Applying its distribution to an initial childhood disposition is an explicit assumption in this demonstration; there is no claim of a validated inherited temperament model. Manual profiles require all 30 facet percentiles.

## Use the existing local model

When the cluster API is reachable (on the cluster itself, or through an established port forward):

```sh
python3 -m devsim.engine work/example-sampled/world.json \
  --agent alex \
  --situation 'You want to prepare for your presentation after an awkward lunch. What do you do next?' \
  --api http://127.0.0.1:8081 \
  --commit-action next-practice \
  --save work/example-sampled/continued-world.json
```

This calls the local chat-completions API, validates the returned JSON and records an **intention** and plan. The model does not award itself progress or manufacture a successful outcome. The world controller schedules the consequence with `requires={'action': 'next-practice'}`. `--context-only` inspects the exact agent context without an inference call or state change.

`Engine.appraise()` is the corresponding model-based observation-interpretation path. The controller first specifies what an agent actually perceived and its source. The LLM proposes meaning, valence, arousal, importance and confidence using that agent's state. These estimates can then be encoded in a shared scheduled event. Appraisal cannot introduce new recipients or commit world facts.

The user restored SSH, and an actual 27B run has now completed: 30 action responses and 36 appraisals across 89 ticks. See [the live run report](history/live-run-report.md). The earlier `example` and `example-sampled` artifacts remain explicitly scripted; the actual model run is in `live-example`. Its exact policy is archived as `live-example/policy-used.json`.

After the fidelity audit, a separate [corrected integration run](../runs/live/audited-live-example/run/summary.json) completed with natural-language personality, correlated adult profiles, event-time scheduling, actual-use recall and source-linked gist consolidation. It has one offered action and is deliberately a wiring check. Its captured requests are in `audited-live-example/run/requests.jsonl`; the older run remains unchanged as historical evidence.

## What is connected

| Component | Current implementation |
|---|---|
| Personality | Internal 30-facet profile compiled to selected facet-specific behavioral language for model requests; existing correlated sampler is available. |
| Situations | Explicit cue labels and matching if-then behavioral tendencies. Automatic DIAMONDS classification remains open. |
| Observations | One shared event; explicit recipients; original subjective episode and source preserved. Being discussed does not grant knowledge. |
| Memory | Source, provenance, confidence, importance, meaning and version history; accessibility/cue gating, mood-sensitive ranking and personality-conditioned gist beliefs. |
| Reinforcement | Actual-use and explicit received-reminder recall, duplicate rejection, minimum interval and capped stability. Inspection never reinforces. |
| Mood | Separate valence and arousal; individual power-law recovery/reactivity options; recalled affect has habituation and a repetition gate. |
| Reinterpretation | Original episode preserved; revisions cite evidence received by that agent and retain previous meanings. |
| Relationships | Role, trust, closeness and firsthand encounter distinguished. Testimony does not create a meeting. |
| Family | Caregiver constraints, cycle rejection and later materialization of a caregiver while preserving committed identity. No forced two-parent household or recursive ancestry expansion. |
| Lazy spawning | World identity can remain a lightweight record; full agent generation is explicit and deterministic by entity seed. A mentioned name does not automatically become a real person. |
| Goals and life planning | Priorities, deadlines, progress, statuses and model-produced action plans are persistent. Outcomes come from controller events. |
| Life events | Chronological scheduling plus automatic age-eligible opportunities, constrained choices, scenario outcomes, prerequisites, shared events and death handling. |
| Development | Automatic scenario-configured, evidence-linked facet changes, bounded per age-year, with old and new values recorded; mood does not rewrite traits. |
| Attachment and culture | Separate persisted context consumed by the expression/appraisal model; no calibrated developmental equations yet. |
| Persistence | Atomic JSON checkpoint replacement; restart reconstructs observation history and current state. |

## Deliberate provisional rules

All times use simulated days. Configuration is saved in each checkpoint. Default numerical values are engineering assumptions, including one-day mood timescale, power-law exponent 0.5, affect budgets, importance-based memory strength and rehearsal gains. None is presented as a fitted psychological law.

The power-law option retains event impulses and sums their contributions. On each new impulse it caps the absolute effective valence mass and arousal mass by proportionally scaling contributions. This changes the source report's dynamics intentionally: it bounds hidden accumulation as well as displayed mood. It does not drop individually small impulses. A quiet interval is evaluated analytically from known inputs; events in that interval must still be supplied or generated.

The FSRS-v4-shaped curve supplies an **accessibility proxy**, not a calibrated human recall probability. Old low-access episodes need a sufficiently specific lexical cue; originals are preserved. A configured event batch can trigger tentative semantic gist generation, with evidence IDs checked and originals archived. Neither the accessibility threshold nor the lexical cue rule is a fitted human model; checking source IDs does not validate an LLM's semantic inference. Semantic retrieval and strict total-token budgeting remain open.

The demo provides only a few childhood and adult events. Its empty years represent omitted history. It must not be described as simulating every intervening year.

## Remaining build work

1. Broader life-event and world consequence policies beyond the included childhood, school and adult-project scenario. The automatic controller works; empirically grounded event opportunities/rates remain open.
2. A complete developmental policy linking repeated experiences, caregiving, attachment and slow trait changes. Bounded automatic trait updates work under explicit scenario assumptions; realistic causal laws remain open.
3. Better semantic retrieval, justified detail-loss policies, source-aware conflicting-belief resolution and autonomous rumination. Basic source-linked gist consolidation is now connected.
4. Social introduction/probing decisions, grounded background expansion and a multi-agent conversation controller. Current identities, encounters and observations provide the information boundaries.
5. Optional TGA/HEXACO mappings and broader trust, health, economics, habits and opinions modules. These are not silently claimed as completed mechanisms.

Fine-tuning and activation steering remain excluded per the user's decision. A UI and large-population optimization are later build work. The complete source-design inventory remains in [the design coverage ledger](design/design-coverage-ledger.md); implementation decisions and current status are in [BUILD_STATE.md](BUILD_STATE.md).
