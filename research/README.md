# Research material

| Path | Contents |
|---|---|
| [`sources/`](sources/README.md) | The ten design and research reports (PDF plus searchable text) that the engine implements, with the mechanism reference guide. Original hashes are retained. |
| `sources/page-marked/` | Alternate text extractions of seven of the reports with `=== PAGE n ===` markers, useful for citing page numbers. |
| `ipip-neo-120/` | IPIP-NEO-120 paper, scoring notebook and the derived item-score dataset used to fit `devsim/data/profile_population_v1_model.json` (third-party terms apply). |
| `experiments/` | Earlier personality-prompting experiments: facet-behavior and prompt-style pilots, identity/memory/mood evaluations, the mood-equation audit and the 27B server launch script. Scored outputs are in `experiments/results/`; raw blind/key files, rubrics, protocols and scoring scripts are in `experiments/raw/`. |

The experiment scripts are historical. Several assume the original cluster paths and a server on port 8081. Run them from the repository root with `PYTHONPATH=.` (or after `pip install -e .`) so they can import `devsim`. `raw/long_dialogue_eval.work-version.py` is a different working copy from `experiments/long_dialogue_eval.py`.
