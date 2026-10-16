# Developmental continuation: mechanisms, assumptions and checks

## Household continuation, 16 October 2026

[Household implementation](HOUSEHOLD_IMPLEMENTATION.md) documents the new room routing, multi-turn interaction, availability/calendar timing, private observations and optional existing cognition/development hooks. `simulate.py --household` enables it in a fresh combined policy. Latest verification is 185 named checks plus twelve core checks, a four-turn actual 27B fixture and a seven-year scripted combined run. Read the guide for source-version boundaries, commands, explicit assumptions and remaining proposals; older figures below retain their historical scope.

## Latest: local Graphiti and MiroFish-inspired tools

[GRAPHITI_IMPLEMENTATION.md](GRAPHITI_IMPLEMENTATION.md) and [setup guide](graphiti-local/README.md) supersede older “no Graphiti/embedding model” statements below. The engine now has a local Graphiti/Neo4j/BGE retrieval index, durable background outbox, explicit fallback diagnostics and read-only quick/deep/history/chain tools. No Zep Cloud subscription or hosted inference dependency was added.

Twelve suites pass **161 checks plus twelve core checks**. The final actual 27B fixture completed five calls/one action with graph-based recall, no fallback, preserved privacy and matching JSON/SQLite restoration. Durable offline-queue/restart behavior was checked separately. The index is derived from private views, not a new source of world truth; immutable-cache scale and unrestricted extraction/history limitations remain explicit. The graph service/container remain running; language test clients have finished.


## Latest fresh test and infant correction

See [LATEST_TEST_REPORT.md](LATEST_TEST_REPORT.md) and [fresh-integration-verification.json](fresh-integration-verification.json). The current verification is **139 named regression checks plus twelve core checks**. Fresh actual 27B caregiver/infant runs and a resumed adult memory interaction completed; a second 100-year scripted scenario completed 165 resolved actions with six deaths and no pending activities. This seed did not produce a birth; earlier new-generation evidence remains separate.

Testing exposed infant CAPS rules with adult-like cognitive challenges despite nonverbal action constraints. `situation.py` now provides bounded infant sensory triggers/nonverbal reactions, `engine.py` supplies capability context and refreshes generated rules at ages two/five. A wrong-root JSON response failed safely; explicit schema/repair feedback fixed the replay. Final regression and corrected infant evidence are recorded with source hashes. These checks establish runnable behavior, not human validity or full scientific coverage. Earlier counts/traces below are historical.


**Newer handoff:** [FULL_BUILD_STATE.md](FULL_BUILD_STATE.md) and [REVIEW_LATER.md](REVIEW_LATER.md) supersede older missing-software lists below. These notes retain their original equations, assumptions and historical evidence.

16 October 2026. This is the continuation of the audited engine, not a new claim of a complete human replica. [Build state](BUILD_STATE.md) and [the coverage audit](source-to-code-audit.md) remain the entry points.

## Newer integrated extension

[Integrated build notes](integrated-build-notes.md) now supersede the older missing-category lists below. Cognition, constrained histories/probing, planning/budgets/habits and explicit world/generation policies are connected, with dedicated checks and separate short actual-model evidence. The developmental equations and historical traces below retain their original scope. Richness, scale and empirical grounding remain open.

## What now runs

