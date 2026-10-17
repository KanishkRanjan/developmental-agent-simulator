# Attention allocation: evidence tags

The attention module (`devsim/attention.py`, parameters in `devsim/policies/attention.json`) decides how much of each delivered event a listener attends to. This file records what each part rests on.

**Rule:** every parameter in `attention.json` carries an `evidence` tag, and any parameter added later must carry one too. Never upgrade a `[D]` or `[U]` into a "fact" in code comments or docs.

| Tag | Meaning |
|---|---|
| `[V]` | Verified source: the idea (not any number here) is taken from the cited work. |
| `[D]` | Design default: a tunable guess, to be calibrated, not cited. |
| `[U]` | Plausible but unverified: the shape itself is uncertain, so it is config-selectable. |

## Sources and claims

- **[V] Kahneman (1973), *Attention and Effort*.** Capacity theory: attention is a limited, shared resource. Allocation depends on momentary intentions (what matters right now) and enduring dispositions (things that always grab you, such as your own name). In the code: capacity `K`, sharing across streams, top-down drive `T` (goal match = momentary intention) and trait topic affinity (enduring disposition).
- **[V] Corbetta and Shulman (2002), as summarized in a 2020 *Frontiers in Integrative Neuroscience* review.** There is a top-down, goal-driven system and a bottom-up system triggered by salient or unexpected stimuli, and novelty can interrupt top-down control. In the code: `T` versus bottom-up capture `B`, combined by a soft OR so that `B` can override boredom.
- **[V] Cherry (1953), the cocktail-party effect.** People can follow one conversation and still notice their own name in another. In the code: an event that addresses or names the listener is never NONE.
- **[D] Closeness to the speaker raises attention.** Plausible, but no specific study was verified. Treat it as a design hypothesis (`w_rel`, `w_ment`, `gamma_rel`).
- **[U] The inverted U of capacity against arousal (Yerkes-Dodson style).** Plausible, but the shape is unverified. It is selectable: `arousal_shape` is `inverted_u` or `monotone`, and `kappa` sets the curvature.
- **[D] Every numeric default.** This covers every weight, threshold, loading, keyword rule, noise scale, rate and duration in `attention.json`.

## Interpretations made in this codebase (all [D])

- An event's stream is its conversation (`@conversation:<key>`) or call (`@call:<n>`). Any other event is a stream of its own.
- Stream load counts the agent's *other* open streams.
- Threat salience comes from event metadata when it is authored. Otherwise it is `max(0, -valence) x arousal` from the listener's own appraisal, so it is computed after the fact, not before attention.
- An agent's own actions and thoughts (`source: self`, `kind: internal`) are always FULL.
- Hearing your own name (a resolved mention of the listener) counts as being addressed.
- A relationship recorded at closeness 0 reads as "known, unrated" (`closeness_known`), because encounters create relationships at 0.
