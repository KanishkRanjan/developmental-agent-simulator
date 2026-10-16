"""Small controller correctness check, with zero live-model calls."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from engine import Engine
from initialize_life import initialize
from lifetime import Lifetime


def main():
    policy = json.loads(Path(__file__).with_name('development-demo.json').read_text())
    with TemporaryDirectory() as directory:
        checkpoint = Path(directory) / 'world.json'
        whole, split = initialize(), initialize()
        Lifetime(whole, policy, scripted=True).run(8035.5)
        Lifetime(split, policy, scripted=True).run(4000, checkpoint)
        split = Engine.load(checkpoint)
        Lifetime(split, policy, scripted=True).run(8035.5)
        assert whole.state == split.state, 'Checkpoint/resume changed life history'
        assert len(whole.state['actions']) > 10
        assert all(a['status'] == 'resolved' for a in whole.state['actions'])
        assert whole.agent('alex')['goals']['community-presentation']['progress'] > 0
        for key, used in whole.state['runtime']['trait_budget'].items():
            assert used <= policy['max_trait_change_per_year'] + 1e-9
        assert whole.agent('alex')['facets']['C1'] != 45
        for event in whole.state['events']:
            age = event['day'] / 365.25
            if 'childhood-support' in event['id']:
                assert 5 <= age < 12
            if 'adolescent-project' in event['id']:
                assert 12 <= age < 18
            if 'adult-community-project' in event['id']:
                assert age >= 18
        # A real-provider failure rolls the tick back and saves the last valid state.
        fail_policy = deepcopy(policy)
        fail_policy.pop('situational_personality', None)  # Enabled-policy rollback is in check_situation.py.
        fail_policy['sampling'] = 'legacy_discrete'
        fail_policy['opportunities'] = [deepcopy(policy['opportunities'][0])]
        fail_policy['opportunities'][0]['min_age'] = 0
        fail_policy['opportunities'][0]['rate_per_year'] = 10000
        for option in fail_policy['opportunities'][0]['options']:
            option.pop('contact_responses',None)  # Two-agent resolution is checked separately.
        failed = initialize()
        controller = Lifetime(failed, fail_policy)
        before = deepcopy(failed.state)
        with patch.object(Engine, 'propose', side_effect=RuntimeError('fixture transport failure')):
            try:
                controller.run(90, checkpoint)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Transport failure swallowed')
        assert failed.state == before and Engine.load(checkpoint).state == before
        event_failed = initialize()
        event_policy = deepcopy(fail_policy)
        event_policy['sampling'] = 'event_driven'
        event_policy['opportunities'][0]['rate_per_year'] = 2
        event_controller = Lifetime(event_failed, event_policy)
        event_before = deepcopy(event_failed.state)
        next_day = min(x for x in event_failed.state['runtime']['next_opportunities'].values() if x is not None)
        with patch.object(Engine, 'propose', side_effect=RuntimeError('fixture event transport failure')):
            try:
                event_controller.run(next_day, checkpoint)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Event-driven transport failure swallowed')
        assert event_failed.state == event_before and Engine.load(checkpoint).state == event_before
        # Exercise the model decision/appraisal integration with a labeled stub.
        provider = initialize()
        def request_stub(system, context, api, model, max_tokens=600):
            if 'new_observation' in context:
                response = {'meaning':'This is how I interpret the observed outcome.', 'valence':0.2,
                            'arousal':0.2, 'importance':0.4, 'confidence':0.6}
                if 'caregiving' in context['new_observation']:
                    response['caregiving'] = {**context['new_observation']['caregiving'], 'responsiveness':.85, 'acceptance':.85}
                return response
            return {'action_id':context['available_actions'][0]['id'], 'action':context['available_actions'][0]['label'],
                    'speech':'', 'goal_id':None, 'plan':[], 'memory_ids':[]}
        with patch('engine.request_json', side_effect=request_stub):
            Lifetime(provider, fail_policy).run(90)
        assert len(provider.state['actions']) == 1
        assert provider.state['events'][0]['observations']['alex']['appraisal_policy'] == 'local_llm_unfitted'
        assert provider.state['runtime']['tick'] == 1
    result = {'passed': True, 'scope':'engineering only; scripted and stubbed providers',
              'checks':['automatic age-eligible events', 'action-dependent outcomes and goals',
                        'bounded automatic trait development', 'identical checkpoint/resume history',
                        'API failure rolls back entire tick', 'model appraisal/decision path with stub']}
    Path(__file__).with_name('lifetime-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
