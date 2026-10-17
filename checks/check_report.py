"""Report agent checks: read-only executed tools, typed citation discipline, separated rendering; stubbed model."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from checks.check_author import SPEC
from devsim.author import compile_scenario
from devsim.interview import state_digest
from devsim.lifetime import Lifetime
from devsim.report import gather, generate, outline, render, section


def world():
    initial, policy, _ = compile_scenario(deepcopy(SPEC), dry_run=False)
    engine = deepcopy(initial)
    policy['cognition']['graphiti_retrieval'] = False  # scripted fixture: no graph outbox
    Lifetime(engine, policy, scripted=True).run(SPEC['duration_years'] * 365.25)
    return initial, engine


def stub(system, context, api, model, max_tokens=600):
    ev = context['evidence']
    if context['task'] == 'report_outline':
        return {'title': 'Fixture report', 'sections': [
            {'title': 'What happened', 'question': 'What did the controller resolve?', 'evidence_ids': [e['id'] for e in ev][:6]},
            {'title': 'Meanings', 'question': 'How did people read it?',
             'evidence_ids': [e['id'] for e in ev if e['category'] == 'agent_interpretation'][:3]
                             + [e['id'] for e in ev if e['category'] == 'observed_outcome'][:1]}]}
    observed = [e['id'] for e in ev if e['category'] == 'observed_outcome']
    meant = [e['id'] for e in ev if e['category'] == 'agent_interpretation']
    claims = [{'type': 'researcher_inference', 'text': 'A pattern across the cited items.', 'evidence_ids': [ev[0]['id']]}]
    if observed:
        claims.append({'type': 'observed', 'text': 'The controller resolved this.', 'evidence_ids': observed[:2]})
    if meant:
        claims.append({'type': 'agent_interpretation', 'text': 'Sam read it this way.', 'evidence_ids': meant[:1] + observed[:1]})
    return {'claims': claims, 'open_questions': ['What would change with another seed?']}


def main():
    checks = []
    initial, engine = world()
    engine.agent('sam')['memory_meta']['scenario-background-sam-0']['meaning'] = 'An appraised authored line, as in live runs.'
    before = state_digest(engine)
    items, log = gather(engine, initial)
    assert state_digest(engine) == before and gather(engine, initial) == (items, log)
    ids = {e['id'] for e in engine.state['events']} | {a['id'] for a in engine.state['actions']}
    assert all(set(i['event_ids']) <= ids for i in items) and [i['id'] for i in items] == [f'E{n + 1}' for n in range(len(items))]
    tools = {i['tool']: i['category'] for i in items}
    assert tools == {'controller_events': 'observed_outcome', 'resolved_actions': 'observed_outcome',
                     'utterances': 'observed_outcome', 'checkpoint_memory_view': 'agent_interpretation',
                     'state_changes': 'observed_outcome'}, tools
    assert all('unverified claim' in i['text'] for i in items if i['tool'] == 'utterances')
    assert not any(e.startswith('scenario-background-') for i in items if i['tool'] == 'checkpoint_memory_view' for e in i['event_ids'])
    flyer = next(i for i in items if i['event_ids'] == ['scenario-flyer'])
    assert flyer['recipients'] == ['sam'] and flyer['day'] == 14
    sam = next(i for i in items if i['tool'] == 'state_changes' and i['owner'] == 'sam')
    assert 'goal friends' in sam['text'] and 'mood at day' in sam['text']
    forgot = deepcopy(engine)
    shown = [i['event_ids'][0] for i in items if i['tool'] == 'checkpoint_memory_view']
    assert shown
    forgot.agent(next(i['owner'] for i in items if i['tool'] == 'checkpoint_memory_view'))['memory_meta'][shown[0]]['tier'] = 'dropped'
    assert shown[0] not in [i['event_ids'][0] for i in gather(forgot, initial)[0] if i['tool'] == 'checkpoint_memory_view']
    checks.append('a forgotten (dropped, merged or unattended) memory is never reported as the person\'s current interpretation')
    checks += ['tools are deterministic, read-only and cite only existing event and action ids',
               'controller events, resolved actions, utterances and state changes are observed outcomes; memory meanings are agent interpretations',
               'utterances are labeled unverified; authored background is not reported as an interpretation; recipients are listed']

    def returns(*answers):
        calls = iter(answers)
        return lambda system, context, api, model, max_tokens=600: next(calls)
    good = {'title': 'T', 'sections': [{'title': 'A', 'question': 'Q?', 'evidence_ids': ['E1']},
                                       {'title': 'B', 'question': 'Q?', 'evidence_ids': ['E2']}]}
    unknown = deepcopy(good); unknown['sections'][0]['evidence_ids'] = ['E999']
    with patch('devsim.engine.request_json', side_effect=returns(unknown, good)):
        assert outline(items, '', api='stub', model='stub') == good
    with patch('devsim.engine.request_json', side_effect=returns(unknown, unknown, unknown)):
        try:
            outline(items, '', api='stub', model='stub')
            raise AssertionError('outline citing unknown evidence accepted')
        except ValueError:
            pass
    checks.append('an outline citing unknown evidence is repaired, and fails after two repairs')

    meant = next(i['id'] for i in items if i['category'] == 'agent_interpretation')
    seen = next(i['id'] for i in items if i['category'] == 'observed_outcome')
    spec = {'title': 'S', 'question': 'Q?', 'evidence_ids': [meant, seen]}
    bad = [[{'type': 'observed', 'text': 'x', 'evidence_ids': [meant]}],
           [{'type': 'agent_interpretation', 'text': 'x', 'evidence_ids': [seen]}],
           [{'type': 'researcher_inference', 'text': 'x', 'evidence_ids': ['E1' if 'E1' not in spec['evidence_ids'] else 'E2']}],
           [{'type': 'speculation', 'text': 'x', 'evidence_ids': [seen]}],
           [{'type': 'observed', 'text': 'x', 'evidence_ids': []}]]
    for claims in bad:
        with patch('devsim.engine.request_json', side_effect=returns(*[{'claims': claims}] * 3)):
            try:
                section(spec, items, api='stub', model='stub')
                raise AssertionError(f'invalid claims accepted: {claims}')
            except ValueError:
                pass
    ok = {'claims': [{'type': 'researcher_inference', 'text': 'x', 'evidence_ids': [meant, seen]}], 'open_questions': []}
    with patch('devsim.engine.request_json', side_effect=returns(ok)):
        assert section(spec, items, api='stub', model='stub')['claims'] == ok['claims']
    checks += ['observed claims cite only observed outcomes; agent-interpretation claims need an interpretation item',
               'claims citing evidence outside their section, untyped claims and uncited claims are rejected']

    with patch('devsim.engine.request_json', side_effect=stub):
        report = generate(engine, api='stub', model='stub', initial=initial, focus='first weeks')
    assert state_digest(engine) == before and report['world_state_sha256'] == before
    text = render(report)
    body, appendix = text.split('## Executed tool results')
    assert all(f'| {i["id"]} |' in appendix for i in items) and '| E' not in body
    claim_lines = [line for line in body.splitlines() if line.startswith('- **')]
    assert claim_lines and all(line.startswith(('- **Observed:**', '- **Agent interpretation:**', '- **Researcher inference:**'))
                               for line in claim_lines)
    assert all(c['text'] not in appendix for s in report['sections'] for c in s['claims'])
    checks += ['a full report leaves the checkpoint unchanged',
               'rendering labels every model claim by type and keeps executed tool results in a separate appendix']

    engine.state['config'].setdefault('cognition', {})
    with patch('devsim.graph_tools.inspect', side_effect=RuntimeError('graph down')):
        more, more_log = gather(engine, initial, [('sam', 'school')])
    assert more == items and more_log[-1]['error'] == 'graph down'
    checks.append('an unavailable graph search is logged as a tool error, never turned into evidence')

    result = {'passed': True, 'scope': 'engineering only; stubbed transport', 'checks': checks}
    Path(__file__).with_name('results').joinpath('report-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
