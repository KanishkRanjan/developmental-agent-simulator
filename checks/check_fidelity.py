"""Source-fidelity and regression checks; no human-validity claim or live calls."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devsim.engine import Engine, FACET_NAMES
from devsim.personality import describe
from devsim.lifetime import Lifetime

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def reject(operation):
    try:
        operation()
    except ValueError:
        return
    raise AssertionError('Invalid operation accepted')


def main():
    traits = dict.fromkeys(FACET_NAMES, 50)
    traits.update(E2=95, E3=5)
    personality = describe(traits)
    assert len(personality['tendencies']) == 2
    assert 'enjoy frequent contact with groups' in ' '.join(personality['tendencies'])
    assert 'hold back or defer' in ' '.join(personality['tendencies'])
    assert '95' not in json.dumps(personality) and '5th' not in json.dumps(personality)
    balanced = describe(dict.fromkeys(FACET_NAMES, 50))
    assert 'balanced' in balanced['tendencies'][0]
    engine = Engine()
    for owner, recovery in [('a', 1.0), ('b', 2.0), ('c', 1.0)]:
        engine.entity(owner, owner.upper())
        engine.materialize(owner, traits, affect={'recovery_multiplier': recovery})
    engine.schedule('shared', 0, 'A and B experience a setback; C is absent.', {
        owner: {'text':'I struggled with the project today.', 'source':'direct', 'valence':-0.5, 'arousal':0.4}
        for owner in ('a', 'b')})
    engine.advance(2)
    assert abs(engine.mood('b')['valence']) > abs(engine.mood('a')['valence'])
    before = deepcopy(engine.state)
    reject(lambda: engine.schedule('wrong-birth',engine.day,'Invalid change.',{},facts={'a':{'birth_day':-100}}))
    engine.caregiver('a','c')
    reject(lambda: engine.schedule('wrong-family',engine.day,'Invalid change.',{},facts={'a':{'caregivers':['b']}}))
    before = deepcopy(engine.state)
    for _ in range(10):
        engine.context('a', 'the project')
    assert engine.state == before
    reject(lambda: engine.schedule('unheard', engine.day, 'Invalid cue', {
        'c': {'text':'I heard nothing.', 'source':'direct', 'cued_memories':['shared']}}))
    engine.schedule('reminder', engine.day, 'A hears B mention the project.', {
        'a': {'text':'B reminded me of struggling with the project.', 'source':'B', 'kind':'testimony', 'cued_memories':['shared']}})
    engine.advance(engine.day)
    assert engine.agent('a')['memory_meta']['shared']['stability_days'] > engine.agent('b')['memory_meta']['shared']['stability_days']
    assert not engine.agent('c')['memory_meta']
    # Model-reported use, rather than candidate lookup, creates the cognitive event.
    context = engine.context('b', 'project')
    engine.commit_action('used-memory', {'owner':'b', 'day':engine.day, 'context':context,
        'decision':{'action':'Think about the project.', 'speech':'', 'goal_id':None, 'plan':[], 'memory_ids':['shared']}})
    assert engine.agent('b')['recall_log'][-1]['memory'] == 'shared'
    with TemporaryDirectory() as directory:
        checkpoint=Path(directory)/'world.json'
        engine.save(checkpoint)
        restored=Engine.load(checkpoint)
        assert restored.world.observations==engine.world.observations, 'Rehearsal rewrote original encoding on load'
        assert Lifetime._world_from_state(engine.state).observations==engine.world.observations, 'Rollback cache changed original encoding'
    engine.advance(4)
    first_impulse = abs(engine.agent('b')['affect_events'][-1]['valence'])
    engine.recall('b', 'shared', 'later-recall', affect=True)
    assert abs(engine.agent('b')['affect_events'][-1]['valence']) < first_impulse
    original = deepcopy(engine.world.observations['a'])
    with patch('devsim.engine.request_json', return_value={'gists':[{'text':'I sometimes need help on projects.', 'confidence':0.6, 'evidence':['shared','reminder']}]}):
        assert engine.consolidate('a', batch_size=2) == 1
    assert original == engine.world.observations['a']
    assert any(b['kind']=='inferred_semantic_gist' for b in engine.agent('a')['beliefs'].values())
    assert all(m.get('archived') for m in engine.agent('a')['memory_meta'].values())
    captured = []
    def model_stub(system, context, api, model, max_tokens=600):
        captured.append(context)
        if 'new_observation' in context:
            return {'meaning':'I interpreted what I heard.', 'valence':0.1, 'arousal':0.1, 'importance':0.3, 'confidence':0.5}
        return {'action':'Pause.', 'speech':'', 'goal_id':None, 'plan':[], 'memory_ids':[]}
    with patch('devsim.engine.request_json', side_effect=model_stub):
        engine.propose('a','What next?')
        engine.appraise('a',{'text':'A reminder arrived.', 'source':'B', 'kind':'testimony'})
    assert len(captured)==2 and all('personality' in c and 'facets_percentiles' not in c for c in captured)
    engine.advance(10000)
    assert not engine.memories('c','project')
    assert not engine.memories('b','unrelated greeting'), 'Old details leaked without an adequate cue'
    assert engine.memories('b','struggled project today'), 'Specific cues should allow recovery of archived episodes'
    # Empty intervals require no opportunity ticks and no model calls.
    idle = Engine()
    idle.entity('a','A')
    idle.materialize('a',traits)
    policy = {'sampling':'event_driven','opportunities':[]}
    Lifetime(idle,policy,scripted=True).run(40*365.25)
    assert idle.state['runtime']['tick']==0
    result = {'passed':True,'scope':'engineering and implementation fidelity only',
        'checks':['facet-specific language without numeric personality table', 'distinct facets retained without broad-trait conflation',
                  'balanced profile fallback', 'read-only inspection', 'listener-only social reminders',
                  'actual model-cited memories trigger recall', 'recalled-affect habituation',
                  'original encoding stability preserved across resume and rollback',
                  'individual recovery parameters', 'source-linked gist without episode rewriting',
                  'events cannot silently rewrite committed birth or family identity',
                  'both action and appraisal use language compiler', 'aged details need retrieval cues',
                  'empty 40-year jump requires zero opportunity ticks']}
    RESULTS_DIR.joinpath('fidelity-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
