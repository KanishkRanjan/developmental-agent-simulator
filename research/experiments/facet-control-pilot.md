# 27B personality-control pilot

## Decision for the next build step

Use the local HauhauCS Qwen3.8-27B model through its chat-completions API with an explicit personality profile in the system message. Activation steering is not needed for the current prototype. An API is the way to call the model; a prompt or a steering vector is how we try to influence its behavior. This pilot tests prompting. It does **not** establish that a generated agent behaves like a real person.

The 9B model is out of scope for further testing at the user's request.

## What was tested

The same 27B model answered short, open-ended situations at temperature 0, with thinking disabled. The test compared two descriptions of a synthetic person:

- **Five domains:** one percentile for each Big Five domain.
- **Thirty facets:** all facet percentiles, including two deliberately opposed facets in the same domain.

For each of three pairs—E2 sociability versus E3 assertiveness, C2 orderliness versus C5 self-discipline, and O1 imagination versus O4 openness to unfamiliar experiences—I made two profiles. One put the first facet at the 85th percentile and the second at the 15th; the other reversed them. The five-domain averages were identical. Each profile received four situations per pair and both prompt formats, making 48 responses per version. A fixed action rubric coded each response as high, low, or mixed for the situation's target facet. A *concordant* response chose the expected high or low action for that target.

| Prompt version | Facet prompt: concordant responses | Domain prompt: concordant responses | Facet prompt: scenario pairs with opposite expected actions |
|---|---:|---:|---:|
| V1, sampled background and bare facet names | 13/24 | 9/24 | 3/12 |
| V2, neutral background and short facet meanings | 21/24 | 8/24 | 9/12 |
| V3, fresh situations with V2 prompt unchanged | 18/24 | 10/24 | 6/12 |

The domain-only prompt necessarily receives identical text for both members of each matched pair. At temperature 0 it produced the same answer in all 12 paired situations, so its 0/12 opposite-action count is a design property of this test, not a broad claim about domain-based agents. Its 8/24 V2 concordance score mainly reflects which actions the situations happened to elicit.

The facet prompt can express distinctions hidden by the domain average. For example, in V2 a high-assertiveness agent stated a mild disagreement before a meeting ended, while the matched low-assertiveness agent let it pass. In another situation, the high-orderliness agent sorted collage materials before starting; the matched low-orderliness agent began without sorting.

V3 kept the V2 system prompts byte-for-byte identical and changed only the situations. The effect persisted but weakened: 6 of 12 matched scenario pairs showed opposite expected actions, compared with 9 of 12 in V2. The failures matter. A high-self-discipline profile postponed a repetitive photo-sorting task, a high-openness-to-experience profile chose the familiar dance class, and a low-self-discipline profile still persisted with a tedious puzzle. The model also mixed signals in some social answers, so the rubric marked them mixed rather than giving them credit. V2 had its own failures: a high-orderliness profile left a usable but untidy workspace alone, and a high-self-discipline profile skipped optional language drills.

## How much to trust this

V2 was revised after inspecting V1. It is a development result, not independent confirmation. V3's situations and scoring rubric were fixed before V3 generation, making it a better check of the V2 prompt, though still small. The V2/V3 prompt supplied plain-language definitions of the targeted facets, so its gain may come from clearer instructions rather than a deeper psychological representation. The actions were coded by the same analyst who designed the test; the shuffled list reduced but did not fully remove awareness of conditions. There is one model, one background profile, a small set of artificial situations, and no human behavioral ground truth. A personality-control result cannot be converted into an accuracy percentage for human replication.

The next useful test is robustness across more profiles and situations, with independent blinded coders. The meaningful research test is whether facet-based agents predict held-out choices of consenting people better than simpler profiles with the same information budget. No activation steering experiment is justified yet: the local API plus a clear prompt already gives a controllable first prototype, and the remaining question is whether its behavior is valid.

The [pilot script](facet_behavior_pilot.py), [rubric and V3 protocol](facet-control-protocol.md), [V1 scored responses](results/facet-pilot-v1-scored.jsonl), [V2 scored responses](results/facet-pilot-v2-scored.jsonl), and [V3 scored responses](results/facet-pilot-v3-scored.jsonl) make this result inspectable. “High,” “low,” and “mixed” are action codes, not judgments about the quality of a response.
