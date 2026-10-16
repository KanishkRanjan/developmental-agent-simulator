# Researcher cockpit

16 October 2026. Implements MiroFish roadmap item 6 ([roadmap](design/MIROFISH_NEXT_FEATURES.md)): a local web view of a run, from one agent's perspective or a labeled researcher view, with a live model-call timeline. Code: `devsim/cockpit.py`. Checks: `checks/check_cockpit.py`. No dependencies beyond the standard library; the page is plain HTML and JavaScript.

## Two kinds of view

| | Agent perspective | Researcher view |
|---|---|---|
| Who could see it | That simulated person | No simulated person; labeled as an outside view |
| Contents | Current mood; goals with status, progress and plan steps; relationships with trust, closeness, evidence and earlier values; calendar; own actions with speech (marked unverified) and the outcome received; **accessible** memories with source, kind, current meaning, confidence and earlier meanings | Model-call timeline (purpose, agent, day, choice, speech, repairs); every raw controller event, action and pending event as JSON; committed identities |
| Boundary | Built only from the person's own received observations and state; another person's private text never appears | Everything, with spoken claims labeled as unverified utterances |

"Accessible" uses the run's cognition policy at the checkpoint's day: a memory that has faded below the detail threshold shows only its encoded gist, and one with no accessible representation is left out. A checkpoint without a cognition policy shows received text and says that no accessibility model applies. A text filter narrows every list.

## Run it

```sh
# A self-contained HTML file for a finished run
python3 -m devsim.cockpit runs/live/author-live/compiled-graphiti/run --out work/cockpit.html

# Live: serves http://127.0.0.1:18090/ and re-reads the run on each 5-second poll
python3 -m devsim.cockpit runs/live/NEW_RUN --serve 18090
```

The target is a run directory (`world.json`, `requests.jsonl`) or a checkpoint file. During a live run, `requests.jsonl` grows as calls finish but `world.json` is written only at the end. Until then the page shows the streaming timeline and a note, and it switches to the full views when the checkpoint appears. The server binds only to `127.0.0.1` and serves only the page and its data. Reading never changes a checkpoint.

## Verification

- [Check suite](../checks/results/cockpit-engineering-checks.json): 7 named checks on a scripted fixture, covering read-only loading, perspective isolation, gist-only and omitted faded memories, script-safe embedding, the pre-checkpoint timeline and the loopback server. Five deliberate mutations each fail the suite.
- [Evidence](../runs/live/cockpit-live/README.md): the static cockpit of the authored scenario's Graphiti run, rendered in headless Chromium in light and dark themes at 1280 and 390 px with no script errors or horizontal overflow, plus a browser-driven live-mode test.

## Limits

- Mood is shown at the checkpoint's day only; there is no mood history chart.
- Accessibility is computed for the checkpoint's day. The cockpit does not reconstruct what someone could recall at an earlier time.
- The live view updates the timeline from model calls. It cannot show agent state mid-run, because `run_live` saves the checkpoint at the end.
- No staged setup wizard: scenarios are created with `devsim.author` and runs started from the command line.
- One run at a time; no side-by-side comparison.
