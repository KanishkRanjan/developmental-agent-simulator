# Parameters: skill acquisition, forgetting and expression

Generated from `devsim/policies/skills.json` (the source of truth) on 18 October 2026. Ledger IDs refer to [research/skill_acquisition_ledger.md](research/skill_acquisition_ledger.md).

- **[V]**: implemented from supported evidence.
- **[D]**: direction or ordering only; the magnitude is a free default.
- **[C]**: the mechanism comes from a single primary study.
- **[U]**: a placeholder with no usable evidence.

No [D] or [U] number is scientific. `devsim.skills.sensitivity_sweep` reruns a scenario across them; `checks/results/skills-sensitivity.json` has an example.

| Name | Default | Tag | Ledger | Rationale |
|---|---|---|---|---|
| `transfer_similarity_cutoff` | 0.5 | [U] | E24 | below this label similarity transfer is exactly 0 (far transfer null, E24 [V]); the cutoff itself is a placeholder |
| `transfer_gain` | 0.3 | [U] | E24 | near-transfer rate boost = 1 + gain x similarity x level of the related skill |
| `aptitude_mode` | "latent" | [D] | E14 | one seeded latent z per agent; the only new agent-level variable (design flag for the owner) |
| `rho_skill` | 0.38 | [V] | E14 | cognitive ability with skill acquisition (Colquitt et al. 2000, rho .38); used only to scale the aptitude effect |
| `log_rate_sigma` | 0.5 | [U] | E14 | between-person spread of log learning rate; beta_apt = rho_skill x log_rate_sigma (mapping [U], direction [D]) |
| `openness_link` | 0.0 | [U] | E14 | no verified openness effect on learning rate; off |
| `alpha_shape` | 2.0 | [U] | E2 | gamma shape of the per (agent, skill) base rate; the gamma FORM is [V] (E2: averaging gamma-rate exponentials gives a power law) |
| `alpha_mean` | 0.15 | [U] | E1 | mean base acquisition rate per full-quality practice |
| `ceiling0` | 0.7 | [U] | E4 | first-segment asymptote; strategy shifts raise it (later pieces surpass earlier ones, E4 [C]) |
| `s0_shape` | 3.0 | [U] | E2 | gamma shape of initial stability |
| `s0_mean_days` | 3.0 | [U] | E12 | mean initial stability before decay-class scaling |
| `s_max_days` | 730 | [U] | E12 | stability ceiling before decay-class scaling |
| `k_s` | 1.2 | [U] | E8 | stability gain per practice; gain grows with the gap since the last one (spacing direction E8 [D]) |
| `p_gap` | 1.0 | [U] | E8 | exponent on (1 - R) in the stability gain |
| `mode_mult_retrieval` | 1.0 | [D] | E9 | acquisition multiplier for retrieval practice |
| `mode_mult_restudy` | 0.9 | [D] | E9 | acquisition multiplier for restudy (testing effect: retrieval at least as good) |
| `mode_s_retrieval` | 1.5 | [D] | E9 | stability gain multiplier for retrieval (g about 0.5 direction, magnitude free) |
| `mode_s_restudy` | 1.0 | [D] | E9 | stability gain multiplier for restudy |
| `feedback_task` | 1.2 | [D] | E21 | task-focused feedback helps |
| `feedback_self` | 0.95 | [D] | E21 | self-focused feedback does not help and may hurt slightly |
| `savings_gain` | 0.8 | [D] | E13 | relearning after a long gap is faster with more prior practice (magnitude [U]) |
| `savings_n` | 10 | [U] | E13 | practices at which savings are about two thirds saturated |
| `decay_cognitive` | 0.44 | [U] | E12 | stability scale exp(-c x attribute); ordering cognitive faster than physical [D]; ln 1.55 used only as a plausibility range |
| `decay_open_loop` | 0.3 | [U] | E12 | open-loop decays faster than closed-loop [D] |
| `decay_accuracy` | 1.1 | [U] | E12 | accuracy-graded decays faster than speed-graded [D]; ln 3 used only as a plausibility range |
| `strategy_shift` | true | [C] | E4 | abrupt strategy shifts with a temporary dip (mechanism E4 [C]; parameters [U]) |
| `h_shift` | 0.03 | [U] | E4 | shift hazard per full-quality practice, shrinking as level approaches the ceiling |
| `dip` | 0.15 | [U] | E4 | temporary drop in level at a shift |
| `shift_boost` | 1.3 | [U] | E4 | rate multiplier for the new segment |
| `shift_ceiling_gain` | 0.5 | [U] | E4 | share of the remaining headroom the new segment adds to the ceiling |
| `w_sleep` | 0.15 | [U] | E19 | performance loss from sleep pressure above sleep_ref (direction E19/E20 [D]; magnitude unknown) |
| `sleep_ref` | 0.6 | [U] | E19 | sleep pressure below which performance is unaffected |
| `w_stress` | 0.1 | [U] | E19 | performance loss from stress above stress_ref; no inverted U, no choking term (NOT FOUND) |
| `stress_ref` | 0.4 | [U] | E19 | stress readout below which performance is unaffected |
| `tier_novice` | 0.05 | [U] | none | performance at or above this is a beginner (below: none) |
| `tier_competent` | 0.3 | [U] | none | competent from here |
| `tier_proficient` | 0.6 | [U] | none | proficient from here |
| `tier_expert` | 0.85 | [U] | none | expert from here |
| `competence_noise` | 0.03 | [U] | none | seeded noise on a competence check |
| `r_self` | 0.29 | [D] | E22 | target correlation of perceived with true skill in the reference population; noise is calibrated to it; no built-in overconfidence (E23 contested) |
| `familiar_noise_cut` | 0.5 | [U] | E22 | share of self-assessment noise removed for a well-practised skill (direction E22 [D]) |
| `clarity_noise_cut` | 0.5 | [U] | E22 | share removed with objective, immediate feedback (direction E22 [D]) |
| `conscientiousness_motivation` | 0.3 | [D] | E14 | conscientiousness raises wanting to practise (motivation .38), never the learning rate |
| `anxiety_motivation` | 0.3 | [D] | E14 | anxiety lowers wanting to practise (motivation -.57); neuroticism and threat sensitivity as anxiety is a [U] mapping |
| `anxiety_attention` | 0.15 | [U] | E14 | mild attention reduction during practice (outcomes -.15 direction) |
| `practice_menu_weight` | 0.3 | [U] | none | how much practice wanting adds to a living-world activity option |
| `eps_level` | 0.01 | [U] | E13 | prune to a savings record below this level |
| `eps_recency_days` | 365 | [U] | E13 | and when unpractised this long |
| `max_skills_per_agent` | 200 | [U] | none | safety valve: least important skills become savings records |
| `event_log_cap` | 50 | [U] | none | practice events kept per skill for audit and replay |

Derived at configure time:
- `sigma_self` (self-assessment noise) is calibrated so that, in a reference population of new skills with uniform true levels and neutral feedback clarity, perceived and true skill correlate at `r_self` [D, E22].
- `beta_apt` = `rho_skill` × `log_rate_sigma`: the rho value is [V, E14], and the mapping onto a log-rate effect is [U].

Fixed by the spec, not tunable:
- **Gamma family** for the per (person, skill) rate and initial stability [V, E2].
- **Zero transfer below the similarity cutoff** [V, E24].
- **No inverted U, no choking term, no overconfidence bias, no far transfer.** These appear in the ledger's section 7 and section 8 lists of claims not to implement and gaps.