| Mechanism | Runtime connection | Explicit limit |
|---|---|---|
| Caregiver-derived expectations | Direct received observations carry the known caregiver identity. The local model estimates responsiveness and acceptance from perceived content; delivery retains this evidence. Learned working models reach subsequent action/appraisal context in language. | Continuous anxiety/avoidance proxies, not ECR-R scores, diagnoses or calibrated attachment types. |
| Early attachment anchor and later variation | Early interaction days update a caregiver-specific anchor; adult interactions produce a working expectation that recovers toward that anchor. | Neutral four-unit prior, age-18 split, 180-day adult recovery and language thresholds are scenario choices. Same-day records share one unit of influence. No claim that adulthood erases or freezes attachment in real people. |
| State-conditioned crystallization | A resolved action with an outcome received by its actor records the temporary state supplied to the action request. Repeated deviations on separate days can make small enduring changes. | The supplied state is a model inference, not measured enacted behavior. Three independent days in a 180-day window, rate .005, daily bound .05 and annual bound .5 are provisional. This is a TESSERA-inspired proxy, not the full psychological framework. |
| Age-related trajectories | Explicit piecewise-linear domain curves are evaluated from absolute simulated age, separately from initial dispositions and learned changes. | The example's small N/A/C trends are unfitted scenario offsets. Equal within-domain shifts are not a TGA mapping or child norms. Death freezes further maturation. |
| Inherited initial dispositions | `materialize_child` uses zero to two known biological parents and separate caregivers, latent genetic/segregation/non-shared components and the existing correlated adult reference model. | Optional existing numpy/scipy runtime. Unrelated-founder/additive assumptions, a common variance share and adult-to-child extrapolation; no validated genetic prediction. Unknown biological parents do not create fictional identities. |
| Needed-person activation | Selecting an interaction can materialize a committed lightweight identity with stable profile sampling and a consistent birth day. | Unknown age uses a labeled scenario assumption. Activation adds no invented historical memories. Full automatic biography/history expansion and surprise-driven probing remain unfinished. |
| Independent interaction response | An offered contact can make a separate model-based decision from its own personality, mood, received history and the transmitted request. Canonical response consequences change the shared event, resolving both intentions. | Contact-response menus and success multipliers are explicit scenario policies. The model does not see the requesting agent's private profile, thoughts or plans. |
| Signature refresh | Earlier generated signatures are archived when scenario age stages or sustained baseline drift trigger regeneration. | Boundaries at 12/18/40/65 and a five-point/one-year drift trigger are provisional. Externally supplied rules are preserved. This is not fitted developmental stage theory or a learned covariance model. |
| Action-dependent event rates | The event scheduler can use resolved-action counts, goal progress or facets in a declared log-rate policy under a constant upper envelope. | Bounded thinning implements the configured clipped intensity, not fitted real-world hazards. No conversion of income correlations/effect sizes into rates. |
| Bounded model view | Optional older context is trimmed deterministically while original records remain intact. The transport renders the actual llama.cpp chat template and counts prompt tokens using that server's tokenizer before inference. | The selected local server must support its template/tokenizer endpoints. Oversized mandatory inputs fail before inference. Semantic embedding retrieval and interference remain unfinished. |
| Structured response repair | Invalid fields, invented action/goal IDs, unavailable memory citations, unsupported signatures or gist evidence fail validation. At most two corrective responses can be requested before the event is rolled back. | No invalid result changes agent state. This does not establish that a syntactically valid interpretation is psychologically or semantically correct. |

Crystallization replaces the old success-only scenario trait deltas when enabled. A successful task does not automatically make a person more confident, and a failed task does not automatically mean an unresponsive caregiver. The actual appraisal input omits controller-suggested affect/attachment scores, so they cannot simply be echoed as supposedly independent estimates.

## Mathematical corrections

The lifespan report's example uses `0.5*G + 0.5*E`, with independent `Var(G)=1` and `SD(E)=0.5`. Its genetic variance share is `0.25/(0.25+0.0625)=0.8`, not 0.5. The new latent model uses `sqrt(h2)*G + sqrt(1-h2)*E` with equally normalized covariance. For two unrelated known parents, the offspring latent genetic vector is `(G1+G2)/2 + sqrt(1/2)*segregation_noise`. With one known parent it is `G1/2 + sqrt(3/4)*residual_noise`, integrating the unknown parent rather than inventing one. These identities specify the simulated model; they do not estimate a real child's heritability.

Founder latent states are conditioned on the original materialization dispositions where available, then retained. Later acquired trait changes must not alter a lazily generated genetic component. Legacy snapshots without an original disposition anchor have a documented fallback and cannot retroactively establish a genuine genetic history.

The report's maturity example adds a fixed amount per function call despite accepting elapsed years. The engine instead evaluates an age curve at the current and origin ages. Splitting the same interval into checkpoints produces the same result. Temporary state recovery similarly uses elapsed days rather than a number of ticks.

All new mathematical policies retain the established information boundary: world identity, private received experience, inferred expectation and shared outcome remain separate records.

Materialization must match an already committed birth day; event updates cannot silently rewrite existing birth/biological-parent/caregiver commitments. Contacts known to be unborn are excluded from the current action menu. Explicit caregiver APIs still handle adding historical family constraints, rather than an unrelated event overwriting them.

## Evidence saved

