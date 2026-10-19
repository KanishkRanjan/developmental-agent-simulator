# Hormone module: evidence for every constant

Generated from `devsim/policies/hormones.json` on 18 October 2026; the config is the source of truth, so update both together.

- **`[V]`** verified: the source was located and the number or direction confirmed by reading it (DOI given).
- **`[D]`** design default: a modelling choice, not claimed to be empirical.
- **`[U]`** unverified or contested. It is configurable, and behaviour resting on a contested claim sits behind a flag.

The design report this module came from had unreliable evidence labels, so every biology number starts at `[U]` and moves up only after reading its source.

| Name | Value | Tag | Source | Notes |
|---|---|---|---|---|
| `b_floor` | 0.05 | [D] | none | stress baseline floor (x units) while asleep and late in the day |
| `b_mood_shift` | 0.2 | [D] | none | extra floor per unit of a lowered mood-baseline-shift dial (static, not allostatic drift) |
| `A_day` | 0.1 | [D] | none | post-wake diurnal component amplitude |
| `tau_day_h` | 7 | [D] | none | post-wake diurnal decline |
| `A_car` | 0.3 | [U] | none verified | awakening-response amplitude; the reported 50-75% rise was not verified |
| `tau_car_h` | 0.67 | [V] | Stalder et al. 2016, Psychoneuroendocrinology 63:414-432, doi:10.1016/j.psyneuen.2015.10.010 (abstract: "marked increase ... over the first 30-45 min after morning awakening") | awakening-response peak ~40 min after waking; Stalder et al. 2016 (doi:10.1016/j.psyneuen.2015.10.010) describe a marked rise over the first 30-45 min; 40 min is a [D] choice within that window |
| `tau_s_h` | 1.75 | [U] | none verified | phasic stress decay; loosely after a 60-90 min plasma cortisol half-life, itself unverified as a psychological timescale |
| `g_s` | 1.0 | [D] | none | stress gain per unit threat appraisal |
| `theta_ts` | 1.0 | [D] | none | threat-sensitivity dial gain on stress increments |
| `theta_n` | 1.0 | [D] | none | neuroticism gain on stress increments |
| `g_novelty` | 0.5 | [D] | none | novelty gain: increment x (1 + g_novelty x surprise) |
| `habituation_power` | 2 | [D] | none | repeat increments scale by 1/(1 + exposures)^power, so they fade within 1-2 exposures |
| `k_controllability` | 0.5 | [D] | none | threat x (1 + k (0.5 - controllability)); neutral 0.5 when no provider |
| `dys_gain` | 0.5 | [D] | none | dysregulation dial raises stress gain by (1 + dys_gain x dys) |
| `dys_tau` | 1.0 | [D] | none | dysregulation dial slows recovery: tau_s x (1 + dys_tau x dys) |
| `rt_bias` | 0.3 | [D] | none | low reality testing reads threat into arousing events: + rt_bias (1 - reality_testing)(1 - threat) arousal |
| `reactivity_sigma` | 0.2 | [D] | none | seeded per-agent log-normal spread of stress gain |
| `sleep_dep_reactivity` | false | [U] | none | flag: sleep pressure raises stress gain |
| `lambda_p` | 0.5 | [U] | none | used only with sleep_dep_reactivity: gain x (1 + lambda_p x P) |
| `tau_rise_h` | 18.2 | [U] | Daan, Beersma and Borbely 1984, Am J Physiol 246:R161-R183 (not read; value seen only as a software default) | Process S rise; two-process model (Daan, Beersma and Borbely 1984, Am J Physiol 246:R161) - number seen only as a software default, original not read |
| `tau_decay_h` | 4.2 | [U] | as tau_rise_h | Process S decay; as tau_rise_h |
| `P_start` | 0.3 | [D] | none | sleep pressure when the module first sees an agent |
| `c_amp` | 0.3 | [D] | none | circadian (Process C) amplitude in sleep_drive |
| `circadian_peak_hour` | 3.0 | [D] | none | clock hour of peak circadian sleep propensity before the chronotype offset |
| `chronotype_sd_h` | 1.0 | [D] | none | seeded per-agent circadian phase offset; not tied to Big Five |
| `wired_override` | true | [U] | none | hypothesis flag: high stress at night lengthens sleep onset and lowers sleep efficiency |
| `L0_min` | 15 | [D] | none | mean sleep-onset latency (minutes) without stress |
| `L_k_min` | 90 | [U] | none | extra latency scale (minutes) for stress above S_wired |
| `S_wired` | 0.25 | [U] | none | stress readout above which onset slows |
| `wired_power` | 1.5 | [U] | none | shape of the latency rise |
| `latency_spread` | 0.5 | [D] | none | seeded latency = mean x (1 - spread + 2 spread u) |
| `k_eff` | 0.4 | [U] | none | sleep efficiency = 1 - k_eff x S at onset (pressure drains slower after a stressed bedtime) |
| `alpha` | 0.2 | [D] | none | Rescorla-Wagner learning rate |
| `v0` | 0.0 | [D] | none | prior expectation for a new target |
| `n_open` | 0.3 | [D] | none | openness raises the prior: V0 = v0 + n_open x openness |
| `N0` | 0.3 | [D] | none | novelty bonus N0 exp(-exposures / tau_n) |
| `tau_n` | 2.0 | [D] | none | novelty bonus fades over exposures |
| `kappa_c` | 0.5 | [D] | none | closeness term in wanting (absorbs the bonding role; no oxytocin variable) |
| `eta` | 0.1 | [D] | none | tonic dopamine gain per unit prediction error |
| `d0` | 0.0 | [D] | none | tonic resting level |
| `d_mood_shift` | 0.3 | [D] | none | mood-baseline-shift dial moves the resting level: D0 = d0 + d_mood_shift x shift |
| `tau_d_h` | 48 | [D] | none | tonic decay toward D0 (hours to days) |
| `gist_weight` | 0.5 | [D] | none | learning weight of a GIST-attended outcome (FULL 1, NONE 0) |
| `rho_k` | 0.3 | [D] | none | reward sensitivity rho = 1 + rho_k tanh(D - D0) |
| `initiative_k` | 0.5 | [D] | none | initiative multiplier on starting interactions: 1 + initiative_k tanh(D - D0) |
| `menu_wanting_weight` | 0.3 | [D] | none | how much wanting W(person) adds to a talk option in the living-world menu |
| `T0` | 0.2 | [D] | none | softmax temperature for target choice |
| `stress_exploration_link` | false | [U] | none | flag: stress raises choice temperature |
| `lambda_T` | 1.0 | [U] | none | used only with stress_exploration_link: T = T0 (1 + lambda_T S) |
| `leave_margin` | 0.2 | [D] | none | leaving is considered once the best alternative beats the current group by this margin |
| `leave_h0` | 0.5 | [D] | none | leaving probability per decision event per unit shortfall beyond the margin (capped at 1) |
| `arousal_s` | 0.8 | [D] | none | arousal readout weight of stress |
| `arousal_load` | 0.2 | [D] | none | arousal readout weight of recent event load (open attention streams) |
| `load_ref` | 3 | [D] | none | streams at which load counts as full |
| `arousal_form` | "off" | [U] | none | how arousal scales attention capacity; tunnel vision and the inverted U are not established, so off by default |
| `k_mono` | 0.3 | [U] | none | monotone form: capacity x (1 - k_mono arousal) |
| `kappa_u` | 2.0 | [U] | none | inverted-U form: capacity x (1 - kappa_u (arousal - 0.5)^2) |
| `lambda_s` | 0.5 | [D] | none | negative mood impulses scale by (1 + lambda_s S at the event) |
| `beta_d` | 0.2 | [D] | none | mood baseline offset per unit (D - D0) |
| `beta_s` | 0.2 | [D] | none | mood baseline offset per unit (S - S0) |
| `S0` | 0.1 | [D] | none | stress readout counted as neutral for the mood offset |
| `style_S_mild` | 0.35 | [D] | none | stress readout for the mild style line |
| `style_S_strong` | 0.6 | [D] | none | stress readout for the strong style line |
| `style_P` | 0.75 | [D] | none | sleep pressure for the tired style line |
| `first_person_low_mood` | false | [U] | none | flag: low mood adds slight first-person emphasis |
| `low_mood` | -0.4 | [D] | none | mood valence counted as low for that flag |
| `length_bias` | "neutral" | [U] | none | stress does not shorten speech by default (no verified source for either direction) |

