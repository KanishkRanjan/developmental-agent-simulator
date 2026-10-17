"""Continuity checks from the environment-v4 run review: lessons do not pile up or crowd out memories, and people
can tell they are repeating themselves. Synthetic; the model is stubbed."""
import json
from pathlib import Path
from unittest.mock import patch

from devsim.context_view import compact
from devsim.engine import Engine, FACET_NAMES, belief_view

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def world():
    e = Engine(3)
    for k in ('a', 'b'):
        e.entity(k, k.upper())
        e.materialize(k, dict.fromkeys(FACET_NAMES, 50))
    return e


def main():
    checks = []

    # Near-duplicate lessons reinforce one belief instead of piling up (lexical matcher: no semantic_matching here).
    e = world()
    lesson = 'When people go quiet in the cafeteria I feel uneasy and want to fill the silence.'
    replies = iter([{'gists': [{'text': lesson, 'confidence': .5, 'evidence': ['e0']}]},
                    {'gists': [{'text': lesson, 'confidence': .7, 'evidence': ['e1']}]},
                    {'gists': [{'text': 'B laughs at my jokes when we are alone.', 'confidence': .6, 'evidence': ['e2']}]}])
    for i in range(3):
        e.schedule(f'e{i}', .1 + i / 10, 'x', {'a': {'text': f'B said something {i}.', 'source': 'b'}})
        e.advance(.1 + i / 10)
        with patch('devsim.engine.request_json', return_value=next(replies)):
            assert e.consolidate('a', batch_size=1) == 1
    beliefs = e.agent('a')['beliefs']
    assert len(beliefs) == 2, beliefs
    merged = next(b for b in beliefs.values() if b['text'] == lesson)
    assert merged['evidence'] == ['e0', 'e1'] and merged['confidence'] == .7 and merged['reinforced'] == 1
    assert any(u['kind'] == 'belief' and u['previous'] for u in e.state['updates']), 'the merge keeps the earlier version'
    checks.append('a near-duplicate lesson reinforces the existing belief (evidence merged, history kept); a new lesson is added')

    # A prompt shows every explicit belief plus at most four inferred lessons, the most related to the situation first.
    many = {f'g{i}': {'text': f'Lesson {i} about the weather.', 'day': i, 'kind': 'inferred_semantic_gist', 'evidence': []}
            for i in range(10)}
    many['g0']['text'] = 'Lesson about the robotics club and the servo.'
    many['own'] = {'text': 'I believe Mum is fair.', 'day': 0, 'evidence': []}
    view = belief_view(many, 'You are at the robotics club.')
    shown = [k for k, b in view.items() if b.get('kind')]
    assert len(shown) == 4 and 'g0' in shown and 'own' in view and {'g9', 'g8', 'g7'} <= set(shown)
    assert belief_view({k: many[k] for k in ('g1', 'own')}, 'x') == {k: many[k] for k in ('g1', 'own')}
    checks.append('a prompt shows every explicit belief and at most four inferred lessons: situation-related first, then the newest')

    # Over budget, beliefs are trimmed to two before memories are cut.
    context = {'situation': 'Now.', 'memories': [{'event': str(i), 'text': 'An event. ' * 40} for i in range(6)],
               'beliefs': {str(i): {'text': 'A lesson. ' * 40} for i in range(6)}}
    size = len(json.dumps(context).encode())
    view = compact(json.loads(json.dumps(context)), size - 1500)
    assert len(view['memories']) == 6 and len(view['beliefs']) < 6
    for budget in range(size - 4000, size, 250):
        view = compact(json.loads(json.dumps(context)), budget)
        assert len(view['memories']) == 6 or len(view['beliefs']) <= 2, budget
    assert len(compact(json.loads(json.dumps(context)), size - 3000)['memories']) < 6
    checks.append('over the byte budget, inferred interpretations (beliefs) are trimmed to two before any memory is cut')

    seen = []
    e.schedule('e9', .9, 'x', {'a': {'text': 'B waved.', 'source': 'b'}})
    e.advance(.9)
    with patch('devsim.engine.request_json', side_effect=lambda s, *a, **k: seen.append(s) or {'gists': []}):
        e.consolidate('a', batch_size=1)
    assert 'Do not describe your own speaking habits' in seen[0]
    checks.append('consolidation asks for lessons about people and events, not scripts of the agent\'s own conversational habits')

    # A person sees the gist of their own words from the previous session, even if sleep dropped those turns.
    from devsim import household
    e = world()
    opener = 'Wow, the silence is so loud I can hear it. Is anyone going to say something?'
    e.schedule('@conversation:monday:0', .4, 'x', {'a': {'text': 'I said: ' + opener, 'source': 'self'},
                                                     'b': {'text': 'A said: ' + opener, 'source': 'a'}})
    e.advance(.4)
    e.state['actions'].append({'id': '@conversation:monday:0:action', 'owner': 'a', 'day': .4, 'status': 'resolved',
                               'decision': {'speech': opener}})
    e.agent('a')['memory_meta']['@conversation:monday:0']['tier'] = 'dropped'
    lunch = {'room': 'cafe', 'topic': 'Lunch'}
    e.state['runtime'] = {'conversations': {'monday': {'status': 'closed', 'active': [], 'spec': lunch},
                                            'tuesday': {'status': 'open', 'active': ['a', 'b'], 'spec': lunch}}}
    e.advance(1.4)
    then = household.conversation_memory(e, 'a')['previous_session']
    assert then == {'days_ago': 1.0, 'what_you_said_then': ['Wow, the silence is so loud I can hear it.']}, then
    assert 'what_you_said_then' not in household.conversation_memory(e, 'b')['previous_session']
    checks.append('the previous same-thread session shows the gist of the person\'s own words, even when sleep dropped those turns')

    # A daily opener that reuses a six-word run is caught as a repeat even when overall similarity is low.
    hit = e.repeated_speech('a', 'Wow, the silence is so loud it is echoing in here. Who wants to talk about the quiz?')
    assert hit and hit['repeated_words'] == 'wow the silence is so loud'
    assert e.repeated_speech('a', 'Did anyone finish the maths homework last night, or is that just me?') is None
    checks.append('a reused run of six words (three of them content words) counts as repeating oneself; ordinary new lines do not')

    result = {'passed': True, 'scope': 'synthetic engineering checks; thresholds are design defaults measured on one run',
              'checks': checks}
    RESULTS_DIR.joinpath('continuity-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
