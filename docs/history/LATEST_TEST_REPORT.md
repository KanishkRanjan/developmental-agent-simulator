# Fresh integrated test results

> **Historical record.** Moved here in the October 2026 restructure; content is unchanged apart from link targets. Counts and scope are as of writing. Commands and bare file names refer to the old `outputs/agent_engine/` layout; see [the path map](README.md#old-to-new-paths).

16 October 2026. Software correctness and integration checks; comparative evaluation remains deferred.

**139 regression checks and the twelve-check core demo passed.** Testing found and repaired an upstream infant-capability gap.

The old action selector enforced empty infant speech/plans, but generated situational rules could still describe riddles and complex challenges. Infant rule generation now chooses bounded sensory triggers and nonverbal reactions; shared context carries capability constraints, and generated rules refresh at ages two and five. These are explicit scenario constraints, not validated developmental norms.

A first replay returned the wrong root JSON key three times. The controller rejected it and rolled the event back before committing an action or rules. The prompt now gives the required root shape and the validator reports the missing key precisely. The corrected fresh replay completed. Failed evidence remains in `fixed-infant-test/run`.

| Test | Result |
|---|---|
| fresh-integrated-test/run | 1 new resolved actions; 6 model requests; 0 repairs; checkpoint restored identically from JSON/SQLite. |
| fresh-infant-test/run | 1 new resolved actions; 5 model requests; 0 repairs; checkpoint restored identically from JSON/SQLite. |
| fresh-memory-continuation | 2 new resolved actions; 14 model requests; 0 repairs; checkpoint restored identically from JSON/SQLite. |
| fixed-infant-test-v2/run | 2 new resolved actions; 15 model requests; 0 repairs; checkpoint restored identically from JSON/SQLite. |
| Fresh 100-year scripted scenario | 165 resolved actions, six retained agents, six deaths, no pending activities; JSON/SQLite identical. This seed produced no new birth; the earlier 85-year fixture covers new-generation scheduling. |

The adult continuation selected earlier encounters through indexed query expansion/semantic recall, received independent replies, and revised interpretations after the outcome. Earlier actions and original observations were preserved. The final infant replay checked bounded rules, empty speech/plans, received interactions and elapsed outcomes on the actual local HauhauCS 27B.

The scripted lifespan skips model cognition. Short live runs do not establish a complete live lifespan, human realism, or predictive improvement. Broader scope and scientific boundaries remain in the source audit. Traces before the infant correction retain their recorded source hashes; the corrected infant trace uses the final runtime.

[Machine-readable evidence](../../runs/verification/fresh-integration-verification.json) · [Current verification manifest](../../runs/verification/final-engineering-verification.json) · [Source audit](../source-to-code-audit.md)
