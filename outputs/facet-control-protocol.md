# Action-coding rubric and fresh-situation protocol

# V2 coding plan, written before V2 generation

The two compared agents have all 30 facets at the 50th percentile except a focal pair swapped between 85th and 15th percentile. Their five broad domain averages are identical. The facet prompt adds short, symmetrical meaning glosses. The domain prompt does not identify the focal facets.

Code a natural response `high`, `low`, or `mixed` for the scenario's target facet, using concrete actions only. Use the same definitions as the V1 rubric:

- E2: contact with several people/groups = high; alone or one familiar/small interaction = low.
- E3: clearly raises and advocates own view = high; withholds or yields without stating it = low.
- C2: arranges or tidies before activity = high; works without ordering or leaves usable mess = low.
- C5: performs or schedules concrete follow-through despite tedium = high; skips/postpones because it is tedious = low.
- O1: invents an unusual or fantastical scene/premise = high; chooses grounded realism = low.
- O4: chooses unfamiliar option = high; familiar option = low.

Conditional answers and answers containing both high and low actions are mixed. We will report the exact transcript and all mixed codes. This is a controllability test on scripted situations, not a human-behavior benchmark.

# V3 fresh-situation check, fixed before generation

Keep the V2 neutral profile (all facets 50th percentile except one pair swapped 85/15), prompt format, model, temperature, and action-coding rubric unchanged. Run the 12 new situations in `PAIRS_V3` of `facet_behavior_pilot.py`. Code blinded responses `high`, `low`, or `mixed` using `facet_behavior_v2_rubric.md`. The primary outcome is the count of scenario pairs where the high-target profile takes a high action and the low-target profile takes a low action. The domain-only prompt should produce identical responses for each pair because its text is identical at temperature zero. Do not edit these situations after reading results.
