# Personality foundation: source and cluster evidence

Prepared 16 October 2026. This is an audit of the **first layer** of the proposed social simulator, using the research sources and the already completed runs on the user's cluster. It does not claim to validate the full developmental or social model.

## What the primary papers establish

The [IPIP-NEO-120 development paper](https://www.sciencedirect.com/science/article/pii/S0092656614000506) describes a 120-item public-domain inventory with four items per facet and six facets per Big Five domain. The [original scoring keys and data archive](https://psycharchives.org/en/item/e42a4531-1daa-4f3d-aef4-58f085c77cd8) are available from the authors' supplementary materials. This gives the benchmark a real questionnaire source; it does not make questionnaire answers a direct measure of an LLM's behavior in a social simulation.

The primary [Taxonomic Graph Analysis (TGA) paper](https://journals.sagepub.com/doi/10.1177/08902070251352590) analyzes the **300-item** IPIP-NEO dataset. The authors restricted its working sample to 149,337 U.S. respondents aged 19–69 and retained 221 items in a final hierarchy of 28 first-level dimensions, six traits and three meta-traits. The paper's table and supplementary information describe the resulting dimensions and loadings. This supports the existence of that empirical structure in the analyzed sample. It does **not** validate taking an arbitrary 30-facet vector from the 120-item questionnaire and simply relabeling it as a 28-facet TGA profile. Any such mapping requires an explicit derivation and check.

This is the first source correction to the Gemini-generated personality report: the TGA result and the 120-item measurement data are related, but they are not the same instrument or automatically interchangeable parameter sets. The report's claim that the 28 facets are unavailable is too broad: the published article describes them, though a ready-made, validated 120-to-TGA conversion was not established by this audit.

## What I found on the cluster

The SSH control connection works. The remote node is `nst-n6`, with an NVIDIA RTX PRO 4000 Blackwell and approximately 24 GB GPU memory. I found an existing `big-five-steering` workspace containing the original prompting baseline and a later same-model comparison. I did not overwrite those runs.

The prompting baseline contains 8,400 final IPIP-NEO-120 item responses for 14 conditions × five repeats × 120 items. Its saved audit reports all responses present and parsed, positive high-versus-low gaps for all five targeted domains, and monotonic measured Extraversion across the five requested levels. For the separate Qwen3-8B model used in that baseline, the gap range was 18.125–38.125 points on the benchmark's 0–100 scoring scale. The largest other-domain shift was 14.375 points. These are **prompt sensitivity and leakage results**, not calibrated human personality scores.

The later comparison uses one selected 9B open-weight model. Its saved results include 55,800 fresh questionnaire/scenario/quality assessments, 5,200 conversation checkpoint probes and 2,600 generated conversation replies. It tested plain prompting, activation steering, one fixed LoRA per high-trait profile, and one adjustable LoRA conditioned on a five-number profile code. The adjustable LoRA was trained to imitate responses from the **same base model under prompting**, so its result tests distillation of that teacher, not an independently grounded human personality.

| Existing comparison, five high-trait profiles | Prompt | Steering | Fixed LoRA | Adjustable LoRA |
|---|---:|---:|---:|---:|
| Mean target questionnaire shift from common baseline | +6.708 | −0.667 | +3.000 | +14.792 |
| Fresh twenty-choice scenario alignment | 0.960 | 0.590 | 0.640 | 0.910 |
| Scenario alignment at turn 100 | 0.300 | 0.050 | 0.000 | 0.300 |

These values are copied from the cluster's saved comparison report. The twenty choices are author-written proxies, and there is only one 100-turn trajectory per profile/method. The report itself says there is no clear overall winner: prompting and adjustable LoRA differ by only one scenario choice on its main structured proxy. The turn-100 result is a strong warning that initial personality expression and persistence are different problems. The exact magnitudes should not be generalized to all models, prompts or steering algorithms.

I ran the existing strict scoring checks, the report integration check and the training-data preflight. All passed. The integration check also shows that a system producing stable but constant answers cannot win on personality control merely through stability. These checks validate important parts of the evaluation machinery; they do not validate the psychological meaning of the tasks.

## New steering diagnostic run

The comparison's nine steering configurations had identical choices on all 80 development records, despite different layers and strengths. I ran an independent, read-only next-token diagnostic using the saved Extraversion vector and the same 9B model. On one held-out conversational prompt, the total variation between baseline and steered next-token distributions was **0.021 at strength 0.5** and **0.041 at strength 2**. At a deliberately larger strength 10, it was **0.235** and the top next token changed. The vector therefore affects the model; the intervention is not a no-op. This one-prompt mechanism check cannot show that strength 10 would produce better or safe personality behavior. It suggests testing the steering magnitude and vector construction directly before concluding that activation steering as a method is ineffective.

The diagnostic script is saved in `work/diagnose_persona_steering.py` and ran on the cluster from `/tmp`, outside the existing comparison workspace. Its first attempt used the older benchmark's environment and failed because that Transformers version does not recognize the newer model architecture; rerunning in the comparison's existing environment succeeded. No package installation or model download was needed.

## What would increase confidence next

1. **Keep the instruments distinct.** Use the published 120-item scoring key for the existing questionnaire results. Derive and verify any TGA mapping from the paper's 300-item/221-retained-item structure rather than assuming a one-to-one rebucketing.
2. **Establish a behavioral ruler.** Collect or locate held-out responses from real people to social situations, or run a blinded human rating study. The current twenty forced choices and self-report questionnaire show control of test answers, not faithful behavior.
3. **Test persistence on multiple histories.** The current single 100-turn conversation per profile is too small to estimate how often character changes under different events. Use repeated trajectories and preserve failures.
4. **Diagnose steering before tuning it as a product method.** Verify effect size on logits and behavior at controlled strengths, check fluency and other traits, and compare to the same unsteered model. A stronger vector that changes text but damages competence is not a success.
5. **Only then move to memory, mood and development.** Each later mechanism needs a baseline and a held-out outcome showing that it adds information beyond the simpler personality agent.

Confidence today: **high** that this particular prompting setup changes answers on its sourced questionnaire; **moderate** that the cluster comparison measured its chosen structured tasks as reported, supported by passing checks; **low** that any tested method already yields enduring human-like personality; **no established confidence** that the full proposed simulator predicts specific people or societies. This ordering lets us build the model together without asking a compelling story to serve as proof.
