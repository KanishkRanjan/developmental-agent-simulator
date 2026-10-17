"""Randomized invariant checks: 500 seeded synthetic worlds mixing mood kernels, sleep (with dials and routines), attention,
cognition and caregiver links. No model server. Found the coarsened-text-after-load bug (17 October)."""
import json, random, sys, tempfile, traceback
from math import isfinite
from pathlib import Path
from devsim.engine import Engine, FACET_NAMES
from devsim import attention, sleep, cognition
from devsim.sleep import HIDDEN

WORDS = 'rain bus exam lunch phone kite fight sorry money mum dad fire party homework school robot'.split()


def run(seed):
    rng = random.Random(seed)
    e = Engine(seed, rng.choice(['power_law', 'average', 'exponential']))
    people = [f'p{i}' for i in range(rng.randint(2, 5))]
    for p in people:
        e.entity(p, p.upper())
        e.materialize(p, {k: rng.uniform(5, 95) for k in FACET_NAMES})
    features = []
    if rng.random() < .6:
        sleep.configure(e); features.append('sleep')
        for p in people:
            if rng.random() < .5:
                sleep.set_dials(e, p, dysregulation=rng.random(), threat_sensitivity=rng.random(),
                                mood_baseline_shift=rng.uniform(-1, 1), reality_testing=rng.random())
        if rng.random() < .5:
            e.state['runtime'] = {}; e.state['household'] = {'locations': {}}
            e.state['config']['household'] = {'rooms': {}, 'routines': {p: {'available_hours': [[rng.randint(5, 9), rng.randint(17, 23)]]} for p in people}}
    if rng.random() < .6:
        attention.configure(e, {'felt_ignored': rng.random() < .5}); features.append('attention')
    if rng.random() < .5:
        cognition.configure(e, {'semantic_matching': False, 'verbatim_days': 1, 'recall_beta': 2}); features.append('cognition')
    if rng.random() < .3:
        e.caregiver(people[1], people[0])
    day = .2
    for n in range(rng.randint(5, 120)):
        day += rng.expovariate(1 / rng.choice([.01, .1, .5, 3]))
        speaker = rng.choice(people)
        listeners = rng.sample(people, rng.randint(1, len(people)))
        key = rng.choice(['@conversation:c%d:%d' % (rng.randint(0, 3), n), 'ev%d' % n, '@call:%d:x%d' % (rng.randint(0, 2), n)])
        obs = {}
        for p in listeners:
            o = {'text': f'{speaker.upper()} said: ' + ' '.join(rng.sample(WORDS, 4)) + ('?' if rng.random() < .2 else '.'),
                 'source': 'self' if p == speaker else speaker, 'kind': 'direct',
                 'valence': rng.uniform(-1, 1), 'arousal': rng.random(), 'importance': rng.random()}
            if p != speaker and rng.random() < .5:
                o['encountered'] = [speaker]
            if p != speaker and rng.random() < .2:
                o['addressed'] = [p]
            obs[p] = o
        e.schedule(key, day, 'x', obs)
        if rng.random() < .3:
            e.advance(day)
            # occasional recall of a random memory
            p = rng.choice(people)
            mids = list(e.agent(p)['memory_meta'])
            if mids:
                e.recall(p, rng.choice(mids), f'r{n}-{p}', rehearse=True, affect=True)
    e.advance(day + rng.choice([0, 1, 10, 400]))
    # invariants
    for p in people:
        m = e.mood(p)
        assert all(isfinite(v) for v in m.values()) and -1 <= m['valence'] <= 1 and 0 <= m['arousal'] <= 1.0000001, (p, m)
        meta = e.agent(p)['memory_meta']
        hidden = {k for k, v in meta.items() if v.get('tier') in HIDDEN}
        shown = {x['event'] for x in e.memories(p, ' '.join(rng.sample(WORDS, 3)), limit=1000)}
        assert not shown & hidden, ('hidden memory recalled', p)
        ctx = e.context(p, 'What now? ' + ' '.join(rng.sample(WORDS, 3)))
        assert not {x['event'] for x in ctx['memories']} & hidden, ('hidden memory in context', p)
        for t in (v.get('tier') for v in meta.values()):
            assert t in (None, 'buffer', 'episodic', 'gist', 'dropped', 'merged', 'unattended'), t
        for v in meta.values():
            assert v['stability_days'] > 0 and isfinite(v['stability_days'])
        received = [o.event_id for o in e.world.observations.get(p, [])]
        assert len(received) == len(set(received)) and set(received) == set(meta), ('receipts != received', p)
        for other, r in e.agent(p)['relationships'].items():
            assert 0 <= r.get('trust', .5) <= 1 and 0 <= r.get('closeness', 0) <= 1, r
        cfg = e.state['config'].get('attention')
        for v in meta.values():
            a = v.get('attention')
            if a:
                assert 0 <= a['weight'] <= 1 and a['tier'] in ('FULL', 'GIST', 'NONE')
                if not a['captured'] and not a['addressed'] and not a['reasons'].get('own_action_or_thought'):
                    expected = 'FULL' if a['weight'] >= cfg['a_full'] else 'GIST' if a['weight'] >= cfg['a_gist'] else 'NONE'
                    assert a['tier'] == expected, a
                assert (a['tier'] == 'NONE') == (v.get('tier') == 'unattended')
        for b in e.agent(p).get('hippocampal_buffer', []):
            assert meta[b['source_event_id']]['tier'] == 'buffer', b
        if 'cognition' in e.state['config']:
            from devsim.cognition import views
            assert not {x['event'] for x in views(e, p, '', 10000)} & hidden
    with tempfile.TemporaryDirectory() as d:
        e.save(Path(d) / 'w.json')
        back = Engine.load(Path(d) / 'w.json')
        assert back.world.observations == e.world.observations and json.dumps(back.state, sort_keys=True) == json.dumps(e.state, sort_keys=True)
        for p in people:
            assert back.mood(p) == e.mood(p)
    return features


RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def main():
    seen = set()
    for seed in range(500):
        seen.update(run(seed))  # any failing seed raises with its message
    assert seen == {'sleep', 'attention', 'cognition'}
    checks = ['500 seeded random worlds (mood kernels, sleep with dials and routines, attention, cognition, caregiver links, '
              'recalls, long skips) keep every invariant: mood finite and in bounds; no hidden memory in recall, views or '
              'context; one receipt per received memory; trust and closeness in [0, 1]; attention tiers match thresholds '
              'and NONE is exactly the unattended tier; buffer entries are tagged; save and load reproduce state, memories '
              'and mood exactly']
    result = {'passed': True, 'scope': 'synthetic randomized engineering invariants; no model', 'checks': checks}
    RESULTS_DIR.joinpath('invariants-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
