# Identity, memory and mood prototype evaluation protocol

Fixed before model generation. Use only the local 27B model, temperature 0, no activation steering or fine-tuning.

## Claims and outcomes

1. **Internal correctness**: simulation-time ordering; world events cannot silently enter an agent's observations; overhearing can; duplicate event IDs do not duplicate observations; diagnostic retrieval does not mutate memory; recall curve has R(S)=0.9; mood valence and arousal are separately bounded, recover with simulated time, and do not alter stable traits. These are software invariants, not empirical psychological validation.
2. **Factual memory utility**: 16 synthetic multiple-choice questions about agents' own observations after distractor events, with the same observations and context budget. Compare four-message prompts selected by (a) most recent, (b) simple lexical overlap, and (c) the proposed retrieval ranking including elapsed-time accessibility and event salience. Exact answer accuracy is the metric. This test can show an implementation advantage over simple selection, not human memory fidelity. Report the strong lexical baseline explicitly.
3. **Mood expression**: present matched immediate and delayed social situations to the same personality profile, with and without the prototype's current valence/arousal state. Inspect whether choices change and return toward baseline without trait mutation. No synthetic expected choice is treated as human ground truth; report qualitative or choice-distribution effects only.

The proposed mood half-life and memory stability are explicitly illustrative. Do not claim quantitative agreement with human affect or autobiographical recall. A "substantial improvement in replicating people" requires held-out individual-level human outcomes and a strong persona-plus-history baseline; this prototype cannot establish that claim.
