# Hormone module: design

Added 18 October 2026. Code: `devsim/hormones.py`. Config: `devsim/policies/hormones.json`. Evidence: [hormone_evidence.md](hormone_evidence.md). Checks: `checks/check_hormones.py`. Population harness: `python3 -m devsim.hormone_calibration`. Turn it on with policy key `hormones: {}`, where any constant can be overridden. Worlds without the key are unchanged.

## Three variables, no more

| Variable | What it is | Advance (closed form, from its anchor) |
|---|---|---|
| `stress_x` | phasic stress | x · exp(−Δ/τ_s); τ_s is longer with dysregulation |
| `sleep_pressure` | Process S | awake: 1 − (1 − P)·exp(−Δ/τ_rise); asleep: P·exp(−efficiency·Δ/τ_decay) |
| `dopamine_tonic` | leaky integral of prediction error | D0 + (D − D0)·exp(−Δ/τ_d) |

`HormoneState` is a frozen dataclass with exactly these three fields, each a `(value, anchor)` pair. A check fails on any other field count. The stress readout is S = 1 − exp(−(baseline + phasic)).
- **Baseline:** not stored. It is a function of time since the last wake: floor, plus a diurnal decline, plus an awakening rise that peaks τ_car after waking. While asleep it is the floor.
- **Sleep and wake times:** they come from the sleep module's night (the longest gap in the routine's waking windows). The onset is delayed by a seeded latency that grows with stress at bedtime under the `wired_override` flag.

Everything is lazy. A read advances a copy, and an event (`on_event`, called once per delivered observation from `Engine.advance`) advances, adds its increment and stores. Nothing ticks, and no step iterates over the agents. A check counts accesses to the agents table during an event, a read and a wanting call, and requires zero.

## Why there is no fourth variable

The spec forbids oxytocin, serotonin, sex steroids, allostatic load, orexin and the rest as per-agent state. What they would have done comes from inputs that already exist:
- **Bonding (the usual oxytocin story):** the wanting score W(target) = V(target) + κ_c · closeness + novelty. Closeness is the existing provider: society-layer tie strength, then recorded closeness, then family from identity facts. A close friend therefore stays wanted when there is no prediction error left to learn from. Prediction error drives learning and novelty-seeking; closeness keeps stable bonds.
- **Chronic or clinical shifts:** the four existing dials. The mood-baseline shift raises the stress floor and moves the dopamine resting level. Dysregulation raises stress gain and slows recovery. Threat sensitivity raises gain. Low reality testing reads threat into arousing events. These are static: no allostatic drift in v1.
- **Individual differences:** Big Five (neuroticism raises stress gain; openness raises the prior for new targets), plus two seeded per-agent parameters (log-normal stress reactivity and a chronotype offset). There is no type, role or sex branch. A check fails if those identifiers appear in the module, and another shows that renaming people, adding identity facts or relabelling ties changes nothing.

Per-target expectations V(target) are memory, not hormone state. They live in a lazily created `agent['expectations']` dict keyed by target: a person, `group:<id>` for group talks, or `activity:<object>:<verb>` for finished living-world activities. They are updated by Rescorla-Wagner with the attention tier weighting the step.

## Where it plugs in (existing interfaces only)

| Consumer | What it gets |
|---|---|
| Attention | fatigue = P (the existing `fatigue` provider); a `capacity_factor` provider from arousal, which is off by default |
| Mood | negative impulses scaled by (1 + λ_s S at the event); a baseline offset β_d (D − D0) − β_s (S − S0) on reading. Mood stays the only mood state. |
| Sleep module | `sleep_efficiency` multiplies the night's quality Q, so a stressed bedtime consolidates less. `sleep_onset_latency` and `sleep_drive` are exposed. When people sleep is still set by the routine; the sleep module does not yet move bedtime by drive. |
| Prompt | `how_you_come_across_right_now`: a text line in the existing context of every model call. No extra calls. |
| Living-world menu | talk and message options get + w · W(person) and × initiative (1 + k tanh(D − D0)) |
| Decisions | `wanting_scores`, a seeded softmax `choose` (stress-to-temperature link off), and `leave_chance` for a group at a decision event. No group-switching event exists for simulated characters yet, so these have no caller beyond the menu. |

## Evidence-grounded speech style

- **Higher stress:** simpler, more fragmented phrasing with pauses and fillers. Simpler phrasing is backed by Saslow et al. 2014 `[V]`; pauses only by a secondary report of Buchanan et al. 2014 `[U]`.
- **Length:** never shortened. The directive says "say as much as you normally would"; `length_bias` is `[U]`, default neutral.
- **High sleep pressure:** flatter feeling, slower to respond `[U]`.
- **First-person emphasis at low mood:** behind a flag, off.

## Population check

On 300 seeded people with spread facets and dials:
- the awakening peak is at 39 min;
- a standard stressor gives S ≈ 0.69 (0.54–0.87), falling to ≈ 0.32 three hours later;
- sleep pressure is ≈ 0.63 at bedtime and ≈ 0.11 on waking;
- a late stressor raises onset latency from about 15 to about 35 minutes and lowers efficiency from 0.97 to 0.75;
- the declared inputs explain 0.98 of the spread in stress reactivity and all of it in wanting, and a nuisance identity fact explains none.

All of this calibrates design defaults. It is not empirical validation.

## Limits

- Nearly every constant is `[D]` or `[U]`, and the Process S time constants are unverified.
- Reads clamp to the latest anchor, so a read of a past time returns the present state.
- The style line reaches every model call, appraisals included; only speech is meant to show it.
- Not live-verified with the 27B model.
