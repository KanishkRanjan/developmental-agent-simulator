# Skill module: report (18 October 2026)

Code: `devsim/skills.py`. Config: `devsim/policies/skills.json`. Parameters: [PARAMETERS.md](PARAMETERS.md). Evidence: [research/skill_acquisition_ledger.md](research/skill_acquisition_ledger.md). Checks: `checks/check_skills.py` (16), with a sensitivity report in `checks/results/skills-sensitivity.json`. Turn it on with policy key `skills: {}`.

## Where it plugs in
- **Situation options** may carry `skill: {key, difficulty, attrs, mode, feedback}`. When such an option is chosen:
  - `competence_check` decides success, replacing the option's fixed `success_probability`;
  - the attempt is a practice event;
  - the outcome observation carries `outcome_target: skill:<key>`, so the hormone module's Rescorla-Wagner step learns how practising it feels.

  The scenario writer's vocabulary includes the field. In the option menu the model sees `how_good_you_think_you_are_at_this` (the person's noisy self-assessment).
- **Living-world activities** in the catalog may declare `skill` attributes. Cooking, homework, revising, working on the robot and paperwork do; finishing one is practice. In the free-time menu, practice wanting (learned value, plus conscientiousness, minus anxiety) adds to those options.
- **Every prompt** carries `your_skills`: the person's top skills as tier texts, plus the not-knowing rule for anything else. This adds no model call.

## Every [U] parameter (37)
`transfer_similarity_cutoff`, `transfer_gain`, `log_rate_sigma`, `openness_link`, `alpha_shape`, `alpha_mean`, `ceiling0`, `s0_shape`, `s0_mean_days`, `s_max_days`, `k_s`, `p_gap`, `savings_n`, `decay_cognitive`, `decay_open_loop`, `decay_accuracy`, `h_shift`, `dip`, `shift_boost`, `shift_ceiling_gain`, `w_sleep`, `sleep_ref`, `w_stress`, `stress_ref`, `tier_novice`, `tier_competent`, `tier_proficient`, `tier_expert`, `competence_noise`, `familiar_noise_cut`, `clarity_noise_cut`, `anxiety_attention`, `practice_menu_weight`, `eps_level`, `eps_recency_days`, `max_skills_per_agent`, `event_log_cap`

The magnitudes behind the [D] directions are free defaults as well; see PARAMETERS.md.

## Interface mismatches with the spec (adapted, not guessed)
1. **Mood is not a bounded-tanh update.** `Engine.mood` uses a power-law kernel by default (or average, or exponential). The module adds no mood variable: success and failure reach mood through the appraised outcome observation.
2. **Wanting is additive.** The hormone module's wanting is W = V + κ·closeness + novelty, not V × closeness-weighting. Practice targets have no closeness, so W = V + novelty; the adapter adds conscientiousness and anxiety terms.
3. **No society-layer feedback events with a `feedback_focus` exist.** `practice(feedback=…)` and the option field `skill.feedback` are the hook.
4. **Attention for practice.** The attention module scores received events, and one's own practice is always FULL there. So `a` for practice is the attention module's capacity for that person at that moment (arousal, fatigue = sleep pressure, dysregulation and the hormone capacity factor), lowered a little by anxiety. That mapping is [U].
5. **Labels.** No lemmatiser exists in the repository, so labels get deterministic suffix stripping ("dancing" and "dance" become `danc`). The only embedding backend sits behind the Graphiti service and is not used; similarity is token Jaccard.
6. **Starting ceiling.** Spec step 5 starts the ceiling at 1, which makes `shift_ceiling_gain` meaningless. The first segment's ceiling is `ceiling0` = 0.7 [U], so later segments can surpass earlier ones (E4).
7. **Savings.** Savings kept only in stability cannot make relearning faster in practice count, but the spec's savings test requires that. A savings multiplier on the rate grows with prior practice and the gap since the last one: 1 + gain × (1 − e^(−n/n_sat)) × (1 − R). Direction [D, E13], magnitude [U]. Pruned skills keep their stability and practice count as a savings record.
8. **Config format.** The config is the repository's JSON policy format (as for hormones and attention), not a Python dataclass. Values are validated on load.

## Not implemented, and why
- **Withholding task content from the model's context:** no task-content routing exists to withhold from. The gate decides outcomes and the directive shapes speech.
- **A separate episodic memory write for notable checks:** the outcome observation already is that memory.
- **Every item on the spec's do-not-implement list:** none was needed.

## Design flag: the aptitude latent
`agent['skill_aptitude']` is one seeded N(0, 1) per person, the module's only new agent-level variable. It exists because cognitive ability is the strongest verified predictor (E14, rho .38 with skill acquisition). Its effect on the log rate is `rho_skill` × `log_rate_sigma`, where the mapping is [U]. Set `aptitude_mode: "off"` to remove it.

## Open questions
- Should social learning (watching, being taught) do more than `expose()`? Today it creates the skill at level 0 with no bonus, because no evidence was found.
- Should the builder's per-person fill ask the model to tag skills on situation options? Today scenarios must name them.
- Tier thresholds, decay coefficients and rates are placeholders. A real run, plus the sensitivity sweep, should show which ones matter.
