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

The target is a run directory (`world.json`, `requests.jsonl`) or a checkpoint file. During a live run, `requests.jsonl` grows as calls finish and `world.json` is rewritten after every scheduler event, so the views show agent state mid-run. Before the first checkpoint exists, the page shows the streaming timeline and a note. The server binds only to `127.0.0.1` and serves only the page and its data. Reading never changes a checkpoint.

## Watching in a terminal

## The control panel (one terminal app)

```sh
python3 -m devsim.app [--api http://127.0.0.1:8081]
```

On first start it asks what people in the world should call you (Enter keeps your login name) and remembers it in `work/control-panel.json`; `y` changes it, and the top bar shows it. It opens with the logo and Pip, the panel's little ASCII robot, and checks that the model server is up. Four tabs (Tab or 1-4):
- **Runs:** every simulation under `runs/live`, `runs/scripted` and `work/runs`, marked running, completed, stopped, failed or interrupted, with day and model calls. Enter offers:
  - Watch;
  - Characters;
  - Stop: SIGINT; `run_live` records `stopped` and the checkpoint stays valid;
  - Resume: a fresh `NAME-r2` from the checkpoint and its archived policy.

  `n` starts a new run from any compiled world: pick it, name the run, choose how long (1, 3, 7 or 30 days, the whole scenario, or typed) and how fast (real time, 1 simulated hour per minute, or as fast as the model allows). Runs start detached (`runs.start`, `pid.json` and `run.log` beside the run) and keep going when the panel closes.
- **Watch:** the full watcher (`p` panel, `m` map/web, `t` talk menus); Esc returns.
- **Characters:** a searchable list (name, id or @handle) with age, place, mood and stress. Open someone to see their card and to:
  - send a notification (they see it on their phone);
  - change personality (Big Five sliders, or all 30 facets), clinical dials, hormones, needs, mood, goals (add, complete, abandon), the trust and closeness of any tie, or a skill's stored level (any skill by name; with the skills module).

  The card shows the person's top skills (stored level and today's tier) when the skills module is on. The builder's Modules list and the start dialog both offer `skills`.

  In a running simulation, changes go through the run's inbox (`visit.edit`, `visit.notify`). They apply all-or-nothing at the next event boundary and are logged in `runtime.researcher_edits` as researcher interventions. For a stopped run they are applied to a staged copy (`NAME-r2/start-world.json`) when you resume it; the old checkpoint is never edited.
- **New:** a step-by-step builder (`devsim/builder.py`), saved as `work/designs/<slug>/design.json` after every step (reach it with `4`, Tab, or `n` → "Design a new world…"; each rebuild goes to the next free `compiled-N` folder):
  - basics and duration;
  - places from templates (home, school, office, hospital, park) and travel times;
  - main characters: name, age, who they are, goals, Big Five sliders, home, and daily hours (student, works days, evening shift, at home);
  - side characters: name, age, one line;
  - relationships (parent, grandparent, sibling, partner, friend, cousin, classmate and so on);
  - background crowd (society layer off, small or large);
  - modules;
  - how to begin.

  **Build** fills each person with one small model call (facets the description implies, where sliders win; background; and for main characters goals and a situation of their own). It compiles with builder limits (up to 30 people), applies sliders and relationships, then begins in one of three ways: the model writes each adult's past (`biography.expand`), a scripted fast-forward of N years (situation highlights, development and sleep; labelled scripted), or no written past. Pip animates while it works. Without the model, people keep sampled personalities.

Checks: `check_tui` (widget helpers), `check_runs` (discovery, liveness, start, stop, resume and staged edits), `check_builder` (layout, sliders, relationships, both beginnings, problems, limits), plus researcher edits in `check_household`. The app was also driven in a pseudo-terminal: splash, runs list, a character's card and sliders, and a full builder walk-through to a compiled world.

Where port forwarding is blocked (as on the cluster machine), watch a run over plain SSH:

