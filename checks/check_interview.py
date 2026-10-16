"""Diagnostic and in-world interview checks; synthetic model stubs."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devsim.engine import Engine, FACET_NAMES
from devsim.interview import ACCOUNT_POLICY, diagnostic, in_world
from devsim.lifetime import Lifetime

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def fixture(household=False):
    e = Engine(seed=91)
    for p, age in [('a', 16), ('b', 41), ('baby', 1)]:
        e.entity(p, p.upper(), {'birth_day': -age * 365.25})
        e.materialize(p, dict.fromkeys(FACET_NAMES, 50), birth_day=-age * 365.25)
        e.schedule('private-' + p, 0, 'A private thought.', {p: {'text': f'PRIVATE_{p} school worry', 'source': 'self',
                                                                  'kind': 'internal', 'importance': .8}})
    e.entity('r', 'Researcher')
    e.advance(.5)
    policy = {'sampling': 'event_driven', 'opportunities': [], 'expression': {'age_appropriate_actions': True}}
    if household:
        policy['household'] = {'rooms': {'kitchen': {'label': 'the kitchen'}},
                               'locations': {p: 'kitchen' for p in ('a', 'b', 'baby')},
                               'routines': {'a': {'available_hours': [[7, 22]], 'response_minutes': [1, 1]}}}
    return e, policy


def snapshot(e):
    return json.dumps(e.state, sort_keys=True), sum(len(v) for v in e.world.observations.values())


def reject(call):
    try:
        call()
    except (ValueError, RuntimeError):
        return
    raise AssertionError('Invalid operation accepted')


def stub(system, context, api, model, max_tokens=600):
    owner = context['identity']['id']
    serialized = json.dumps(context)
    assert all(f'PRIVATE_{p}' not in serialized for p in ('a', 'b', 'baby') if p != owner)
    if context.get('task') == 'diagnostic_interview':
        return {'answer': 'I keep worrying about school.', 'confidence': .7,
                'memory_ids': [context['memories'][0]['event']] if context['memories'] else []}
    if 'new_observation' in context:
        return {'meaning': 'Being questioned feels uncomfortable.', 'valence': -.4, 'arousal': .5,
                'importance': .7, 'confidence': .6}
    return {'action_id': 'answer', 'action': 'Answer honestly.', 'speech': 'School has been hard lately.',
            'goal_id': None, 'plan': [], 'memory_ids': []}


def main():
    checks = []
    e, policy = fixture()
    before = snapshot(e)
    with patch('devsim.engine.request_json', side_effect=stub):
        records = diagnostic(e, ['a', 'b'], ['How is school?', 'What worries you?'], api='stub', model='stub')
    assert len(records) == 4 and {(r['owner'], r['question']) for r in records} == {
        (p, q) for p in 'ab' for q in ('How is school?', 'What worries you?')}
    assert all(r['mode'] == 'diagnostic' and r['policy'] == ACCOUNT_POLICY for r in records)
    assert snapshot(e) == before and not e.state['updates'] and not e.agent('a')['recall_log']
    checks += ['batch diagnostic interview answers every agent-question pair from private context only',
               'diagnostic interview leaves world state, observations, recall and mood unchanged']

    bad = lambda *args, **kw: {'answer': 'x', 'confidence': .5, 'memory_ids': ['private-b']}
    with patch('devsim.engine.request_json', side_effect=bad):
        reject(lambda: diagnostic(e, ['a'], ['Anything?'], api='stub', model='stub'))
    assert snapshot(e) == before
    checks += ['diagnostic answer citing another agent\'s memory is rejected without state change']

    c = Lifetime(e, policy)
    reject(lambda: diagnostic(e, ['baby'], ['Hello?'], api='stub', model='stub'))
    reject(lambda: in_world(c, 'baby', 'r', ['Hello?'], 'iv-baby'))
    reject(lambda: diagnostic(e, ['a', 'a'], ['Hello?'], api='stub', model='stub'))
    reject(lambda: diagnostic(e, ['a'], [' '], api='stub', model='stub'))
    reject(lambda: in_world(c, 'a', 'a', ['Hello?'], 'iv-self'))
    reject(lambda: in_world(c, 'a', 'nobody', ['Hello?'], 'iv-unknown'))
    checks += ['infants, self-interviews, unknown interviewers, duplicate agents and empty questions are rejected']

    facts = deepcopy(e.state['entities'])
    with patch('devsim.engine.request_json', side_effect=stub):
        result = in_world(c, 'a', 'r', ['How is school?', 'Why do you worry?'], 'iv1')
    assert result['mode'] == 'in_world' and result['policy'] == ACCOUNT_POLICY and len(result['turns']) == 2
    meta = e.agent('a')['memory_meta']
    for turn in result['turns']:
        assert meta[turn['question_event']]['kind'] == 'direct' and turn['reply_event'] in meta
        assert turn['question_event'] not in e.agent('b')['memory_meta']
        action = next(x for x in e.state['actions'] if x['id'] == turn['action'])
        assert action['status'] == 'resolved' and action['outcome_event'] == turn['reply_event']
    assert meta['@interview:iv1:0:question']['meaning'] == 'Being questioned feels uncomfortable.'
    assert e.mood('a')['valence'] < 0 and e.mood('b')['valence'] == 0
    assert e.agent('a')['relationships']['r']['firsthand']
    assert e.state['entities'] == facts
    assert any(m['event'] == '@interview:iv1:0:question' for m in e.context('a', 'Researcher asked me about school')['memories'])
    checks += ['in-world questions become appraised received events for the interviewee only',
               'in-world replies are committed actions resolved by the observed reply',
               'in-world interview leaves mood and a firsthand acquaintance but no world facts',
               'later decisions can retrieve the interview memory']
    reject(lambda: in_world(c, 'a', 'r', ['Again?'], 'iv1'))
    checks += ['interview ids cannot be reused']

    with patch('devsim.engine.request_json', side_effect=stub):
        peer = in_world(c, 'a', 'b', ['Are you okay?'], 'iv-peer')
    heard = e.agent('b')['memory_meta'][peer['turns'][0]['reply_event']]
    assert heard['encountered'] == ['a'] and peer['turns'][0]['question_event'] in e.agent('b')['memory_meta']
    checks += ['a materialized interviewer hears the reply as a direct observation of the speaker']

    calls = []
    def fail_second(system, context, api, model, max_tokens=600):
        calls.append(context)
        if 'available_actions' in context and sum('available_actions' in x for x in calls) == 2:
            raise RuntimeError('fixture transport failure')
        return stub(system, context, api, model, max_tokens)
    before = snapshot(e)
    with patch('devsim.engine.request_json', side_effect=fail_second):
        reject(lambda: in_world(c, 'a', 'r', ['First?', 'Second?'], 'iv-fail'))
    assert snapshot(e) == before
    with patch('devsim.engine.request_json', side_effect=stub):
        in_world(c, 'a', 'r', ['First?', 'Second?'], 'iv-fail')
    checks += ['a failure on a later question rolls back the whole interview; the id stays usable']

    with patch('devsim.engine.request_json', side_effect=stub):
        later = diagnostic(e, ['a'], ['What did the researcher ask you?'], api='stub', model='stub')
    assert any(m['event'].startswith('@interview:iv1') for m in later[0]['context']['memories'])
    checks += ['a diagnostic interview after an in-world interview sees it as received memory']

    with TemporaryDirectory() as directory:
        root = Path(directory)
        e.save(root / 'world.json'); e.save(root / 'world.sqlite')
        restored = [Engine.load(root / 'world.json'), Engine.load(root / 'world.sqlite')]
        assert all(r.state == e.state and r.mood('a') == e.mood('a') for r in restored)
        Lifetime(restored[0], policy).run(1)
        assert restored[0].day == 1
    checks += ['interviewed checkpoints restore identically from JSON and SQLite and resume under the same policy']

    h, house = fixture(household=True)
    scripted = Lifetime(h, house, scripted=True)
    h.state['day'] = h.state['runtime']['current_day'] = 3.1
    reject(lambda: in_world(scripted, 'a', 'r', ['Up late?'], 'iv-night'))
    h.state['day'] = h.state['runtime']['current_day'] = 3.5
    done = in_world(scripted, 'a', 'r', ['Lunch?'], 'iv-noon')
    assert done['provider'] == 'scripted_engineering_fixture' and h.state['actions'][-1]['status'] == 'resolved'
    checks += ['household availability gates in-world interviews; scripted provider needs no model']

    result = {'passed': True, 'scope': 'engineering only; stubbed transport', 'checks': checks}
    RESULTS_DIR.joinpath('interview-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
