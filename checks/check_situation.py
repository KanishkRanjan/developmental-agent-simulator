"""Situational personality checks with a labeled stub, never human validation."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devsim.engine import Engine, FACET_NAMES
from devsim.lifetime import Lifetime
from devsim.situation import DIMENSIONS, offsets, transition, validate_rules
from devsim import POLICY_DIR

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def stub(system, context, api, model, max_tokens=600):
    if context.get('task') == 'generate_situational_signatures':
        return {'rules': [{'id': f'rule-{i}', 'dimension': 'Adversity',
                           'trigger_context': 'My work is criticized in front of other people.',
                           'narrative_shift': 'Become quieter while deciding how to respond.',
                           'state_modifiers': {'E': -8, 'N': 4}} for i in range(5)]}
    if context.get('task') == 'construe_situation':
        return {'meaning': 'I perceive a difficult public evaluation.',
                'dimensions': {d: 1.0 if d == 'Adversity' else 0.0 for d in DIMENSIONS},
                'controllability': 0.4, 'active_rule_ids': ['rule-0']}
    if 'new_observation' in context:
        return {'meaning': 'I interpreted the outcome.', 'valence': 0.1, 'arousal': 0.2,
                'importance': 0.3, 'confidence': 0.5}
    return {'action': context['available_actions'][0]['label'], 'action_id': context['available_actions'][0]['id'],
            'speech': '', 'goal_id': None, 'plan': [], 'memory_ids': []}


def reject(operation):
    try:
        operation()
    except ValueError:
        return
    raise AssertionError('Invalid operation accepted')


def main():
    e = Engine()
    e.entity('a', 'A')
    e.materialize('a', dict.fromkeys(FACET_NAMES, 50))
    before = deepcopy(e.agent('a')['facets'])
    with patch('devsim.engine.request_json', side_effect=stub) as provider:
        e.generate_signatures('a')
        e.generate_signatures('a')
        assert provider.call_count == 1
        e.prepare_situation('a', 'My work is criticized publicly.', 's0', half_life_days=2)
    assert e.agent('a')['facets'] == before
    assert offsets(e.agent('a'), 0)['E3'] == -8
    assert offsets(e.agent('a'), 2)['E3'] == -4
    assert offsets(e.agent('a'), 2)['N1'] == 2
    context = e.context('a', 'My work is criticized publicly.')
    assert context['temporary_behavior']['tendencies'] and len(context['active_situation_rules']) == 1
    assert 'state_modifiers' not in json.dumps(context) and 'facets_percentiles' not in context
    saved = deepcopy(e.state)
    for _ in range(5):
        assert context == e.context('a', 'My work is criticized publicly.')
    assert e.state == saved
    perception = deepcopy(e.agent('a')['situational_state']['perception'])
    perception['active_rule_ids'] = ['invented']
    reject(lambda: transition(e.agent('a'), 0, perception, 2))
    reject(lambda: validate_rules([{'id': 'x', 'dimension': 'Adversity', 'trigger_context': 'x',
                                  'narrative_shift': 'x', 'state_modifiers': {'Q': 8}}]))
    with patch('devsim.engine.request_json', return_value=perception):
        assert e.prepare_situation('a', 'Bad classification.', 'bad') is None  # optional step: skipped, not fatal
    assert [x['step'] for x in e.state['runtime'].pop('skipped_model_steps')] == ['situation']
    if 'runtime' not in saved and not e.state['runtime']: del e.state['runtime']
    assert e.state == saved, 'Invalid construal partially mutated state'
    with TemporaryDirectory() as directory:
        checkpoint=Path(directory)/'stage.json'
        e.save(checkpoint)
        aging=Engine.load(checkpoint)
        aging.advance(18*365.25)
        with patch('devsim.engine.request_json',side_effect=stub) as generator:
            aging.generate_signatures('a')
            aging.generate_signatures('a')
            assert generator.call_count==1
        assert len(aging.agent('a')['caps_versions'])==1
        assert aging.agent('a')['caps_provenance']['stage']==2
    perception = deepcopy(e.agent('a')['situational_state']['perception'])
    for i in range(20):
        e.agent('a')['situational_state'] = transition(e.agent('a'), 0, perception, 2)
    assert offsets(e.agent('a'), 0)['E3'] == -20
    assert e.agent('a')['facets'] == before
    # One event in a real controller path using the stubbed API; then resume.
    policy = json.loads(POLICY_DIR.joinpath('development-demo.json').read_text())
    policy['opportunities'] = [deepcopy(policy['opportunities'][0])]
    opportunity = policy['opportunities'][0]
    opportunity.update(actor='a', min_age=0, rate_per_year=2,
                       options=[deepcopy(opportunity['options'][1])])
    opportunity['options'][0].pop('development_success', None)
    policy['situational_personality'] = {'recovery_half_life_days': 2}
    policy.pop('consolidation_batch_size', None)
    with TemporaryDirectory() as directory:
        clean = Engine()
        clean.entity('a', 'A')
        clean.materialize('a', before)
        controller = Lifetime(clean, policy)
        due = next(iter(clean.state['runtime']['next_opportunities'].values()))
        baseline = deepcopy(clean.state)
        # Failure after signature generation must roll back signatures, states and action.
        def failure(system, context, api, model, max_tokens=600):
            if context.get('task') == 'construe_situation':
                raise RuntimeError('fixture unavailable provider')
            return stub(system, context, api, model, max_tokens)
        checkpoint = Path(directory) / 'rollback.json'
        with patch('devsim.engine.request_json', side_effect=failure):
            try:
                controller.run(due, checkpoint)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Failed provider did not propagate')
        assert clean.state == baseline and Engine.load(checkpoint).state == baseline
        seen = []
        def capture(system, context, api, model, max_tokens=600):
            seen.append(deepcopy(context))
            return stub(system, context, api, model, max_tokens)
        # Rollback replaces state objects; recreate controller as an actual retry does.
        with patch('devsim.engine.request_json', side_effect=capture):
            Lifetime(clean, policy).run(due, checkpoint)
        action = next(c for c in seen if 'available_actions' in c)
        assert action['temporary_behavior']['tendencies']
        assert len(clean.state['actions']) == 1 and clean.state['actions'][0]['status'] == 'resolved'
        resumed = Engine.load(checkpoint)
        assert resumed.context('a', 'School.') == clean.context('a', 'School.')
        whole = Engine.load(checkpoint)
        resumed.advance(due + 1)
        resumed.advance(due + 2)
        whole.advance(due + 2)
        assert resumed.context('a', 'School.') == whole.context('a', 'School.'), 'Recovery depends on observation frequency'
    # Infant capability limits apply upstream of the action selector. Model
    # prose cannot introduce school/work/puzzle triggers through generated CAPS.
    from devsim import expression, situation
    child = Engine()
    child.entity('baby','Baby');child.materialize('baby',before,birth_day=0)
    expression.configure(child,{'age_appropriate_actions':True})
    raw = {'rules':[{'id':f'b{i}', 'trigger_id':key, 'reaction_id':'orient',
                     'state_modifiers':{'E':1}} for i,key in enumerate(situation.INFANT_TRIGGERS)]}
    with patch('devsim.engine.request_json',return_value=raw) as generator:
        rules = child.generate_signatures('baby')
        assert generator.call_args.args[1]['developmental_capabilities']['band']=='infant'
        assert all(r['trigger_context'] in [v[1] for v in situation.INFANT_TRIGGERS.values()] for r in rules)
        child.generate_signatures('baby');assert generator.call_count==1
    bad=deepcopy(raw);bad['rules'][0]['trigger_id']='solve-riddle'
    reject(lambda:situation.infant_rules(bad))
    bad=deepcopy(raw);bad['rules'][0]['narrative_shift']='Run a company'
    reject(lambda:situation.infant_rules(bad))
    saved_child=deepcopy(child.state)
    with patch('devsim.engine.request_json',return_value=bad):
        child.agent('baby')['caps_provenance']['capability_band']='legacy-unknown'
        retry_state=deepcopy(child.state)
        assert child.generate_signatures('baby')==retry_state['agents']['baby']['caps_rules']  # skipped: previous rules kept
        assert [x['step'] for x in child.state['runtime'].pop('skipped_model_steps')]==['signatures']
        if 'runtime' not in retry_state and not child.state['runtime']: del child.state['runtime']
        assert child.state==retry_state
    child.state=saved_child
    with TemporaryDirectory() as directory:
        file=Path(directory)/'child.json';child.save(file);child=Engine.load(file)
        for age,band in [(2,'early-childhood'),(5,'child')]:
            child.advance(age*365.25)
            with patch('devsim.engine.request_json',side_effect=stub) as generator:
                child.generate_signatures('baby');child.generate_signatures('baby')
                assert generator.call_count==1
            assert child.agent('baby')['caps_provenance']['capability_band']==band
        assert len(child.agent('baby')['caps_versions'])==2
        assert child.agent('baby')['facets']==before
    result = {'passed': True, 'scope': 'engineering only; stubbed API',
              'checks': ['generated signatures reused', 'age-stage refresh archives prior signatures',
                         'subjective situation and specific rule selection',
                         'temporary state separate from enduring traits', 'elapsed-time recovery and checkpoint equivalence',
                         'bounded simultaneous domain shifts', 'language-only personality and temporary behavior',
                         'context inspection is read-only', 'invalid output cannot partially mutate state',
                         'controller prepares state before action', 'failed construal rolls back entire event',
                         'infant signatures use bounded sensory trigger and nonverbal reaction catalogs',
                         'invalid infant competence is rejected before state mutation',
                         'capability transitions refresh at ages two and five after checkpoint restore']}
    RESULTS_DIR.joinpath('situation-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