## Sources checked (18 October 2026)

| Claim | Result | Used for |
|---|---|---|
| Cortisol awakening response peaks 30–45 min after waking | **Confirmed** in the abstract of Stalder et al. 2016, doi:10.1016/j.psyneuen.2015.10.010. The "50–75% rise" is not stated there. | `tau_car_h` `[V]` (40 min is a `[D]` choice within the window); `A_car` stays `[U]` |
| Process S time constants 18.2 h (rise) and 4.2 h (decay) | **Not confirmed.** The values appear as defaults of a two-process-model software package that cites Daan, Beersma and Borbély 1984 without attributing the numbers. Borbély's 2022 retrospective (doi:10.1111/jsr.13598) states the functional forms but no values. | `tau_rise_h`, `tau_decay_h` `[U]` |
| Greater stress reactivity goes with lower linguistic complexity | **Confirmed** in the full text of Saslow et al. 2014, *Psychophysiology* 51:257–266, doi:10.1111/psyp.12171, PMID 24354732. Study 2: "greater cortisol reactivity associated with lower complexity". Complexity is a share of words, so it says nothing about length. | the "simpler phrasing" part of the stress style lines |
| Acute stress increases speech pauses | **Secondary source only:** a British Psychological Society digest of Buchanan, Laures-Gore and Duff 2014, *Biological Psychology* 97:60–66 (doi:10.1016/j.biopsycho.2014.02.005 as listed there). The primary abstract was not read. The digest reports no difference in speaking rate. | the "pauses and fillers" part of the style lines, `[U]` |
| Stressed speakers produce more total words | **Not found** in either source | `length_bias` stays `neutral` (`[U]`); stress never shortens speech by default |
| Plasma cortisol half-life of 60–90 min as a psychological timescale | Not checked | `tau_s_h` `[U]` |

