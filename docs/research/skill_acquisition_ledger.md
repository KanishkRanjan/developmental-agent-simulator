# Skill Acquisition Research Ledger (MiroFish)

Purpose: permanent record of what our two research rounds established, how strongly, and what is still unknown. The coding agent copies this file to `docs/research/skill_acquisition_ledger.md` and every numeric parameter in the code must cite a ledger ID (E#) or be marked [U] (unsupported default).

## How to read the tags

Research-run evidence tags (assigned by the research agent, objective criteria):
- A = two or more independent meta-analyses or large preregistered replications agree
- B = a single meta-analysis, or several consistent primary studies, or a formal proof plus multi-dataset survey
- C = a single primary study
- D = theory, expert consensus, or review without direct test
- X = contested by better evidence

Our own status column:
- CHECKED = we personally confirmed the paper's actual conclusion against the abstract or text in this project
- UNCHECKED = reported by a research run, not independently re-verified by us. Treat as provisional. Evidence tags and citation attributions in commissioned reports have been wrong three times in this project (hormone report twice, round-1 skill report once), so UNCHECKED numbers must be spot-checked before anything depends on their magnitude.

Code-side tags (used in source comments and PARAMETERS.md):
- [V] directly implemented from a CHECKED or well-supported ledger entry
- [D] direction/ordering only implemented; magnitude is a free default
- [U] no usable evidence; default value is a placeholder, must be exposed in config and covered by sensitivity analysis

---

## 1. Curve shape (acquisition and forgetting)

HEADLINE: the shape of individual learning curves is CONTESTED. Round 1 claimed "individuals universally follow exponential, power law is purely an averaging artifact". That was wrong in framing: its 25,280-curve dataset is Donner and Hardy (2015), whose finding was the opposite direction (piecewise power law beats single power law).

| ID | Finding | Numbers | Tag | Status | DOI / ID |
|---|---|---|---|---|---|
| E1 | Heathcote, Brown and Mewhort 2000: exponential fits unaveraged practice data better than power function; averaging biases toward power | exponential won in 40 of 40 data sets; 79.0% of 7,910 series (475 subjects, 24 experiments); APEX variant won 84.1% of series | B | UNCHECKED (abstract-level) | 10.3758/BF03212979 |
| E2 | Murre and Chessa 2011: averaging exponentials with gamma, uniform or half-normal rate distributions yields a power function (mathematical proof plus simulation) | proof | B | UNCHECKED (abstract plus PMC text) | 10.3758/s13423-011-0076-y ; PMID 21468774 |
| E3 | Haider and Frensch 2002: abrupt strategy changes occur in individual curves; aggregation of discontinuous curves can look like a power law | empirical plus simulation | C | UNCHECKED (abstract) | 10.1037//0278-7393.28.2.392 ; PMID 11911396 |
| E4 | Donner and Hardy 2015: piecewise power law explains individual curves better than a single power law, complexity-controlled | 25,280 individual curves, 500 trials each, four cognitive tasks; later pieces usually surpass earlier ones, often after a temporary dip; transition rate negatively associated with age | C | CHECKED (abstract read directly) | 10.3758/s13423-015-0811-x ; PMC4577530 |
| E5 | Zhang, McDougle and Leonard 2025 (Cognition): people correctly predict exponential SHAPE of skill learning curves but mispredict parameters (too optimistic). NOT a power-vs-exponential test. | six preregistered experiments, n = 500; actual curves fit exponential better than LINEAR only | C | UNCHECKED | 10.1016/j.cognition.2025.106083 |
| E6 | Wixted and Carpenter 2007: Wickelgren power law m = lambda(1 + beta t)^(-psi) fits Ebbinghaus savings data | one dataset, 2-page commentary | C | UNCHECKED | 10.1111/j.1467-9280.2007.01862.x |
| E7 | Rubin and Wenzel 1996: century of retention data compared across function families (linear, hyperbolic, exponential, logarithmic, power) | only abstract and contents seen; the "210 datasets x 105 functions" figure came from a blog and is unverified | D | UNCHECKED | 10.1037/0033-295X.103.4.734 |
| E7b | Individual-level forgetting may follow genuine power curves (Wixted and Ebbesen 1997, cited secondhand by Radvansky et al. 2022) | primary not opened | X for any single-law claim | UNCHECKED | not captured |
| E7c | Lumosity (36,297 users, 51 tasks): trajectories covary across tasks; "a general ability factor expressed mostly at later stages of practice plus task-specific factors" | abstract only | C | UNCHECKED | 10.1038/s41562-020-00935-3 |

Modelling consequence (what the code does): exponential approach within a learner-item segment [D, contested]; population-level power-law behaviour must EMERGE from gamma-distributed per-learner/per-skill rates [V from E2, math]; optional discrete strategy-shift change-points [C]. Never hardcode one aggregate power law. Never claim "individuals are universally exponential".

## 2. Practice scheduling, retention, decay

| ID | Finding | Numbers | Tag | Status | DOI / ID |
|---|---|---|---|---|---|
| E8 | Cepeda et al. 2006 spacing synthesis: optimal inter-study gap increases as retention interval increases | 839 assessments, 317 experiments, 184 articles | B | UNCHECKED | 10.1037/0033-2909.132.3.354 |
| E9 | Rowland 2014 testing effect: retrieval beats restudy | g = 0.50, 95% CI 0.42 to 0.58; 159 effect sizes, 61 studies; 81% positive; with feedback 0.73, without 0.39. Adesope et al. 2017 (secondhand): g = 0.61 | B (A if Adesope confirmed) | UNCHECKED | 10.1037/a0037559 |
| E10 | Brunmair and Richter 2019 interleaving | overall g = 0.42 (59 studies, 238 effect sizes); paintings 0.67; maths 0.34; WORDS -0.39 (blocking better); texts and tastes n.s.; stronger when categories similar to each other and items within a category dissimilar | B | UNCHECKED (preprint text) | 10.1037/bul0000209 |
| E11 | Driskell, Willis and Copper 1992 overlearning: significant, moderate effect on retention; moderated by degree, task type, retention length | d = 0.75 for cognitive tasks (secondhand via Rohrer et al. 2005; only 7 of 51 comparisons had long intervals, none over 4 weeks). The "50% overlearning threshold" is NOT FOUND in this paper. | B | UNCHECKED | 10.1037/0021-9010.77.5.615 |
| E12 | Arthur et al. 1998 skill decay (verified from full text by the research subagent, OCR caveats) | Overall d = -0.97 (delta -0.95, k = 178, N = 8,719). By interval: 1-7 d -1.03 (k=89); >7-14 d -1.54 (13); >14-28 d -0.95 (19); >28-90 d -0.65 (33); >90-180 d -1.42 (7); >180-365 d -1.04 (11); >365 d -1.28 (k=3, N=275). By task: physical -0.76 vs cognitive -1.18; speed -0.33 vs accuracy -1.02; closed-loop -0.73 vs open-loop -1.06; natural -0.94 vs artificial -1.00. | B | UNCHECKED | 10.1207/s15327043hup1101_3 |

Cautions on E12: the abstract says -1.4 at 365+ days but the paper's own table gives -1.28 from only 3 studies; -1.42 belongs to the 90-180 day band; decay is NOT monotonic across bands (interval confounded with task mix). The values are all-task means. d is in SD units and CANNOT be converted to a decay rate without baseline variance. Round 1 wrongly used -1.40 as the cognitive-family value.

Usable from E12 with confidence: ORDERING only. Cognitive faster than physical; accuracy-graded faster than speed-graded; open-loop faster than closed-loop; natural vs artificial nearly equal.

E13 Savings on relearning: conceptually supported (Ebbinghaus savings, E6) but no verified meta-analytic magnitude. [D]

## 3. Individual differences

| ID | Finding | Numbers | Tag | Status | DOI / ID |
|---|---|---|---|---|---|
| E14 | Colquitt, LePine and Noe 2000 training meta-analysis (full text via subagent, OCR caveats) | Cognitive ability: rho = .69 with declarative knowledge (k=12, N=6,737), rho = .38 with skill acquisition (k=17, N=6,713). Conscientiousness: .38 with MOTIVATION to learn (k=3, N=388) but -.01 with knowledge and -.05 with skill acquisition (both n.s.). Anxiety: -.57 motivation (k=3), -.17 knowledge (k=8), -.15 skill acquisition (k=4). Pre-training self-efficacy: .42 motivation, .30 knowledge, .32 skill. Motivation predicts outcomes beyond ability (beta .39 knowledge, .22 skill). | B | UNCHECKED | 10.1037/0021-9010.85.5.678 |
| E15 | Round 1: grit is essentially conscientiousness (Credé et al. 2017 jangle fallacy) | little incremental validity | B | PARTLY CHECKED (round-1 critique) | not captured |
| E16 | Round 1: growth mindset effects are tiny (Sisk et al. 2018; two meta-analyses inside ONE paper, so not independent) | r = .10; intervention d = .08 on academic achievement (schoolchildren, not skill acquisition) | B | PARTLY CHECKED | 10.1177/0956797617739704 |
| E17 | Round 1: Mosing et al. 2014 twin study, music PERCEPTUAL discrimination ability: heritability 40-70%, no causal practice effect after genetic control | N = 10,500, single study, one domain, measured perceptual aptitude not performance skill. Heritability is not fixedness. Overgeneralised in round 1. | C | PARTLY CHECKED | PMID 25079217 |
| E18 | Round 1: Hambrick and Engle 2002 | measured memory/comprehension of baseball content; did NOT estimate any learning rate. "WMC sets the learning-rate parameter" is NOT supported. | C | PARTLY CHECKED | PMID 12018938 |

NOT FOUND: Big Five effect sizes for openness, extraversion, agreeableness, neuroticism on learning rate; Blume et al. 2010 transfer correlations; variance in asymptotic ceilings between people; sensitive periods; sex differences (and per project rules there is no sex special-casing anyway).

## 4. Performance versus stored skill (state effects)

| ID | Finding | Numbers | Tag | Status | DOI / ID |
|---|---|---|---|---|---|
| E19 | Pilcher and Huffcutt 1996 sleep deprivation: strongly impairs functioning; mood affected more than cognitive or motor performance; partial deprivation worse than short- or long-term total deprivation | 19 studies, 143 coefficients, N = 1,932; specific d values NOT verified | B | UNCHECKED (abstract) | 10.1093/sleep/19.4.318 ; PMID 8776790 |
| E20 | Lim and Dinges 2010: 24-48 h deprivation reduced performance across cognitive domains except accuracy in processing speed and reasoning | 70 articles, 147 cognitive tests | B | UNCHECKED | PMC3290659 |

NOT FOUND: choking under pressure effect sizes (Beilock and Carr 2001), Yerkes-Dodson empirical test (contested anyway, do NOT implement inverted-U), decomposition of within-person state variance vs stable skill, magnitudes of stress effect on a learned skill.

## 5. Feedback, metacognition, transfer, deliberate practice

| ID | Finding | Numbers | Tag | Status | DOI / ID |
|---|---|---|---|---|---|
| E21 | Kluger and DeNisi 1996 feedback interventions (round 1): average improvement but over a third decrease performance; shifting attention to the self (praise, comparison, ego threat) hurts, task-focused feedback helps | d = 0.41 mean; about 38% of effects negative; 131 studies, 23,663 observations. Single, 30-year-old meta-analysis, mostly workplace and lab tasks. Round 1 over-tagged it [A]. | B | PARTLY CHECKED | 10.1037/0033-2909.119.2.254 |
| E22 | Zell and Krizan 2014: self-evaluations of ability correlate moderately with performance | M r = .29 (SD .11, range .09 to .63) over 22 meta-analyses; higher for domain-specific, objective, familiar, low-complexity tasks | A (synthesis of 22 meta-analyses) | UNCHECKED | 10.1177/1745691613518075 |
| E23 | Dunning-Kruger effect is CONTESTED. Gignac and Zajenkowski 2020 (IQ, N = 929): mostly a statistical artefact; Hiller 2023 comment disputes a recoding choice; Nedelec, Dunkel and van der Linden 2023 replication found a significant DK effect. Magnus and Peresetsky 2022 and Mazor and Fleming 2021 not opened. | | X | UNCHECKED | 10.1016/j.intell.2020.101449 |
| E24 | Far transfer is null: Sala and Gobet 2017; Gobet and Sala 2023 (chess, music, working-memory training). Melby-Lervåg et al. 2016 cited as concordant, not opened. | little to no true variability between training types | A | UNCHECKED (abstract and snippets) | PMC5724589 ; PMC9903001 |
| E25 | Macnamara, Hambrick and Oswald 2014 deliberate practice: 26% games, 21% music, 18% sports, 4% education, under 1% professions. 2018 corrigendum (88 studies, 14% overall): games 24, music 23, sports 20, education 5, professions 1. Ericsson and Harwell 2019 dispute what counts as deliberate practice (r = .50 games k=5, .71 music k=3, .58 sports k=5, tiny k). Retrospective practice estimates; few professions studies. | | B, definition contested [X for strong claims either way] | UNCHECKED | 10.1177/0956797614535810 ; PMID 29733772 |
| E26 | Dreyfus stage model lacks empirical support (Peña 2010, medical education critique) | | X | PARTLY CHECKED | 10.3402/meo.v15i0.4846 |

## 6. Computational models

| ID | Finding | Numbers | Tag | Status | DOI / ID |
|---|---|---|---|---|---|
| E27 | Half-life regression (Settles and Meeder 2016): recall p = 2^(-delta/h), half-life h = 2^(theta . x), x = counts of exposures, correct, incorrect (square-root transform helps) | 12.9 M Duolingo traces. MAE 0.128 vs Leitner 0.235, Pimsleur 0.445, logistic regression 0.211, constant 0.175. AUC only 0.538 (Leitner 0.542). Half-life Spearman 0.201. | C | UNCHECKED (full text via subagent) | 10.18653/v1/P16-1174 |
| E28 | ACT-R base-level learning and Pavlik and Anderson practice-and-forgetting: activation is a log-sum of power-decaying traces over past timestamps (closed-form given timestamps) | fitted parameters NOT verified | D | UNCHECKED | 10.1207/s15516709cog0000_14 |

NOT FOUND: Bayesian Knowledge Tracing equations with fitted values (hidden-Markov, sequential), Performance Factors Analysis fitted values, FSRS equations and parameters. Do not copy any FSRS constant from memory.

---

## 7. Claims that must NOT be implemented as stated (mismatch and overclaim log)

1. "Individual learning curves universally follow exponential decay" (round 1 headline). Contested [X]; see section 1.
2. d = -1.40 at one year used as the cognitive-task retention value. It is an all-task figure from k = 3 and differs from the paper's own table (-1.28).
3. The "50% overlearning threshold" attributed to Arthur 1998 or Driskell 1992. Not found in either.
4. "WMC or genetic aptitude is the learning-rate parameter" and "genetics multiplies probability of starting practice". Single studies of different outcomes; unsupported leaps.
5. "Minimal parameter set explains most variance" (round 1 part 11). No source gives variance explained for that set, and it contradicts the report's own finding that practice count explains little variance in real domains.
6. The 10,000-hour rule and "talent doesn't matter / practice explains nothing" in either direction. Both over-read E25.
7. Growth mindset as a meaningful driver of learning (E16, d = .08). Grit as a separate predictor from conscientiousness (E15).
8. Positive far transfer or "learning to learn" generalisation (E24; learning-to-learn NOT FOUND).
9. Inverted-U (Yerkes-Dodson) stress-performance curve. Contested; no verified source.
10. Dunning-Kruger as a built-in novice overconfidence bias (E23 contested).
11. Citing Zhang et al. 2025 as evidence for the true curve shape (E5).
12. Round-1 body footnotes for Heathcote pointed to other papers; Arthur claims pointed to a first-responders article; Dunning-Kruger citation title belongs, I believe, to a 2022 paper by different authors (unverified).

## 8. Research gaps (NOT FOUND, require future research or stay [U])

Sleep consolidation magnitudes (Rasch and Born 2013 fetch failed); choking under pressure; stable-skill vs state variance split; adult skill initiation triggers and abandonment rates; hours per week on self-directed learning; novice vs expert LANGUAGE markers (vocabulary, hedging, curse of knowledge) and how zero-knowledge responses look (confusion, bluffing, deflection); BKT, PFA, FSRS and ACT-R fitted parameters; Big Five effect sizes beyond conscientiousness; Blume et al. 2010; Melby-Lervåg numbers; negative-transfer meta-analyses; Macnamara and Maitra 2019 replication figures; Cepeda optimal-gap ratios; Driskell 50% threshold; Magnus and Peresetsky 2022; Mazor and Fleming 2021.

Full text of both reports and the critiques lives in the transcript at /mnt/transcripts/2026-10-18-12-58-56-mirofish-hormones-skills.txt (and journal.txt for earlier sessions).
