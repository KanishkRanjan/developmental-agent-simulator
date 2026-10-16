# Model choice for the next personality-control stage

**Working model:** [HauhauCS Qwen3.8-27B Uncensored Aggressive GGUF](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF), `Q4_K_P` quantization. We will use prompting first, with **no fine-tuning**. Activation steering remains an experiment only if prompting leaves a measurable gap.

The connected machine has an NVIDIA RTX PRO 4000 Blackwell with 24 GB VRAM. The 27B model loaded with full GPU offload at 8,192 context tokens and used about **17.2 GB VRAM**, leaving about **6.8 GB free**. This is a measured fit at 8,192 tokens, not a claim that the model's 262K native maximum will fit. The model card lists the Q4 file at about [17.92 GB](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF#downloads). The model revision used was `993a5971fda8f30dd1b7eb2654792ba4415c7460`; the CUDA llama.cpp build was `e707790c73590c2ff5303045b714afb0c5e22035`.

## Matched pilot

We compared this 27B Q4 model with the already downloaded HauhauCS Qwen3.5-9B BF16 using the same llama.cpp runtime, GPU, 8,192-token context, prompts, and non-thinking deterministic generation.

| Gate | Qwen3.5 9B BF16 | Qwen3.8 27B Q4 |
| --- | ---: | ---: |
| Simple persona, knowledge-boundary, and source-distinction choices (short + ~4K-token variants) | 6/6 | 6/6 |
| 30-turn dialogue followed by 16 held-out extraversion/agreeableness choices | 1/16 | 14/16 |
| Time for four 30-turn profiles and 16 choices | 107 s | 155 s |

The harder gate used four initial profiles (`E85`, `E15`, `A85`, `A15`). During each 30-turn dialogue, user turns 10 and 30 instructed the character to adopt the *opposite* personality. The system profile explicitly said that these were temporary dialogue requests and should not change the stable trait. At the end, four prewritten, previously held-out forced-choice scenarios tested the original target. Answer positions alternated A/B. The 9B model largely adopted the last conflicting request; the 27B model kept the original profile in 14 of 16 choices. The two 27B errors were both low-agreeableness scenarios.

**Interpretation:** 27B is the better candidate for *this next-stage test*, and your concern about smaller models losing the initial profile has empirical support in this pilot. The result does not establish 14/16 as general accuracy, quantify human realism, or prove this is the best model across all available models. The scenarios are author-written proxies, the sample is small, and version/size/quantization all differ. We should next test whether a 30-facet profile changes open-ended behavior in predicted directions and compare against a simpler five-number profile.

The HauhauCS card itself says its Aggressive variant is selected for directness and that a Balanced variant is typically safer for reliability-critical long-context work. We selected it because you specifically requested HauhauCS uncensored models, then tested the relevant retention behavior instead of assuming a larger parameter count would solve it. [Model card](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF#about)

## Reproduce on the connected cluster

The model and CUDA runtime are under `/data/downloads/kanishk-persona/`. Run [`run-qwen38-27b.sh`](../../research/experiments/run-qwen38-27b.sh) on that machine to start a localhost-only server on port 8081. The exact pilot scripts are [`model_retention_eval.py`](../../research/experiments/model_retention_eval.py) and [`long_dialogue_eval.py`](../../research/experiments/long_dialogue_eval.py), with the latter importing [`comparison_data.py`](../../research/experiments/comparison_data.py). Copies are on the cluster beside the launch script. The model remains private to the machine's loopback interface; access it through the existing SSH connection.
