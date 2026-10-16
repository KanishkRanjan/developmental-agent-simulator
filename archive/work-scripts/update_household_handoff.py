from pathlib import Path
root=Path('outputs');b=root/'agent_engine'
section='''## Latest: household environment and conversation layer

[Household implementation](HOUSEHOLD_IMPLEMENTATION.md) is the newest phase. Explicit rooms/audibility, private multi-turn conversation, waking windows/response intervals and elapsed calendar reservations now connect to the existing scheduler, memory/mood and optional cognition/development paths. Use `household_example.py` for a short scene or `simulate.py --household` for fresh combined policies; archived policies remain unchanged.

Thirteen suites pass **185 named checks plus twelve core checks**, including 24 new household checks. The actual HauhauCS 27B scene completed four independent turns/23 calls with no Graphiti fallback; a closed-room person received none of it. The final seven-year scripted combined run completed 61 actions including 16 conversation turns. [Verification](household-verification.json) and the implementation guide record the source-version boundary: optional crystallization/sample-clock refinements are locally checked, while the preserved live trace precedes them. These are engineering results, not measured human fidelity. Automatic scenario authoring, interviews, report generation and a GUI remain proposed.

Earlier milestone sections below are historical and keep their original scope.

'''
for name in ['BUILD_STATE.md','source-to-code-audit.md','RESUME.md','CURRENT_STATUS.md','FULL_BUILD_STATE.md','REVIEW_LATER.md']:
 p=b/name;t=p.read_text();head,rest=t.split('\n',1);p.write_text(head+'\n\n'+section+rest.lstrip('\n'))
p=root/'START_HERE.md';t=p.read_text();head,rest=t.split('\n',1)
p.write_text(head+'\n\n'+section.replace('(HOUSEHOLD_IMPLEMENTATION.md)','(agent_engine/HOUSEHOLD_IMPLEMENTATION.md)').replace('(household-verification.json)','(agent_engine/household-verification.json)')+rest.lstrip('\n'))
for name in ['development-notes.md','integrated-build-notes.md','README.md']:
 p=b/name;t=p.read_text();head,rest=t.split('\n',1)
 note='''## Household continuation, 16 October 2026

[Household implementation](HOUSEHOLD_IMPLEMENTATION.md) documents the new room routing, multi-turn interaction, availability/calendar timing, private observations and optional existing cognition/development hooks. `simulate.py --household` enables it in a fresh combined policy. Latest verification is 185 named checks plus twelve core checks, a four-turn actual 27B fixture and a seven-year scripted combined run. Read the guide for source-version boundaries, commands, explicit assumptions and remaining proposals; older figures below retain their historical scope.

'''
 p.write_text(head+'\n\n'+note+rest.lstrip('\n'))
p=b/'sources/README.md';t=p.read_text();t+='''\n## Household environment continuation

[New implementation and audit](../HOUSEHOLD_IMPLEMENTATION.md) connects the conversation's information-flow requirement to explicit room/audibility rules, received utterances and private appraisals. MiroFish's environment/activation code motivated the software pattern; room acoustics, waking hours and response latencies are declared scenario assumptions, not newly verified findings from the reports. The accepted memory/mood/development mechanisms remain distinct from the spoken content's factual truth.
''';p.write_text(t)
p=b/'MIROFISH_NEXT_FEATURES.md';t=p.read_text();t=t.replace('They are **not implemented additions or evidence of missing previously completed mechanisms**.',
 'Update: items 2–3 now have a bounded household implementation; see [the implementation and evidence](HOUSEHOLD_IMPLEMENTATION.md). The remaining recommendations are **not implemented additions or evidence of missing previously completed mechanisms**.')
t=t.replace('2. **An environment that routes information.**','2. **An environment that routes information — household subset implemented.**')
t=t.replace('3. **Daily availability and response timing.**','3. **Daily availability and response timing — household subset implemented.**')
t+='''\n## Implemented scope after this roadmap

`household.py` now supplies rooms/audibility and multi-turn private dialogue; calendars/routines govern response intervals, and `Lifetime` checkpoints the queues. `household_example.py` and `simulate.py --household` are executable entry points. Broader groups/channels, automatic invitations/commutes, scenario authoring, interviews, reports and the GUI remain separate proposals. Do not interpret this update as all six roadmap items being completed.\n''';p.write_text(t)
# Refresh authoritative audit map with precise new scope.
p=b/'source-to-code-audit.md';t=p.read_text();needle='| World events versus private observations |'
index=t.index(needle)
t=t[:index]+'''| Physical information routing / household dialogue | Implemented bounded household policy | `household.py` routes normal speech through same-room/explicit one-hop audibility; independent private-context turns, listener appraisals, nonverbal infants and departures are scheduler events. No universal shared transcript, autonomous conversation generation, whispering or mishearing model. |
| Daily activation / response timing | Implemented declared routines | Waking windows gate elapsed reservations/opportunities; sampled response intervals reserve calendars and persist across resume. No empirical routine/latency fit, commute policy or population time zone model. |
'''+t[index:];p.write_text(t)
print('Updated continuation entry points, audit, source guide and roadmap.')
