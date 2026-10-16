# Evidence-linked reports

16 October 2026. Implements MiroFish roadmap item 5 ([roadmap](design/MIROFISH_NEXT_FEATURES.md)): an outline → tool → section report over a checkpoint, with executed tool output kept separate from model-written text. Code: `devsim/report.py`. Checks: `checks/check_report.py`.

## Workflow

| Step | Who | Output |
|---|---|---|
| Tools | Deterministic code, read-only (state hash checked) | Evidence items `E1…En`, each with a category, tool name and the event/action ids it rests on |
| Outline | The local model (`task: report_outline`) | 2–5 sections, each a question with 1–12 cited evidence ids |
| Sections | The local model (`task: report_section`), one call per section, seeing only that section's evidence | Typed claims with citations, plus open questions |
| Render | Code | `report.md` (labeled claims, then the tool results as a separate appendix) and `report.json` |

Evidence categories and tools:

| Category | Tool | Content |
|---|---|---|
| `observed_outcome` | `controller_events` | Applied controller events (interventions, scenario background, conversations) with their recipients |
| `observed_outcome` | `resolved_actions` | Each decision and the resolved outcome as its owner received it |
| `observed_outcome` | `utterances` | What someone said, labeled an unverified claim, not a world fact |
| `observed_outcome` | `state_changes` | Goal status/progress, trust/closeness and enduring facet changes since the initial world, plus final mood (needs `--initial`) |
| `agent_interpretation` | `checkpoint_memory_view` | Each person's current meaning of a received memory and the previous version if it was revised. Authored background lines are excluded |
| `agent_interpretation` | `graphiti_quick_search` | Optional ranked results of a search over one person's current private graph view (`--graph-query OWNER QUERY`) |

## Claim discipline

Every claim is typed and validated before it is accepted (two repairs, then the report fails):

- **Observed** claims cite only `observed_outcome` items.
- **Agent interpretation** claims cite at least one `agent_interpretation` item.
- **Researcher inference** claims cite whatever they rest on.
- A claim may cite only its section's evidence. Unknown ids, untyped claims and uncited claims are rejected.

The checks confirm that a claim points at the right kind of evidence. They do not confirm that the claim is true. `report.md` says so at the top.

## Run it

```sh
python3 -m devsim.report CHECKPOINT.json --initial INITIAL.json \
  --focus "Optional research question" \
  --graph-query priya "robotics club" \
  --api http://127.0.0.1:8081 --out runs/live/NEW_REPORT
```

Writes `report.md`, `report.json`, `requests.jsonl`, `source-hashes.json`, `server-model.json` and `summary.json` into a fresh directory. `--graph-query` needs a checkpoint with a cognition policy and the local Graphiti service; if the search fails, the error goes in the tool log and nothing becomes evidence. From Python: `gather(engine, initial, graph_queries)`, `generate(engine, api=..., model=...)` and `render(report)`.

## Verification

- [Check suite](../checks/results/report-engineering-checks.json): 9 named checks with stubbed transport. Four deliberate mutations each fail the suite: accepting an observed claim that cites interpretations, filing utterances as interpretations, turning a failed graph search into evidence, and reporting authored background as an interpretation.
- [Live evidence](../runs/live/report-live/README.md): a report on the authored scenario's Graphiti run with the actual 27B model. 5 calls, no repairs, 65 evidence items, 4 sections and 23 claims. Without being told, it flagged the day-5 club claim that contradicts the day-10 invitation.

## Limits

- Claims are checked for citation type, not truth. A wrong reading can cite the right items; the live report over-reads closeness values of 0.0 as "integration without deep bonds", which may only reflect that these situations never update closeness.
- Contradictions are found by the model, not by a deterministic tool.
- The memory view is the checkpoint's current state. It does not reconstruct what someone knew at an earlier time.
- One checkpoint per report; no comparison across runs or seeds.
- The outline sees summaries of every item, and with the 8192-token server context that limits reports to roughly 70–80 evidence items. Longer runs will need filtering or paging.
