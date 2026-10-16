# Cockpit evidence (16 October 2026)

[`author-graphiti-cockpit.html`](author-graphiti-cockpit.html) is the static cockpit of the [authored scenario's Graphiti run](../author-live/README.md) (day 58.44, 45 model calls). Open it in any browser; it needs no server.

```sh
python3 -m devsim.cockpit runs/live/author-live/compiled-graphiti/run --out runs/live/cockpit-live/author-graphiti-cockpit.html
```

It holds the researcher view and three agent perspectives: Priya (18 accessible memories, 8 actions), Arun (9 memories) and Meera (11 memories). Every memory in this run was still above the detail threshold at day 58, so all show `episodic_detail`.

## Browser verification

Headless Chromium (Playwright, in a scratch environment under `work/`) loaded the page and switched between the researcher view and Priya's perspective. This was done in light and dark themes at widths of 1280 and 390 px. In all eight cases there were no script errors and no horizontal overflow. Four of the screenshots are in [`screenshots/`](screenshots/).

Live mode was tested against a scratch run directory:
1. The directory started with 3 model calls and no checkpoint. The page showed the timeline and a "no checkpoint yet" note.
2. Seven calls and a half-written line were appended. The page updated itself to 10 calls within a poll and ignored the partial line.
3. `world.json` was added. The page switched to the full views, and Meera's perspective loaded.