```sh
python3 -m devsim.watch runs/live/RUN/run             # full-screen app
python3 -m devsim.cockpit runs/live/RUN/run --follow  # plain scrolling lines
```

`devsim/watch.py` is a full-screen `curses` app (standard library only). The left panel shows each person's place, or "in transit", and current mood. The right panel shows the conversation feed: committed decisions and what was said, grouped under the simulated day, time and place (room, channel, group, interview, invitation or situation). The bottom line shows the latest model call. Keys:

- `q` quits.
- `↑`/`↓` and `PgUp`/`PgDn` scroll, and `End` returns to the live bottom.
- `a` switches between all decisions and speech only.
- `1`–`9` show one person (and pick them for the panel), and `0` shows everyone.
- `p` slides the **character panel** in from the right, or out again. It shows:
  - the person's face as ASCII art, with an expression that follows their mood, stress and sleep pressure;
  - age, place and current activity, and their main personality tendencies;
  - mood bars; hormone bars (stress, sleep pressure, dopamine) and need bars when those modules are on;
  - goals with progress, their closest people (closeness and trust), their latest inner thought and last line;
  - how many memories are still recallable.

  `Tab` picks the next person.
- `m` cycles the right pane through a **room map** (rooms as boxes per site, joined where they can hear each other, people by number, pets, people in transit), a **relationship web** (the picked person in the middle, lines by closeness, labels with closeness and trust, from their own records only) and the feed.
- `t` opens a **menu** instead of commands. You can:
  - talk to someone face to face or phone them, picking from a list that shows where they are and whether they are awake;
  - introduce a new character through a short form: name, who they are, age, whom they meet, how they know them (stranger, classmate, cousin and so on, or your own words), then confirm;
  - send one of your characters again;
  - speak to the group.

  During a talk, `t` types your next line, and `Tab` offers "let the model play your character" and "end the talk". Typed commands (`@name`, `/call`, `/send`, `/auto`, `/bye`) still work for power users. `c` calls someone from a list.

**Faces** use shape-matched ASCII after Alex Harri's method (`devsim/ascii_art.py`). Each cell is sampled with 6 circles; directional contrast against 10 outside circles and global contrast are applied; the nearest of 95 precomputed glyph shapes (`devsim/data/ascii_shapes.json`, built with `python3 -m devsim.ascii_art --build-shapes` from DejaVu Sans Mono) is chosen. Looks are seeded per person and shaped by age. Checks: `checks/check_ascii.py`.

**Introducing a character** with a description makes one model call. It synthesizes the facets the description implies and up to 3 first-person background sentences as the character's own memory; scripted runs keep a sampled personality. A stated relationship becomes a fact for both people at the first meeting, with role, trust and closeness from `visit.RELATIONSHIPS` (design defaults). The person gets one introduction memory marked `researcher_introduced`, and no shared past is invented.

It refreshes every 2 seconds and never changes the run. Checks: `checks/check_watch.py`, covering data and layout without a terminal. It was also run in a real pseudo-terminal against the live environment run.

## Verification

- [Check suite](../checks/results/cockpit-engineering-checks.json): 7 named checks on a scripted fixture, covering read-only loading, perspective isolation, gist-only and omitted faded memories, script-safe embedding, the pre-checkpoint timeline and the loopback server. Five deliberate mutations each fail the suite.
- [Evidence](../runs/live/cockpit-live/README.md): the static cockpit of the authored scenario's Graphiti run, rendered in headless Chromium in light and dark themes at 1280 and 390 px with no script errors or horizontal overflow, plus a browser-driven live-mode test.

## Limits

- Mood is shown at the checkpoint's day only; there is no mood history chart.
- Accessibility is computed for the checkpoint's day. The cockpit does not reconstruct what someone could recall at an earlier time.
- Mid-run state is as of the last completed scheduler event; a model call in progress is not shown until its event commits.
- No staged setup wizard: scenarios are created with `devsim.author` and runs started from the command line.
- One run at a time; no side-by-side comparison.
