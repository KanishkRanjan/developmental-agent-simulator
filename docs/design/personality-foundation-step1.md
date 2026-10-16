# Step 1 — evidence-grounded personality profiles

This is the first working layer of the social simulation. It generates **30 IPIP-NEO-120 facet scores** (each 4–20) while preserving the dependence observed between facets in respondent data. It does **not** yet generate behavior, mood, development, or a complete person.

## What was built

- [`profile_population_v1.py`](../../devsim/profile_population_v1.py) scores respondent item data, fits a Gaussian copula to the 30 facets, and samples bounded profiles.
- [`ipip_neo_120_key.json`](../../devsim/data/ipip_neo_120_key.json) records the 120 item-to-facet assignments from [Johnson's original 2014 paper, Table 1](https://doi.org/10.1016/j.jrp.2014.05.003).
- [`profile_population_v1_model.json`](../../devsim/data/profile_population_v1_model.json) contains only aggregate facet distributions and their latent correlations, so sampling does not require the respondent file.

The fitting data is the [NeuroQuest derived parquet](https://huggingface.co/datasets/ecorbari/IPIP120-SCORES), which the maintainers say comes from [John Johnson's published respondent data](https://osf.io/tbmh5/). The derived parquet contains 410,376 records. We retained 339,434 records with age 18–70 and complete 1–5 item responses. This is a **self-selected internet sample**, not a representative population. The parquet's item columns are already reverse-keyed; applying the published key's reversal again would invert some facets. We caught and corrected this by cross-checking every recomputed raw facet sum against the parquet's reported facet scores. All 30 correlations are positive and above 0.927.

## Verification

The fit used an 80/20 respondent split (271,547 fitting records; 67,887 held out). We generated 67,887 new profiles and compared them with the held-out respondents:

| Check | Result |
| --- | ---: |
| Mean absolute error of 30 facet means, on 4–20 score scale | 0.0175 |
| Mean absolute error of 30 facet standard deviations | 0.0110 |
| Mean absolute error of 435 pairwise facet correlations | 0.0080 |
| Largest absolute pairwise correlation error | 0.0388 |
| Pairwise correlation error when sampling facets independently | 0.1964 |
| Generated scores outside 4–20 | 0 |

The same fitting run produced the same results on the connected RTX PRO 4000 Blackwell cluster. This is a distribution-reproduction check. It does not show that sampled profiles predict speech or action, and it cannot prove a synthetic life history matches an actual human.

## Use

Run `python profile_population_v1.py sample --model profile_population_v1_model.json --count 5 --seed 42` from this directory after installing `numpy`, `pandas`, `pyarrow`, and `scipy`. To refit, download the source parquet and run `python profile_population_v1.py fit --data /path/to/IPIP120-SCORES.parquet --out profile_population_v1_model.json`.

The next layer is mapping this structured profile into a model prompt and testing whether different target facets cause distinguishable **behavior**, with profile information held constant across models. Fine-tuning is excluded per your request. The original 30 IPIP facets and the 28 empirical facets in the later TGA paper are separate constructs until we estimate a defensible mapping; relabeling one as the other would be invalid.
