"""Evidence-linked study report: executed tools -> model outline -> model sections of typed, cited claims.

tools:    deterministic, read-only evidence items E1..En from a checkpoint (and optionally its
          initial world and Graphiti quick searches). Each item is an observed_outcome (what the
          controller resolved or delivered, what someone said, state changes) or an
          agent_interpretation (a person's current meaning of a memory and earlier versions).
outline:  the local model groups evidence into sections, each a question with cited items.
sections: the local model writes claims typed observed / agent_interpretation /
          researcher_inference. Citations are validated against the item categories.

The report keeps executed tool results separate from model-written text. A citation check
shows a claim points at the right kind of evidence, not that the claim is true.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import time

from .engine import Engine, validated_json
from .interview import state_digest

CLAIM_EVIDENCE = {'observed': {'observed_outcome'}, 'agent_interpretation': {'agent_interpretation'},
                  'researcher_inference': {'observed_outcome', 'agent_interpretation'}}
LIMITS = {'sections': 5, 'section_items': 12, 'claims': 8, 'summary_chars': 140, 'item_chars': 400}


def _clip(text, limit):
    text = ' '.join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def _observation(engine, owner, event_id):
    return next((o for o in engine.world.observations.get(owner, []) if o.event_id == event_id), None)


def gather(engine, initial=None, graph_queries=()):
    """Run the deterministic tools; return (evidence items, tool log). The checkpoint is not changed."""
    before = state_digest(engine)
    items, log = [], []

    def add(category, tool, owner, day, text, event_ids, **extra):
        items.append({'id': f'E{len(items) + 1}', 'category': category, 'tool': tool, 'owner': owner,
                      'day': None if day is None else round(day, 2), 'text': _clip(text, LIMITS['item_chars']),
                      'event_ids': event_ids, **extra})

    events = [e for e in engine.state['events'] if e['status'] == 'applied']
    outcome_ids = {a.get('outcome_event') for a in engine.state['actions']}
    for event in events:
        if event['id'] in outcome_ids:
            continue
        recipients = sorted(event['observations'])
        add('observed_outcome', 'controller_events', None, event['day'],
            f'{event["description"]} Delivered to {", ".join(recipients) or "nobody"}.', [event['id']], recipients=recipients)
    log.append({'tool': 'controller_events', 'items': len(items)})
    start = len(items)
    for action in sorted(engine.state['actions'], key=lambda a: a['day']):
        decision, owner = action['decision'], action['owner']
        outcome = _observation(engine, owner, action.get('outcome_event'))
        text = f'{owner} chose "{decision.get("action", decision.get("action_id"))}" ({action["status"]}).'
        if outcome:
            text += f' Resolved outcome as {owner} received it: {outcome.text}'
        add('observed_outcome', 'resolved_actions', owner, action['day'], text,
            [i for i in (action['id'], action.get('outcome_event')) if i])
        if decision.get('speech'):
            add('observed_outcome', 'utterances', owner, action['day'],
                f'{owner} said (an unverified claim, not a world fact): "{decision["speech"]}"', [action['id']])
    log.append({'tool': 'resolved_actions+utterances', 'items': len(items) - start})
    start = len(items)
    from .sleep import HIDDEN
    for owner in sorted(engine.state['agents']):
        received = {o.event_id: o for o in engine.world.observations.get(owner, [])}  # one index, not a scan per memory
        for event_id, meta in engine.agent(owner)['memory_meta'].items():
            obs = received.get(event_id)
            # A forgotten (dropped, merged) or unattended memory has no current meaning for this person.
            if not obs or meta.get('provenance') == 'scenario_authoring' or not meta.get('meaning') or meta.get('tier') in HIDDEN:
                continue
            versions = meta.get('versions', [])
            text = f'{owner}\'s current meaning (confidence {meta["confidence"]:.2f}): {meta["meaning"]}'
            if versions:
                text += f' Earlier meaning: {versions[-1].get("meaning", "")}'
            add('agent_interpretation', 'checkpoint_memory_view', owner, obs.day, text, [event_id],
                revised=bool(versions))
    log.append({'tool': 'checkpoint_memory_view', 'items': len(items) - start})
    if initial is not None:
        start = len(items)
        for owner in sorted(engine.state['agents']):
            if owner not in initial.state['agents']:
                continue
            now, then = engine.agent(owner), initial.agent(owner)
            changes = []
            for key, goal in now['goals'].items():
                old = then['goals'].get(key, {})
                if goal.get('progress') != old.get('progress') or goal.get('status') != old.get('status'):
                    changes.append(f'goal {key} {old.get("status")} {old.get("progress", 0)} -> {goal.get("status")} {goal.get("progress", 0)}')
            for other, rel in now['relationships'].items():
                old = then['relationships'].get(other, {})
                for field in ('trust', 'closeness'):
                    if rel.get(field) != old.get(field):
                        changes.append(f'{field} toward {other} {old.get(field)} -> {round(rel.get(field), 3)}')
            moved = {k: round(v - then['facets'][k], 3) for k, v in now['facets'].items() if abs(v - then['facets'][k]) > 1e-9}
            if moved:
                changes.append(f'enduring facet changes {moved}')
            mood = engine.mood(owner)
            changes.append(f'mood at day {engine.day:.1f}: valence {mood["valence"]:.2f}, arousal {mood["arousal"]:.2f}')
            add('observed_outcome', 'state_changes', owner, engine.day, f'{owner}: ' + '; '.join(changes), [])
        log.append({'tool': 'state_changes', 'items': len(items) - start})
    for owner, query in graph_queries:
        from .graph_tools import inspect
        try:
            result = inspect(engine, owner, query, 'quick')
        except Exception as exc:  # the report records an unavailable tool instead of inventing its output
            log.append({'tool': 'graphiti_quick_search', 'owner': owner, 'query': query, 'error': str(exc)[:300]})
            continue
        ids = [m['event'] for m in result['memories']]
        log.append({'tool': 'graphiti_quick_search', 'owner': owner, 'query': query, 'returned_event_ids': ids})
        if ids:
            add('agent_interpretation', 'graphiti_quick_search', owner, None,
                f'Graph search of {owner}\'s current private view for "{query}" returned, in rank order: '
                + '; '.join(f'{m["event"]} ({_clip(m.get("meaning") or m.get("text", ""), 90)})' for m in result['memories'][:5]), ids)
    if state_digest(engine) != before:
        raise RuntimeError('Report tools changed the checkpoint')
    return items, log


def _summaries(items):
    return [{'id': i['id'], 'category': i['category'], 'owner': i['owner'], 'day': i['day'],
             'summary': _clip(i['text'], LIMITS['summary_chars'])} for i in items]


def outline(items, focus, *, api, model):
    known = {i['id'] for i in items}
    system = ('You plan a short research report on a fictional developmental social simulation. Group the supplied '
              'evidence into 2 to 5 sections. Each section asks one question the evidence can answer: what happened, '
              'how people interpreted it, what changed, and any contradictions (for example a claim that conflicts with '
              'the timing of controller events). Cite only supplied evidence ids. Return JSON: title (string), sections '
              f'(list of objects with title, question, evidence_ids of 1 to {LIMITS["section_items"]} ids).')

    def validate(result):
        sections = result.get('sections')
        if not isinstance(result.get('title'), str) or not result['title'].strip():
            raise ValueError('title needs text')
        if not isinstance(sections, list) or not 2 <= len(sections) <= LIMITS['sections']:
            raise ValueError(f'sections: 2 to {LIMITS["sections"]}')
        for n, s in enumerate(sections):
            if not all(isinstance(s.get(k), str) and s[k].strip() for k in ('title', 'question')):
                raise ValueError(f'sections[{n}] needs title and question')
            ids = s.get('evidence_ids')
            if not isinstance(ids, list) or not 1 <= len(ids) <= LIMITS['section_items'] or set(ids) - known:
                raise ValueError(f'sections[{n}].evidence_ids: 1 to {LIMITS["section_items"]} supplied ids')
    context = {'task': 'report_outline', 'focus': focus, 'evidence': _summaries(items)}
    return validated_json(system, context, validate, api, model, 1200)


def section(spec, items, *, api, model):
    cited = [i for i in items if i['id'] in spec['evidence_ids']]
    category = {i['id']: i['category'] for i in cited}
    system = ('Write one section of a research report on a fictional simulation from the supplied evidence only. '
              'Every claim has a type: observed (what the controller resolved or delivered, or what someone said; cite '
              'only observed_outcome items), agent_interpretation (how a person understood events; cite at least one '
              'agent_interpretation item), or researcher_inference (your interpretation across evidence, such as a '
              'contradiction or pattern; cite the items it rests on). An utterance shows that something was said, not '
              'that it is true. Do not add facts beyond the evidence. Return JSON: claims (list of objects with type, text, '
              f'evidence_ids; 1 to {LIMITS["claims"]} claims), open_questions (list of strings, may be empty).')

    def validate(result):
        claims = result.get('claims')
        if not isinstance(claims, list) or not 1 <= len(claims) <= LIMITS['claims']:
            raise ValueError(f'claims: 1 to {LIMITS["claims"]}')
        for n, c in enumerate(claims):
            kind, ids = c.get('type'), c.get('evidence_ids')
            if kind not in CLAIM_EVIDENCE:
                raise ValueError(f'claims[{n}].type must be one of {sorted(CLAIM_EVIDENCE)}')
            if not isinstance(c.get('text'), str) or not c['text'].strip() or len(c['text']) > 600:
                raise ValueError(f'claims[{n}].text needs up to 600 characters')
            if not isinstance(ids, list) or not ids or set(ids) - set(category):
                raise ValueError(f'claims[{n}].evidence_ids must cite supplied ids')
            kinds = {category[i] for i in ids}
            if kind == 'observed' and kinds - CLAIM_EVIDENCE['observed']:
                raise ValueError(f'claims[{n}]: an observed claim cites only observed_outcome items')
            if kind == 'agent_interpretation' and not kinds & CLAIM_EVIDENCE['agent_interpretation']:
                raise ValueError(f'claims[{n}]: an agent_interpretation claim cites an agent_interpretation item')
        questions = result.get('open_questions', [])
        if not isinstance(questions, list) or not all(isinstance(q, str) for q in questions):
            raise ValueError('open_questions must be a list of strings')
    context = {'task': 'report_section', 'section': {'title': spec['title'], 'question': spec['question']},
               'evidence': [{k: i[k] for k in ('id', 'category', 'owner', 'day', 'text')} for i in cited]}
    result = validated_json(system, context, validate, api, model, 1500)
    return {'title': spec['title'], 'question': spec['question'], 'evidence_ids': spec['evidence_ids'],
            'claims': result['claims'], 'open_questions': result.get('open_questions', [])}


def generate(engine, *, api, model, initial=None, focus='', graph_queries=()):
    before = state_digest(engine)
    items, log = gather(engine, initial, graph_queries)
    plan = outline(items, focus, api=api, model=model)
    sections = [section(s, items, api=api, model=model) for s in plan['sections']]
    if state_digest(engine) != before:
        raise RuntimeError('Report generation changed the checkpoint')
    return {'title': plan['title'], 'focus': focus, 'day': engine.day, 'world_state_sha256': before, 'model': model,
            'sections': sections, 'evidence': items, 'tool_log': log,
            'scope': 'Model-written claims are checked for citation and type discipline only, not for truth. '
                     'Evidence items are executed tool output over a fictional simulation.'}


LABELS = {'observed': 'Observed', 'agent_interpretation': 'Agent interpretation', 'researcher_inference': 'Researcher inference'}


def render(report):
    lines = [f'# {report["title"]}', '',
             f'Simulated day {report["day"]:.2f}. Model: `{Path(report["model"]).name}`. Checkpoint sha256 `{report["world_state_sha256"][:16]}…`.', '',
             f'> {report["scope"]}', '']
    if report['focus']:
        lines += [f'Focus: {report["focus"]}', '']
    lines += ['Claims are model-written. Each is labeled **Observed** (simulation outcomes and recorded speech), '
              '**Agent interpretation** (a simulated person\'s understanding) or **Researcher inference** (the model\'s '
              'reading across evidence), and cites executed tool results listed at the end.', '']
    for s in report['sections']:
        lines += [f'## {s["title"]}', '', f'*{s["question"]}*', '']
        lines += [f'- **{LABELS[c["type"]]}:** {c["text"]} ({", ".join(c["evidence_ids"])})' for c in s['claims']]
        if s['open_questions']:
            lines += ['', 'Open questions:'] + [f'- {q}' for q in s['open_questions']]
        lines.append('')
    lines += ['## Executed tool results', '', 'Deterministic, read-only output over the checkpoint. Not model-written.', '',
              '| Id | Category | Tool | Owner | Day | Event ids | Text |', '|---|---|---|---|---|---|---|']
    for i in report['evidence']:
        text = i['text'].replace('|', '\\|')
        lines.append(f'| {i["id"]} | {i["category"]} | {i["tool"]} | {i["owner"] or ""} | {"" if i["day"] is None else i["day"]} '
                     f'| {", ".join(i["event_ids"])} | {text} |')
    lines += ['', 'Tool log:', '', '```json', json.dumps(report['tool_log'], indent=2), '```', '']
    return '\n'.join(lines)


def main():
    from . import engine as engine_module
    from .run_live import recorder, select_model
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('--initial', type=Path, help='The run\'s starting world, for the state-change tool')
    parser.add_argument('--focus', default='', help='Optional research question to emphasize')
    parser.add_argument('--graph-query', nargs=2, action='append', default=[], metavar=('OWNER', 'QUERY'),
                        help='Graphiti quick search to include as evidence (repeatable)')
    parser.add_argument('--api', default='http://127.0.0.1:18081')
    parser.add_argument('--out', type=Path, required=True, help='Fresh output directory')
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a fresh output directory')
    engine = Engine.load(args.checkpoint)
    initial = Engine.load(args.initial) if args.initial else None
    if args.graph_query:
        if 'cognition' not in engine.state['config']:
            parser.error('--graph-query needs a checkpoint with a cognition/view policy')
        engine.state['config'].setdefault('graphiti_namespace', 'analyst_' + sha256(args.checkpoint.read_bytes()).hexdigest())
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'source-hashes.json').write_text(json.dumps(
        {str(p.resolve()): sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}, indent=2) + '\n')
    model, models = select_model(args.api)
    (args.out / 'server-model.json').write_text(json.dumps(models, indent=2) + '\n')
    started, counts, original = time.monotonic(), {}, engine_module.request_json
    engine_module.request_json = recorder(original, args.out / 'requests.jsonl', counts)
    try:
        report = generate(engine, api=args.api, model=model, initial=initial, focus=args.focus,
                          graph_queries=[tuple(q) for q in args.graph_query])
    finally:
        engine_module.request_json = original
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.out / 'report.md').write_text(render(report))
    summary = {'checkpoint': str(args.checkpoint), 'model': model, 'requests': counts, 'evidence_items': len(report['evidence']),
               'sections': len(report['sections']), 'claims': {k: sum(c['type'] == k for s in report['sections'] for c in s['claims'])
                                                                for k in CLAIM_EVIDENCE},
               'seconds': round(time.monotonic() - started, 3)}
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