- [Development checks](development-engineering-checks.json): information isolation, failure versus support, same-day bounds, early anchor/later recovery, independent resolved experiences, annual bounds, maturation/resume equivalence and no post-death maturation.
- [Inheritance checks](temperament-engineering-checks.json): stable expansion order, distinct siblings, parent/caregiver separation, variance identities and no inheritance of later acquired trait changes.
- [World growth checks](world-growth-engineering-checks.json): selected-interaction activation, full-event rollback, no fabricated history, bounded action-dependent rates and resumed thinning equivalence.
- [Context checks](context-engineering-checks.json): deterministic view bounds, retained current personality/action menu, explicit omissions and rendered-token overflow rejection before inference.
- [Actual childhood interaction run](development-live-example/run/summary.json): three actions, six appraisals, two consolidations, three situation interpretations and one signature-generation request. All three tasks remained unsolved; received support still updated caregiver expectations. There was no forced crystallization when no rule matched. One action was deliberately offered to exercise the caregiving path; the first five years were not developed.
- [Actual repeated-trigger run](crystallization-live-example/run/summary.json): three additional actions, three appraisals and three interpretations. Two actions were offered; the scenario deliberately matched a generated signature. One bounded lasting update followed the third independent day. This is not an independent evaluation of prediction.
- [Final transport check](crystallization-live-example/final-transport-smoke.json): actual proposal using bounded context and the rendered-token guard, without committing an action.
- [Final appraisal check](development-live-example/final-caregiving-smoke.json): actual perceived-text appraisal with controller score hints removed, without committing an observation.

The actual developmental traces precede the final removal of controller score hints and the context guard; the two final smoke checks exercise those later changes explicitly. The repeated-trigger trace retains broader received evidence in its update record; the current implementation narrows new update evidence to the influential nonzero exposures. Historical traces are preserved.

The [actual independent interaction](interaction-live-example/run/integrity-checks.json) completed with eight calls and two resolved actions. The child request was forced to exercise the path; the caregiver had two responses and chose to help. The separate caregiver-role/age-refresh probe could not complete because SSH disappeared. Adult signature refresh was subsequently live-verified in the main continuation. Its 13 requests exercised the final token guard, but no overflow reduction was required; that branch and the formal-role context remain locally checked.

Original encoding stability now has its own immutable metadata field. Both checkpoint loading and event rollback reconstruct the encoding value, not later rehearsed accessibility. Legacy snapshots use the explicit observation stability or unchanged historical encoding policy as a documented fallback. Regression checks cover both reconstruction paths.

## Running and continuing

From this engine directory, use the existing environment for inherited profiles:

```sh
../../work/profile-env/bin/python initialize_life.py --inherited --save NEW_DIRECTORY/initial.json
../../work/profile-env/bin/python run_live.py --world NEW_DIRECTORY/initial.json \
  --policy development-demo.json --until-day 8035.5 --out NEW_DIRECTORY/run \
  --api http://127.0.0.1:18081
```

Choose a new output directory for a new experiment. Resume using the saved world and its archived `policy-used.json`; the controller rejects silent policy/provider changes. The loopback URL requires the user's established cluster forwarding connection. A live connection must be checked, not assumed from this document.

Engineering checks are `check_context.py`, `check_fidelity.py`, `check_situation.py`, `check_lifetime.py`, `check_development.py`, `check_temperament.py` and `check_world_growth.py`; the last two require the existing profile environment. The core demonstration is `demo.py --out NEW_DIRECTORY`. These checks establish implementation properties, not scientific accuracy.

`check_interaction.py` additionally checks independent contact decisions, private-history isolation, shared resolution, causal response consequences and rollback. [Final verification](final-engineering-verification.json) records all eight check scripts and the core demo against the final source hashes.

The first longer-run attempt is preserved in `development-lifetime-live/first-attempt`: the model returned a misspelled required field, and the whole first event was rolled back. The resumed run used bounded output repair and repaired three invalid outputs. It stopped at age 19.007 with 27 resolved actions when the SSH connection disappeared. The subsequent [continuation](development-lifetime-live/continued-run/summary.json) completed at age 22 with four additional actions, 31 resolved actions total, 90 recalls, one archived signature version and a completed preparation goal. All prior actions and the archived policy were preserved; the final state restored successfully. This continuation took 187.948 seconds and 13 model requests without output repairs. [Resume instructions](RESUME.md) identify the latest checkpoint and remaining scope. The connection disappeared again after the final save.

## Source references and remaining work

See [preserved reports](sources/README.md): *Lifespan Development* sections 3, 4 and 6 for attachment, state/trait change and social/narrative layers; its implementation example on pp.12–13 for the weighting and tick-size problems; *Situational Personality Variability* pp.10–11 for temporary states and signatures; *Life-Event Engine Research Plan* for event rates and selection versus causation. Source claims are proposals unless separately verified.

Still unfinished: full constrained biographies and automatic social probing, semantic retrieval/interference and richer detail loss, automatic conditional reconsolidation without the rejected formulas, autonomous rumination, full narrative-identity updates, competing goals/time allocation/habits, and general demographic/economic/social consequences. The unresolved instrument mapping and empirical calibration are not repaired by inventing coefficients. Wider society and mental-health extensions remain separate from this runnable developmental milestone.
