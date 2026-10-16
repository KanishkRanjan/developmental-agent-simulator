"""Developmental mechanism checks; synthetic engineering evidence only."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devsim.engine import Engine, FACET_NAMES
from devsim.development import attachment_models
from devsim.lifetime import Lifetime

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def reject(operation):
    try:
        operation()
    except ValueError:
        return
    raise AssertionError('Invalid operation accepted')


def initial():
    e = Engine()
    for key in ('child', 'sibling', 'caregiver'):
        e.entity(key, key)
        e.materialize(key, dict.fromkeys(FACET_NAMES, 50), birth_day=-9000 if key == 'caregiver' else 0)
    for owner in ('child', 'sibling'):
        e.caregiver(owner, 'caregiver')
    return e


def received(responsiveness=1, acceptance=1):
    return {'text': 'We tried the task together but did not solve it; I was listened to warmly.',
            'source': 'direct', 'kind': 'direct', 'valence': -.4, 'encountered': ['caregiver'],
            'caregiving': {'caregiver': 'caregiver', 'responsiveness': responsiveness, 'acceptance': acceptance}}


def main():
    e = initial()
    for day in range(3):
        e.schedule(f'care-{day}', day, 'Warm response despite task failure.', {'child': received()})
    e.advance(3)
    model = attachment_models(e.agent('child'), e.day)['caregiver']
    assert model['prototype']['anxiety'] < .4 and model['prototype']['avoidance'] < .4
    assert not attachment_models(e.agent('sibling'), e.day), 'Uninvolved sibling learned a private experience'
    text = json.dumps(e.context('child', 'Ask for help?')['attachment_expectations'])
    assert 'Usually expects' in text
    bad = received()
    bad.update(kind='testimony', encountered=[], references=['caregiver'])
    reject(lambda: e.schedule('hearsay', e.day, 'Someone claims a caregiver was unkind.', {'child': bad}))
    bad = received()
    bad['caregiving']['caregiver'] = 'sibling'
    reject(lambda: e.schedule('noncaregiver', e.day, 'Wrong identity.', {'child': bad}))
    # Repeated records in one day cannot exceed one day of learning weight.
    one, many = initial(), initial()
    one.schedule('one', 0, 'Interaction.', {'child': received()})
    one.advance(0)
    for i in range(30):
        many.schedule(f'repeat-{i}', 0, 'Same-day interaction.', {'child': received()})
    many.advance(0)
    assert attachment_models(one.agent('child'), 0)['caregiver']['prototype'] == attachment_models(many.agent('child'), 0)['caregiver']['prototype']
    early = deepcopy(model['prototype'])
    e.advance(20 * 365.25)
    e.schedule('later-rejection', e.day, 'Direct adult interaction.', {'child': received(0, 0)})
    e.advance(e.day)
    later = attachment_models(e.agent('child'), e.day)['caregiver']
    assert later['prototype'] == early and later['current']['anxiety'] > early['anxiety']
    e.advance(e.day + 360)
    assert attachment_models(e.agent('child'), e.day)['caregiver']['current']['anxiety'] < later['current']['anxiety']
    # State exposure affects traits only after acted-on, received consequences on independent days.
    e = initial()
    curves = {'C': [[0, 0], [18, 0], [40, 2]]}
    e.configure_development('child', curves)
    e.agent('child')['caps_rules'] = [{'id': 'persist', 'dimension': 'Duty',
        'trigger_context': 'A task needs sustained effort.', 'narrative_shift': 'Work more persistently.',
        'state_modifiers': {'C': 8}}]
    perception = {'meaning': 'A task needs sustained effort.', 'dimensions': {
        d: 1 if d == 'Duty' else 0 for d in ('Duty','Intellect','Adversity','Mating','Positivity','Negativity','Deception','Sociality')},
        'controllability': .8, 'active_rule_ids': ['persist']}
    for day in range(20):
        e.advance(day)
        with patch('devsim.engine.request_json', return_value=perception):
            e.prepare_situation('child', 'A task needs sustained effort.', f'state-{day}')
        context = e.context('child', 'A task needs sustained effort.')
        action_id, event_id = f'action-{day}', f'outcome-{day}'
        proposal = {'owner': 'child', 'day': e.day, 'context': context,
                    'decision': {'action': 'Work on the task.', 'speech': '', 'goal_id': None, 'plan': [], 'memory_ids': []}}
        e.commit_action(action_id, proposal)
        if day == 0:
            reject(lambda: e.crystallize('child', action_id, event_id))
        e.schedule(event_id, e.day, 'An attempt was made.', {'child': {'text': 'I worked on the task.', 'source': 'direct'}}, requires={'action': action_id})
        e.advance(e.day)
        changed = e.crystallize('child', action_id, event_id)
        if day < 2:
            assert not changed and e.agent('child')['facets']['C1'] == 50
        reject(lambda: e.crystallize('child', action_id, event_id))
    assert 50 < e.agent('child')['facets']['C1'] <= 50.5 + 1e-9
    assert all(used <= .5 + 1e-9 for used in e.agent('child')['crystallization_budget'].values())
    state = deepcopy(e.state)
    for _ in range(5):
        e.context('child', 'Read only.')
    assert e.state == state
    with TemporaryDirectory() as directory:
        checkpoint = Path(directory) / 'state.json'
        e.save(checkpoint)
        whole, split = Engine.load(checkpoint), Engine.load(checkpoint)
        whole.advance(40 * 365.25)
        split.advance(20 * 365.25)
        split.save(checkpoint)
        split = Engine.load(checkpoint)
        split.advance(40 * 365.25)
        assert whole.state == split.state, 'Age curves changed with checkpoint frequency'
        assert abs(whole.agent('child')['facets']['C1'] - 52.5) < 1e-9
        # Death freezes maturation instead of aging the record afterwards.
        split.schedule('death', split.day, 'End of synthetic life.', {}, outcomes={'child': {'alive': False}})
        split.advance(split.day)
        frozen = dict(split.agent('child')['facets'])
        split.advance(80 * 365.25)
        assert split.agent('child')['facets'] == frozen
    # Exercise caregiver appraisal and controller learning using a labeled stub.
    e = initial()
    option = {'id': 'ask', 'label': 'Ask the caregiver for help.', 'contact': 'caregiver',
              'contact_text': 'I listened warmly but the task remained unsolved.',
              'caregiving': {'responsiveness': .9, 'acceptance': .9},
              'success_probability': 0, 'success_text': 'Solved.',
              'failure_text': received()['text'], 'valence_success': .5, 'valence_failure': -.3}
    policy = {'sampling':'event_driven', 'development': {'maturation': curves,
              'crystallization': {'rate': .005, 'minimum_days': 3, 'max_change_per_year': .5}},
              'opportunities': [{'id':'support','actor':'child','min_age':0,'max_age':18,'rate_per_year':4,
                                 'situation':'A task is difficult.','options':[option]}]}
    controller = Lifetime(e, policy)
    due = next(iter(e.state['runtime']['next_opportunities'].values()))
    def stub(system, context, api, model, max_tokens=600):
        if 'new_observation' in context:
            assert not set(context['new_observation']) & {'valence','arousal','importance','confidence','meaning'}
            result = {'meaning':'I was supported even though the task remained unsolved.', 'valence': -.2,
                      'arousal': .3, 'importance': .6, 'confidence': .7}
            if 'caregiving' in context['new_observation']:
                assert set(context['new_observation']['caregiving']) == {'caregiver'}
                result['caregiving'] = {'caregiver':'caregiver','responsiveness':.9,'acceptance':.9}
            return result
        return {'action_id':'ask','action':option['label'],'speech':'','goal_id':None,'plan':[],'memory_ids':[]}
    with patch('devsim.engine.request_json', side_effect=stub):
        controller.run(due)
    assert len(e.agent('child')['caregiving_experiences']) == 1
    assert e.state['actions'][0]['status'] == 'resolved'
    assert not e.agent('caregiver').get('caregiving_experiences')
    result = {'passed':True, 'scope':'synthetic engineering checks, not psychological validation',
        'checks':['received caregiver evidence only', 'task failure is not caregiver rejection',
                  'same-day learning weight bounded', 'early anchor with recovering adult working state',
                  'independent enacted experiences required for crystallization', 'intention alone cannot change traits',
                  'annual and daily trait-change bounds', 'maturation and learned changes remain separate',
                  'elapsed-age maturation invariant across checkpoints', 'no post-death maturation',
                  'read-only context', 'actual controller/appraisal wiring with stub']}
    RESULTS_DIR.joinpath('development-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
