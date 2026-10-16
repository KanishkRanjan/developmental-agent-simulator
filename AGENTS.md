# Continuing this project

Before making implementation changes or reporting completion, read:

1. `docs/START_HERE.md` — continuation guide and user decisions.
2. `docs/BUILD_STATE.md` — latest verified build state.
3. `docs/source-to-code-audit.md` — authoritative source fidelity and missing mechanisms.
4. `research/sources/README.md` — preserved reports, searchable text and mechanism references.
5. `docs/development-notes.md` — latest developmental mechanisms, equations, checks and explicit limits.
6. `docs/RESUME.md` — current connection status, saved checkpoints and continuation commands.
7. `docs/integrated-build-notes.md` — latest cognition, history, planning and world policies, assumptions and source-version boundaries.

Use the latest audit over older milestone claims; `docs/history/` is a historical record. Historical successful runs do not establish full design coverage or scientific validity. Inspect the relevant implementation before changing it; these documents reduce rediscovery, not the need to verify code.

## Layout

- Engine code is the `devsim` package; run modules from the repository root as `python3 -m devsim.<module>`. Inside the package use relative imports.
- Checks live in `checks/`; run `python3 -m checks.run_all` (add `--skip graphiti` without the local Graphiti service). Suites write results to `checks/results/`.
- Preserved run evidence lives in `runs/` and is never edited; new runs go to a fresh directory under `runs/live/` or `runs/scripted/`, or under `work/` for scratch.
- Temporary work and local runtime state go in `work/` (gitignored).

When work changes the implementation or its verified status, update `docs/BUILD_STATE.md` and the relevant audit entries before handing off.
