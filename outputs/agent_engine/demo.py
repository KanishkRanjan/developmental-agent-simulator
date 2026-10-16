"""Connected engineering demonstration. No comparative accuracy benchmark.

python demo.py --out DIRECTORY [--sampled]
Optional --sampled reuses the existing adult population profile model and
requires the already-created profile-env (numpy/pandas/scipy).
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from engine import Engine, FACET_NAMES, sampled_profile


def expect_rejection(operation):
    try:
        operation()
    except (ValueError, KeyError):
        return
    raise AssertionError('Invalid operation was accepted')


def build(sampled=False):
    engine = Engine(seed=42)
    for key, name in [('alex', 'Alex'), ('bea', 'Bea'), ('cam', 'Cam'), ('maya', 'Maya')]:
        engine.entity(key, name)
    for index, key in enumerate(('alex', 'bea', 'cam')):
        traits = sampled_profile(42 + index) if sampled else dict.fromkeys(FACET_NAMES, 50)
        if not sampled:
            traits.update({'N1': 70 if key == 'alex' else 40, 'E3': 35 if key == 'alex' else 65})
        engine.materialize(key, traits, birth_day=0,
                           attachment={'caregiver_availability': 'uncertain'} if key == 'alex' else {})
    engine.caregiver('alex', 'maya')
    # A limited, supplied developmental history. The empty years are not simulated.
    engine.schedule('childhood-support', 3650, 'Maya helps Alex prepare a school presentation.', {
        'alex': {'text': 'Maya sat with me and helped me practice my presentation.', 'source': 'direct',
                 'kind': 'direct', 'valence': 0.6, 'arousal': 0.4, 'importance': 0.8,
                 'encountered': ['maya'], 'meaning': 'I can ask Maya for help.', 'stability_days': 300}})
    engine.advance(3650)
    # Later expansion of the caregiver retains the same identity and family constraint.
    engine.materialize('maya', dict.fromkeys(FACET_NAMES, 50), birth_day=-25 * 365.25)
    engine.develop('alex', {'C1': 55}, ['childhood-support'], 'confidence-growth-example')
    engine.advance(20 * 365.25)
    engine.goal('alex', 'presentation', 'Prepare and deliver a community project presentation.', priority=0.8, deadline=engine.day + 7)
    engine.situation_rule('alex', 'public-criticism', ['social', 'criticism'],
                          'May hesitate and ask what was meant before deciding how to respond.')
    day = engine.day
    engine.schedule('private-gossip', day, 'Bea and Cam privately discuss Alex; Alex is absent.', {
        'bea': {'text': 'I told Cam that Alex seemed nervous at rehearsal.', 'source': 'direct', 'encountered': ['cam'],
                'references': ['alex']},
        'cam': {'text': 'Bea said Alex seemed nervous at rehearsal.', 'source': 'Bea', 'kind': 'testimony',
                'references': ['alex'], 'provenance': 'bea-impression'}})
    engine.advance(day)
    private_context = engine.context('alex', 'How do you feel about the upcoming presentation?')
    assert 'private-gossip' not in {m['event'] for m in private_context['memories']}
    assert 'alex' not in engine.agent('cam')['relationships']
    engine.believe('cam', 'alex-nervous', 'Bea thinks Alex was nervous.', 0.5,
                   ['private-gossip'], 'cam-heard-impression')
    engine.schedule('heard-teasing', day + 1, 'All three meet. Alex hears Bea tease them about rehearsal.', {
        'alex': {'text': 'At lunch, Bea joked about me freezing during rehearsal. Cam was there.', 'source': 'direct',
                 'encountered': ['bea', 'cam'], 'valence': -0.6, 'arousal': 0.7, 'importance': 0.8,
                 'meaning': 'I felt exposed and was unsure whether Bea meant to hurt me.'},
        'bea': {'text': 'I joked about Alex freezing at rehearsal, with Alex and Cam present.', 'source': 'direct',
                'encountered': ['alex', 'cam']},
        'cam': {'text': 'I heard Bea joke about Alex freezing; Alex was listening.', 'source': 'direct',
                'encountered': ['alex', 'bea']}})
    engine.advance(day + 1)
    affected_context = engine.context('alex', 'Bea has just teased you at lunch. What do you do?', ['social', 'criticism'])
    assert affected_context['mood']['valence'] < 0
    assert engine.agent('alex')['relationships']['bea']['firsthand']
    engine.schedule('clarification', day + 2, 'Bea apologizes and clarifies the joke to Alex.', {
        'alex': {'text': 'Bea apologized and said the joke was meant affectionately.', 'source': 'Bea', 'kind': 'testimony',
                 'valence': 0.3, 'arousal': 0.2, 'provenance': 'bea-apology'},
        'bea': {'text': 'I apologized to Alex for the joke.', 'source': 'direct'}})
    engine.advance(day + 2)
    engine.revise('alex', 'heard-teasing', 'Bea says the joke was affectionate. I am less sure it was hostile.',
                  0.6, ['clarification'], 'reinterpret-teasing')
    # Scripted intention demonstrates controller wiring; this is not a model output.
    situation = 'You still want to prepare for your presentation. What is your next step?'
    context = engine.context('alex', situation)
    proposal = {'owner': 'alex', 'day': engine.day, 'context': context,
                'decision': {'action': 'Practice the opening with Maya.', 'speech': 'Could we rehearse the first minute?',
                             'goal_id': 'presentation', 'plan': ['Ask Maya for help', 'Practice the opening', 'Revise notes'],
                             'memory_ids': ['childhood-support']}}
    engine.commit_action('practice-intention', proposal)
    engine.schedule('practice-outcome', day + 3, 'Alex and Maya complete an hour of rehearsal.', {
        'alex': {'text': 'I practiced my opening with Maya for an hour.', 'source': 'direct',
                 'encountered': ['maya'], 'valence': 0.4, 'arousal': 0.3, 'importance': 0.6},
        'maya': {'text': 'I helped Alex rehearse their presentation opening.', 'source': 'direct', 'encountered': ['alex']}},
        outcomes={'alex': {'goals': {'presentation': {'progress': 0.4}}}},
        requires={'alive': ['alex', 'maya'], 'action': 'practice-intention'})
    engine.advance(day + 3)
    assert engine.agent('alex')['goals']['presentation']['progress'] == 0.4
    assert engine.state['actions'][0]['status'] == 'resolved'
    return engine, {'profile_source': 'fitted adult population sampler; child use is an assumption' if sampled else 'synthetic hand-set example',
                    'before_hearing': private_context, 'after_hearing': affected_context,
                    'after_rehearsal': engine.context('alex', situation),
                    'scripted_action': proposal['decision'], 'model_called': False}


def correctness_checks(engine):
    before = deepcopy(engine.state)
    for _ in range(10):
        engine.context('alex', 'Bea rehearsal Maya presentation')
    assert engine.state == before, 'Inspection changed agent state'
    expect_rejection(lambda: engine.schedule('heard-teasing', engine.day, 'duplicate', {}))
    expect_rejection(lambda: engine.advance(engine.day - 1))
    expect_rejection(lambda: engine.entity('maya', 'Someone else'))
    expect_rejection(lambda: engine.caregiver('maya', 'alex'))
    expect_rejection(lambda: engine.revise('alex', 'heard-teasing', 'unheard claim', 0.9, ['private-gossip'], 'bad-revision'))
    engine.recall('alex', 'heard-teasing', 'recall-once', rehearse=True, affect=True)
    first = deepcopy(engine.agent('alex')['memory_meta']['heard-teasing'])
    engine.recall('alex', 'heard-teasing', 'recall-again', rehearse=True, affect=True)
    assert first == engine.agent('alex')['memory_meta']['heard-teasing'], 'Immediate repeats reinforced memory'
    assert len([x for x in engine.agent('alex')['affect_events'] if x['memory'] == 'heard-teasing']) == 1
    expect_rejection(lambda: engine.recall('alex', 'heard-teasing', 'recall-once'))
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'checkpoint.json'
        engine.save(path)
        restored = Engine.load(path)
        assert restored.context('alex', 'presentation') == engine.context('alex', 'presentation')
        # Fixed event stream gives the same state after one skip or several.
        left, right = Engine.load(path), Engine.load(path)
        for world in (left, right):
            world.schedule('future', world.day + 2, 'Maya sends Alex a reminder.', {
                'alex': {'text': 'Maya reminded me of the presentation date.', 'source': 'Maya', 'kind': 'testimony'}})
        target = left.day + 10
        left.advance(target)
        right.advance(right.day + 1)
        right.advance(right.day + 2)
        right.advance(target)
        assert left.state == right.state and left.mood('alex') == right.mood('alex')
        right.schedule('death-example', right.day, 'Synthetic end-of-life fixture.', {}, outcomes={'alex': {'alive': False}})
        right.schedule('post-death', right.day + 1, 'Should not be delivered.', {
            'alex': {'text': 'Impossible live observation', 'source': 'direct'}})
        right.advance(right.day + 1)
        assert right.state['events'][-1]['status'] == 'ineligible'
        expect_rejection(lambda: right.context('alex', 'Act'))
    return {'passed': True, 'scope': 'software correctness only',
            'checks': ['private information isolation', 'heard teasing changes mood', 'firsthand encounter provenance',
                       'source-linked reinterpretation', 'action-linked outcome', 'read-only inspection',
                       'duplicate and backwards-time rejection', 'family consistency and cycle rejection',
                       'rehearsal and affect repetition gates', 'checkpoint round trip', 'time-skip consistency',
                       'no post-death live observations or actions']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path(__file__).with_name('example'))
    parser.add_argument('--sampled', action='store_true')
    args = parser.parse_args()
    engine, trace = build(args.sampled)
    checks = correctness_checks(engine)
    args.out.mkdir(parents=True, exist_ok=True)
    engine.save(args.out / 'world.json')
    (args.out / 'trace.json').write_text(json.dumps(trace, indent=2) + '\n')
    (args.out / 'engineering-checks.json').write_text(json.dumps(checks, indent=2) + '\n')
    print(json.dumps({'checkpoint': str(args.out / 'world.json'), **checks}, indent=2))


if __name__ == '__main__':
    main()
