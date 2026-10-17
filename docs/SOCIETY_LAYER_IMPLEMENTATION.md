# Society layer

Package: [`devsim/population/`](../devsim/population/). Config: [`devsim/policies/society-layer.json`](../devsim/policies/society-layer.json) (92 parameters: 5 V, 8 U, 79 D). Checks: [`checks/check_population.py`](../checks/check_population.py) (11 named checks, about 2 minutes). Design: "MiroFish Society Layer: Corrected and Improved Design (v2)" (claude.ai doc, 17 October 2026), built in its build order, with its validation checks run at steps 4, 6 and 8.

Tags follow the design: **V** = verified anchor with its source in the note; **D** = design default, unverified; **U** = unverified figure from memory. Only V values may be cited as evidence. The five V values are NFHS-5 Maharashtra infant and under-five mortality, median age at first marriage and adolescent fertility, and the Holt-Lunstad 2015 isolation odds ratio.

## Using it

- In a scenario policy: `"society_layer": {"overrides": {...}, "bind": ["priya", "arun"]}`. With no `bind`, every character is bound. Archived worlds and policies without the key are unchanged.
- Each bound character keeps its own Big Five (facet domain means), birth day and dials, and gets a place in the implicit population. Characters linked as caregiver and child share one population household; the engine's family is the family.
- Their circle reaches them as received observations ("Vikas got in touch with me.", "I heard that Asha died.", "Madhuri and I had a serious falling-out"). Appraisal, the hippocampal buffer, mood and grief then handle these like any experience. Repeated "got in touch" news is routine, so it reuses its appraisal.
- Their context gains `social_world`: a fixed persona (speech style, directness, stubbornness), the closest people with relation and closeness, any non-cooperation floor, and opinions on configured `topics`.
- A spoken turn between bound characters moves their opinions by the bounded-confidence rule. The model never sets an opinion.

## What was built, by build step

