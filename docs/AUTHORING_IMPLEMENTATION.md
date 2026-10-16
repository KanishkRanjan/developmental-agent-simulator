# Scenario authoring

16 October 2026. Implements MiroFish roadmap item 1 ([roadmap](design/MIROFISH_NEXT_FEATURES.md)): a plain-language setting becomes a reviewable spec, and a deterministic compiler turns the reviewed spec into a validated world and policy. Code: `devsim/author.py`. Checks: `checks/check_author.py`.

## Workflow

| Step | Who | Output |
|---|---|---|
| `draft` | The local model, prompted with the supported vocabulary (`task: author_scenario`) | `scenario.json`. It is accepted only if it compiles; otherwise the field-named error is fed back, up to two repairs |
| Model review | The local model compares the draft with the setting (`task: review_scenario`) | `review.json`: issues, each tied to a real field of the spec, with that field's value |
| Researcher review | You | An edited `scenario.json`. `review` re-checks it against the setting |
| `compile` | Deterministic code, no model | `initial.json`, `policy.json`, `assumptions.json`, and a scripted dry run in `summary.json` |

## Vocabulary

Unknown keys are rejected rather than ignored.

- **People:**
  - age
  - up to 10 facet percentiles, with a stated basis
  - caregivers, who must be older people in the scenario
  - up to 3 goals
  - up to 3 private background lines
  - starting `facts`, such as `{"club_member": false}`
- **Environment** (optional `household`):
  - rooms, which are any places, including school or work
  - locations and routines
  - `routes`, for commutes
  - `groups`, for institutions and clubs with meeting places and schedules
  - `channels`, for written chats
  - `invitations`
  - conversations in a room or channel
  - interviews

  See [the environment guide](ENVIRONMENT_IMPLEMENTATION.md).
- **Situations:** up to 12 recurring situations, at most daily (365 per year).
  - Each has 2–4 options.
  - Each may have `requires_facts`, so it can occur only while those facts hold.
  - An option may have `effects_success` / `effects_failure`. These set facts, or give the actor and contact a shared `relationship_role`.
  - An option with a contact may start a `conversation` or interview.
- **Interventions:** scheduled events with recipients' observations, and optional `sets_facts`.
- **Assumptions:** everything the spec assumes that the setting did not state.

### Situations that follow events

A situation that should only happen after something else uses `requires_facts`, and something has to set that fact. For example:
- The intervention "Ms. Okafor invites Priya" sets `{"priya": {"invited": true}}`.
- The situation "decide about the club" requires it.
- That situation's "join" option has the effect `{"priya": {"club_member": true}}`.
- The situation "club meeting" requires `club_member`.

Membership through an environment invitation commits `member_<group>` automatically. Starting group members get `member_<group> = true` as a starting fact.

The compiler checks that every required fact is produced by something: a starting fact, an intervention, an option effect, a starting group membership or an invitation. If nothing produces it, the situation could never occur, and the spec is rejected with the field name.

## Guarantees

- **Numbers are labeled assumptions.** `assumptions.json` lists every generated number with its JSON path, every compiler default, and the assumptions the spec states. The policy description says rates, probabilities, valences, ages and percentiles are scenario assumptions.
- **Authored claims are not simulated history.** Each background line becomes a private internal day-0 experience of its owner only, with `provenance: scenario_authoring`. Interventions are controller events delivered only to their listed recipients. Testimony must name another person as its source.
- **Facts are safe state flags.** Keys are slugs and cannot rewrite identity or family fields. Values are booleans, numbers or short text. They change only through committed events: interventions, resolved options and invitation replies.
- **Facets left out stay neutral.** They are set to the 50th percentile, not sampled.
- **Strict validation with field names.** Every field above is checked, and the full `Lifetime` policy and household validation runs against the built world.
- **Recall on in live runs.** Compiled policies enable semantic recall over the local Graphiti index (private full-text fallback, recorded, if the service is down). The scripted dry run turns graph indexing off, as `simulate --scripted` does.
- **Review cites real fields.** A model review issue whose path is not a field of the spec is repaired, and the review fails after two repairs. Review is advisory and never edits the spec.
- **Deterministic.** Compiling the same spec gives the same world and policy. The saved `initial.json` runs under `policy.json` with a fresh controller.

## Run it

From the repository root:

```sh
python3 -m devsim.author draft --setting-file setting.txt --api http://127.0.0.1:8081 --out runs/live/NEW_DRAFT
# read review.json, edit runs/live/NEW_DRAFT/scenario.json, optionally re-check it:
python3 -m devsim.author review runs/live/NEW_DRAFT/scenario.json --setting-file setting.txt \
  --api http://127.0.0.1:8081 --out runs/live/NEW_REVIEW
python3 -m devsim.author compile runs/live/NEW_DRAFT/scenario.json --out runs/live/NEW_COMPILED
```

The setting can also be given as text instead of `--setting-file`. Every step needs a fresh output directory and writes `source-hashes.json` and `summary.json`; the model steps also write `requests.jsonl`. The compile summary prints ready-to-run `run_live` and scripted `lifetime` commands. From Python, use `compile_scenario(spec)` (returns engine, policy, report), `draft(setting, api=..., model=...)` and `review(setting, spec, api=..., model=...)`.

## Verification

- [Check suite](../checks/results/author-engineering-checks.json): 13 named checks with stubbed transport and a scripted provider. They include:
  - gated situations that never occur before their intervention and do occur after it
  - chained effects with relationship roles
  - a compiled scenario using places, routes, groups, channels, invitations and interviews
  - field-cited review with repair
  - a 26-case rejection table, including fact keys, values and reachability

  Three deliberate mutations of fact gating each fail the suite: dropping the compiled gate, accepting unreachable facts, and dropping intervention facts.
- [First live evidence](../runs/live/author-live/README.md), from before facts, effects, environment and review existed:
  - The draft compiled after one field-named repair. Human review found three problems: a pre-written outcome, a testimony with no person as its source (now rejected), and a routine that contradicted the setting.
  - A live 27B run with Graphiti recall resolved all 8 actions.
  - In that run, Priya claimed a club meeting before her invitation. An authored outcome text that mentions the club, in a situation that can fire before the invitation, seeded the claim. `requires_facts` and the model review now address exactly this.
- **Live evidence for the extended vocabulary: in progress** in `runs/live/environment-live/`. The first attempt used the whole environment vocabulary but failed after two repairs on the old 52-per-year rate cap (it wrote a daily situation). The cap is now 365. A second attempt failed on a 0-year horizon and an overnight availability window `[[23, 7]]`. The vocabulary now explains both, and household validation says how to split overnight windows.
- [Manifest](../runs/verification/author-verification.json) for the first phase.

## Limits

- The model review is advisory and may miss problems or flag non-problems. It does not replace reading the spec.
- The reachability check confirms that a required fact can be set somewhere, not that it will be set before the horizon ends.
- Effects cover facts and relationship roles. Goals change only through `progress_gain`, and trust, closeness and resources are not authored.
- The dry run uses the scripted provider. It shows the policy runs, not how model-driven agents behave.
- Compiled policies do not enable reflection, autonomous goals or rumination; only recall is on.
- The prompt and output must fit the server's 8192-token context. Repairs send back the previous draft with the error so the model changes only that field, but it can still change others.