## Deliberately not implemented (spec section 1)

- **Cortisol suppressing melatonin or diluting adenosine.** No such coupling exists between stress and sleep pressure. The only link is the flagged `wired_override` (onset latency and efficiency), which is labelled a hypothesis.
- **Early-life stress permanently recalibrating the stress system.** There is no developmental or allostatic drift of the baseline; a persistent offset comes only from the existing dials (`b_mood_shift`, `dys_tau`, `dys_gain`).
- **Blunted basal cortisol in PTSD or burnout.** Not modelled.
- **Candidate-gene effects.** None. Per-agent spread comes only from seeded log-normal reactivity and chronotype offsets.
- **Blood glucose and executive function.** Not modelled.
- **"Dopamine = pleasure" and "oxytocin = love hormone".** Tonic dopamine is a leaky integral of prediction error that scales initiative and reward sensitivity. Bonding is society-layer closeness in the wanting score.
- **Tunnel vision and an inverted U of arousal.** `arousal_form` is off by default; the monotone and inverted-U forms are `[U]` options.

## Deviation from the spec, recorded as `[D]`

The spec sets r = valence × attention-tier weight. With r = 0, a Rescorla-Wagner step still moves V toward 0, which contradicts its own test that "a zoned-out interaction produces about no learning". This module therefore applies the tier weight to the learning step instead: V += α w (r − V), and D += η w δ. An unattended outcome (w = 0) then changes nothing.