| Step | Module | What it does |
|---|---|---|
| 1 Seeds and fact log | `core.py` | Hash-keyed draws (no shared random state); append-only log of timestamped facts; `commit` (shown means immutable), `rollback` (uncommitted facts plus joint partners' slices), `horizon` (earliest uncommitted joint fact). |
| 2 Implicit graph | `core.py` | People are a pure function of (seed, id): place cell, household, age, sex, Big Five, dials, heavy-tailed degree propensity θ. Edge rule `p_ij = min(1, κ θ_i θ_j e^(−|x_i−x_j|/h))` decided by a pair hash; household kin and spouses always tied. Candidates are the cell and its 8 neighbors, seeded long-range permutation partners (both directions, so discovery is symmetric), and people born nearby. |
| 3 Ties | `ties.py` | `s(Δt) = floor + (s_last − floor)(1 + Δt/9S)^−1`, the memory forgetting curve. Kin have a higher floor and longer S; Conscientiousness lengthens S. A friendly contact restores the tie to its peak, resets Δt and multiplies S; a hostile one lowers the peak and valence and may rupture the tie; reconciliation scales with prior closeness. Contacts come from per-year hashed candidate buckets thinned to the current hazard, so a pair's history is the same however it is queried. |
| 4 Demography | `demography.py` | Competing risks piecewise constant per one-year age band: death (infant and child hazards from NFHS-5, Gompertz-Makeham adult hazard [U], isolation multiplier), women's marriage, marital fertility with parity factors and a birth interval, and a job-state chain. One exponential draw per event, keyed by (person, event number). |
| 5 Joint events | `demography.py` | A marriage draws the husband from nearby people by compatibility and age gap. He must be alive and free then and later (rejection), and the fact lands in both logs. `observe(pid, t, 'seen_alive' / 'seen_single')` commits a sighting, rolls back latent contradictions with their partners, and conditions later draws. |
| 6 Opinions and rumors | `diffusion.py` | Composition-rejection event selection (power-of-two bins, rejection inside a bin). Deffuant updates within ε, weighted by source credibility discounted less for low reality testing. A mean-field histogram per topic for people not yet realized. Behaviors and rumors spread by exposure counts from distinct ties within a window; threat items spread faster with threat sensitivity. |
| 7 Institutions and norms | `institutions.py` | No member lists: a person's school or workplace is a hash pick in their region, and members are enumerated by scanning that region. Roles go to the best fit (traits plus seniority). Norms are mean, sd and tightness per community; sanction sensitivity is one formula over dials and traits; collective action is a threshold cascade fired by tension. |
| 8 Economy and opportunity | `demography.py`, `institutions.py` | Job states (unemployed, informal, formal) as competing risks with trait effects; job loss logs a poverty-stress dial shift; income is lognormal per state. Heavy-tailed opportunities arrive faster with more reachable institutions; success multiplies capital and failure shrinks it. |
| 9 Isolation feedback | `demography.py` | Integration index = tier-weighted base tie strengths minus known losses; death hazard × exp(isolation × ln 1.29 × 1.5 under 65). A death logs `tie_lost` and a buffered grief shift on close survivors; time spent isolated slowly raises threat sensitivity. |
| 10 Model-boundary guards | `guards.py`, `bridge.py` | Opinions in state; `clamp` (a proposed change never exceeds the rule's, same direction); `post_check`; fixed personas; conflict floors; variance monitor and collapse flag. One voice per call was already the engine's design. |

## Validation (non-circular: calibration inputs are never counted)

| Check | Result | Basis |
|---|---|---|
| Contact vs closeness | Spearman −0.62 between closeness and days since last contact; median gap 1.1 days for kin, 17.7 for friends | Roberts & Dunbar 2011 (V, direction) |
| Total fertility | Period TFR 2.11 on the check's sample (1.9–2.25 across seeds); input was only adolescent fertility 47/1,000 | NFHS-5 Maharashtra 1.7 (V). **Runs high**: the parity factors are unverified, and tuning them to 1.7 would make the check circular |
| Marriage timing | Median first marriage 19.7 (the only marriage input, 19.6); 25% of women 20–24 married before 18 | NFHS-5 21.9% (V) |
| Heavy tails | Degree mean 111, median 70, max 467; top 1% hold 25% of capital after 30 years; fit helps (Spearman 0.41) but top outcomes are not all the best fits; identical personalities in different networks end apart | Lindenfors 2021, Pluchino 2018 (mechanism) |
| Opinion structure | ε = 1: one group (sd 0.03); ε = 0.15: two or more groups (sd 0.42) | Model property on this graph |
| Lazy vs eager | The mean-field compartment agrees with realized people (1 vs 6 peaks); a life resolved in one call or in chunks is identical; resolving 600 women in reverse order gives the same married share (0.953) and mean parity (1.33) | Design test |
| Isolation (plumbing only) | The death hazard ratio between the most and least isolated equals the imposed exp(Δ × ln 1.29 × 1.5) | The odds ratio is an input, so this tests wiring, not science |

Also checked: config tags, refused overrides, determinism, edge symmetry, query cost the same for 40,000 and 4,000,000 people, no bigamy, committed facts protected, institution membership consistency, role fit, collective trigger, no archetype words, guard behavior, and the engine bridge in a scripted two-character year (93 news items for Priya, all from real entities, shown people committed, stable context, event-driven checks).

## Departures from the design, and why

- **Contact rate by pair strength, not tier rank.** Tier rank depends on both people's whole networks (slow and query-order dependent). Rates follow the pair's starting strength, and tiers stay a ranking view.
- **Contacts do not inflate strength.** A first version raised strength on every contact and saturated frequent ties at 1. The design only resets the decay clock and lengthens stability, so a contact restores the tie to its peak.
- **Isolation uses base tie strengths.** Resolving every neighbor's life to compute a death hazard recurses across the population. The index uses base strengths minus known deaths and ruptures (marked `shortcut:` in code).
- **Reachable institutions use age eligibility only** (same reason; `shortcut:`).
- **Pre-start histories.** Base people are conditioned to be alive at the start. Births before the start count toward parity but do not create people; base children stand for them.
- **News about fights only from close ties**, and repeat contact news at most once in 21 days (both D), to keep a live run's model calls bounded.
- **OASIS** is not used; this is built into devsim. The design's note to check OASIS's own scaling does not apply.

## Limits

- Not verified with the 27B model in a live run.
- Population size defaults to 360,000 (`grid` 60 × `cell_size` 100). Queries cost the same at any size, but the log and tie records grow with what is touched.
- Order independence is statistical, not exact (as the design says). Queries are forward in time.
- Mean field is well-mixed, not on the graph. Unrealized people never adopt behaviors.
- Partners' engine identities are lightweight (name, birth day). Talking to one in person needs the existing lazy activation.
- Missing anchors (design open questions): tie decay constants, divorce, job-change and age-specific mortality for India, effect sizes from loneliness to each dial, tightness values, ε and μ.

## Changes outside the package

| File | Change |
|---|---|
| `devsim/engine.py` | `context` adds `social_world` for bound characters (from the last check, so repeated builds agree). |
| `devsim/household.py` | After a spoken turn, bound characters' opinions update by the rule. |
| `devsim/lifetime.py` | Validates and applies a `society_layer` policy, binds characters, and adds the event-driven `society` queue item. |
