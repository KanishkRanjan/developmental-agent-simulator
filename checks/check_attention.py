"""Attention allocation checks; synthetic, no model server. Every parameter is a design default, so these check the
mechanism's direction and bookkeeping, not calibrated psychology."""
from copy import deepcopy
import inspect
import json
from pathlib import Path
from random import Random
from statistics import mean, pvariance
from unittest.mock import patch

from devsim import attention, sleep
from devsim.engine import Engine, FACET_NAMES
from devsim.lifetime import Lifetime
from checks.check_environment import fixture as environment_fixture

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
CFG = {k: v['value'] for k, v in attention.parameters().items()}


def a_of(fit=.4, c_actor=.3, c_ment=0., goal=0., fatigue=0., load=0, dys=0., arousal=.5, z=.4, cfg=CFG):
    """(a, a_raw) through the pure model functions with the noise draw z held fixed."""
    T = attention.top_down(cfg, fit, c_actor, c_ment, goal)
    K = attention.capacity(cfg, arousal, fatigue, load, dys)
    raw = K * attention.share(cfg, T, [.5] * load, dys)
    return attention.noisy(raw, z, cfg['s_0'] + cfg['s_dys'] * dys), raw


def rejects(overrides):
    try:
        attention.configure(Engine(1), overrides)
    except ValueError:
        return True
    return False


def world(people, seed=5, facets=None, dial=None, enabled=True):
    e = Engine(seed)
    for p in people:
        e.entity(p, p.title())
        e.materialize(p, (facets or {}).get(p, dict.fromkeys(FACET_NAMES, 50)))
        if dial and p in dial:
            sleep.set_dials(e, p, **dial[p])
    if enabled is not None:
        attention.configure(e, {'enabled': enabled})
    return e


def turns(e, speaker, listeners, n, start=.3, gap_minutes=1, text='{s} said: nice weather today, number {i}.', key='x', extra=None):
    for i in range(n):
        e.schedule(f'@conversation:{key}:{i}', start + i * gap_minutes / 1440, 'A conversation turn.', {
            p: {'text': text.format(s=speaker.title(), i=i), 'source': speaker, 'kind': 'direct', 'encountered': [speaker],
                **(extra(p, i) if extra else {})} for p in listeners})


def results(e, owner):
    return {k: m['attention'] for k, m in e.agent(owner)['memory_meta'].items() if 'attention' in m}


def strip_attention(state):
    state = deepcopy(state)
    state['config'].pop('attention', None)
    state.get('runtime', {}).pop('policy_fingerprint', None)
    return state


def main():
    checks = []

    # 4.6 sanity values from the spec: one stream, theta 2, u0 0.15.
    for u, expected in [(.2, .64), (.05, .10), (.8, .97)]:
        assert abs(attention.share(CFG, u, [], 0) - expected) < .01, (u, attention.share(CFG, u, [], 0))
    checks.append('stream share matches the spec sanity values: u 0.2 -> 0.64, 0.05 -> 0.10, 0.8 -> 0.97')

    grid = [i / 10 for i in range(11)]
    for name in ('fit', 'c_actor', 'c_ment', 'goal'):
        for other in (0, .3, .7):
            base = {k: other for k in ('fit', 'c_actor', 'c_ment', 'goal')}
            for z in (-2, 0, 1.5):
                values = [a_of(**{**base, name: x}, z=z)[0] for x in grid]
                assert all(b >= a - 1e-12 for a, b in zip(values, values[1:])), (name, other, z)
    checks.append('with noise held fixed, raising topic fit, speaker closeness, mentioned closeness or goal match never lowers a')

    for name, levels in [('fatigue', grid), ('load', range(6)), ('dys', grid)]:
        for fit in (.1, .5, .9):
            raws = [a_of(fit=fit, **{name: x})[1] for x in levels]
            assert all(b <= a + 1e-12 for a, b in zip(raws, raws[1:])), (name, fit)
    shape = [attention.capacity(CFG, x, 0, 0, 0) for x in grid]
    assert max(shape) == shape[5] and shape[0] < shape[5] > shape[10]
    assert attention.capacity({**CFG, 'arousal_shape': 'monotone'}, .0, 0, 0, 0) == CFG['K_max']
    checks.append('fatigue, stream load and dysregulation never raise a_raw; capacity peaks at mid arousal (inverted_u) or is flat (monotone)')

    assert rejects({'w_topic': .5}) and rejects({'a_gist': .7}) and rejects({'theta': 0}) and rejects({'nonsense': 1})
    assert rejects({'arousal_shape': 'linear'}) and rejects({'affinity_base': {'social': .4}})
    assert rejects({'loadings': {'social': {'X': 1}}}) and rejects({'topic_rules': {'threat': ['Fire']}})
    assert not rejects({'w_topic': .25, 'w_goal': .30})
    e = Engine(1)
    attention.configure(e)
    try:
        attention.configure(e, {'theta': 3})
        raise AssertionError('policy silently replaced')
    except ValueError:
        pass
    checks.append('config fails fast: weights must sum to 1, a_gist < a_full, theta > 0, known keys, choices and well-formed tag tables')

    # Phase 2: bottom-up capture.
    for T in (0, .2, .9):
        assert attention.combined(T, 1) == 1
        assert abs(attention.combined(T, 0) - T) < 1e-12
    assert attention.bottom_up(CFG, 0, .9, 1, False) > attention.bottom_up(CFG, 0, .9, 0, False)
    assert attention.bottom_up(CFG, 0, 0, 0, True) == 1 and attention.bottom_up(CFG, .7, 0, 0, False) == .7 * CFG['g_sur']
    checks.append('soft OR: B = 1 gives u = 1 whatever T; B is the max of surprise, threat (scaled by threat sensitivity) and being addressed')

    # Golden regression: the master switch off reproduces the engine without the module exactly.
    plain, policy = environment_fixture()
    Lifetime(plain, policy, scripted=True).run(10)
    off, policy = environment_fixture()
    Lifetime(off, {**policy, 'attention': {'enabled': False}}, scripted=True).run(10)
    assert json.dumps(strip_attention(plain.state), sort_keys=True) == json.dumps(strip_attention(off.state), sort_keys=True)
    assert all('attention' not in m for a in off.state['agents'].values() for m in a['memory_meta'].values())
    for variant in ({}, {'sleep': {}}):
        on, policy = environment_fixture()
        Lifetime(on, {**policy, **variant, 'attention': {}}, scripted=True).run(10)
        tiers = [m['attention']['tier'] for a in on.state['agents'].values() for m in a['memory_meta'].values() if 'attention' in m]
        assert tiers and set(tiers) <= {'FULL', 'GIST', 'NONE'}
    checks.append('golden regression: enabled=false gives a byte-identical scripted 10-day household world; enabled runs with and without sleep')

    # Determinism: insertion order of events and of recipients does not change any result.
    def scene(order):
        e = world(['a', 'b', 'c', 'd'])
        events = [(f'@conversation:y:{i}', .3 + i / 1440, {p: {'text': f'A said: the exam is soon {i}.', 'source': 'a',
                   'encountered': ['a']} for p in order}) for i in range(8)]
        events += [(f'one-off-{i}', .3 + (i + .5) / 1440, {p: {'text': 'B waved.', 'source': 'b'} for p in order if p != 'b'})
                   for i in range(4)]
        for key, day, obs in (events if order[0] == 'b' else events[::-1]):
            e.schedule(key, day, 'x', obs)
        e.advance(1)
        return {p: results(e, p) for p in 'bcd'}
    assert scene(['b', 'c', 'd']) == scene(['d', 'c', 'b'])
    checks.append('same seed gives identical attention results whatever order events and recipients were scheduled in')

    # Directly addressed is never NONE; an asleep listener barely takes anything in.
    e = world(['a', 'b'])
    for i in range(30):
        e.schedule(f'call-{i}', .3 + i / 1440, 'x', {'b': {'text': 'A said to B: blah.', 'source': 'a', 'addressed': ['b']}})
    e.advance(1)
    assert all(r['tier'] == 'FULL' and r['addressed'] and r['captured'] and not r['may_skip_response'] for r in results(e, 'b').values())
    e = world(['a', 'b'])
    e.attention_providers = {'asleep': lambda engine, i, now: True}
    turns(e, 'a', ['b'], 20, extra=lambda p, i: {'valence': -.8, 'arousal': .7})
    e.advance(1)
    asleep = list(results(e, 'b').values())
    assert all(r['capacity'] == CFG['K_sleep'] and r['tier'] == 'NONE' for r in asleep)
    assert e.mood('b') == {'valence': 0, 'arousal': 0}, 'unattended events must not move mood'
    e.schedule('wake', 1.1, 'x', {'b': {'text': 'A shouted to B: wake up!', 'source': 'a', 'addressed': ['b']}})
    e.advance(1.2)
    woken = e.agent('b')['memory_meta']['wake']['attention']
    assert woken['tier'] == 'FULL' and woken['capacity'] > CFG['K_sleep'] and woken['bottom_up'] >= CFG['B_wake']
    checks.append('a directly addressed event (or one naming the listener) is captured, FULL and needs a response; asleep, capacity is K_sleep, only B >= B_wake gets in')

    # 5.2 Emotion: one event moves mood by its weight a; a captured event in full.
    def one(obs, dial=None, enabled=True):
        e = world(['a', 'b'], dial=dial, enabled=enabled)
        e.attention_providers = {'closeness': lambda engine, i, j: 1.0}  # a close speaker, so the event is not NONE
        e.schedule('one', .3, 'x', {'b': {'source': 'a', **obs}})
        e.advance(.4)
        return e.mood('b')['valence'], e.agent('b')['memory_meta']['one'].get('attention')
    calm = {'text': 'A said: the weather is grey.', 'valence': -.4, 'arousal': .3}
    (v_on, r), (v_off, _) = one(calm), one(calm, enabled=None)
    assert not r['captured'] and r['tier'] != 'NONE' and abs(v_on) < abs(v_off)
    alarm = {'text': 'A said: there is a fire in the kitchen!', 'valence': -.9, 'arousal': .95}
    (v_on, r), (v_off, _) = one(alarm, {'b': {'threat_sensitivity': 1}}), one(alarm, {'b': {'threat_sensitivity': 1}}, enabled=None)
    assert r['captured'] and v_on == v_off
    checks.append('emotion: an uncaptured event moves mood by a fraction a of its impulse; a captured (threat) event moves it in full')

    # Effects: NONE leaves a hidden receipt only; GIST keeps who, topic and rough valence; mood ignores NONE.
    e = world(['a', 'b'])
    turns(e, 'a', ['b'], 60, text='{s} said: I spilled tea on the rug again, number {i}.',
          extra=lambda p, i: {'valence': -.5, 'arousal': .4, 'threat_salience': 0})
    e.advance(1)
    meta = e.agent('b')['memory_meta']
    by = {t: [k for k, m in meta.items() if m['attention']['tier'] == t] for t in ('FULL', 'GIST', 'NONE')}
    assert all(by.values()), {t: len(v) for t, v in by.items()}
    observed = {o.event_id: o for o in e.world.observations['b']}
    assert all(meta[k]['tier'] == 'unattended' and 'tea' not in observed[k].text for k in by['NONE'])
    assert all(meta[k]['tier'] == 'gist' and meta[k]['gist_only'] and observed[k].text.startswith('Half-noticed: A')
               and 'unpleasant' in observed[k].text and 'tea' not in observed[k].text for k in by['GIST'])
    shown = {m['event'] for m in e.memories('b', 'tea rug spilled', limit=100)}
    assert shown and not shown & set(by['NONE'])
    full_k = [k for k in by['FULL']][0]
    assert 'tea' in observed[full_k].text and e.state['events'][[x['id'] for x in e.state['events']].index(by['NONE'][0])][
        'observations']['b']['text'].count('tea') == 1  # the original stays in the event log
    plain = world(['a', 'b'], enabled=None)
    turns(plain, 'a', ['b'], 60, text='{s} said: I spilled tea on the rug again, number {i}.',
          extra=lambda p, i: {'valence': -.5, 'arousal': .4, 'threat_salience': 0})
    plain.advance(1)
    stab = {o.event_id: o.stability_days for o in plain.world.observations['b']}
    assert all(observed[k].stability_days < stab[k] for k in by['GIST'] + by['NONE'])
    checks.append('NONE writes only a hidden receipt (no recall, no mood); GIST encodes who, topic and rough valence at lower stability; originals stay in the event log')

    # Context: the household recent-conversation view skips unattended turns.
    from devsim import household
    e.state['runtime'] = {'conversations': {'x': {'status': 'open', 'active': ['a', 'b'], 'spec': {'topic': 't'}}}}
    seen = household.conversation_memory(e, 'b', turns=100)['this_conversation']
    assert len(seen) == len(by['FULL']) + len(by['GIST']) and not any(t['text'] == '(not attended)' for t in seen)
    checks.append('LLM context: NONE turns are left out of memories and conversation_so_far; GIST turns appear as one summary line')

    # Statistical: N = 2000 sampled agents, identical events; no archetype flag anywhere.
    rng = Random(42)
    people = [f'p{i}' for i in range(2000)]
    facets = {p: {k: rng.uniform(20, 80) for k in FACET_NAMES} for p in people}
    dial = {p: {'dysregulation': rng.random(), 'threat_sensitivity': rng.random()} for p in people}
    big = world(['speaker', *people], facets=facets, dial=dial)
    turns(big, 'speaker', people, 6, text='{s} said: the bus was late again this morning, number {i}.')
    big.advance(1)
    assert big.state['attention_stats']['allocations'] == 6 * len(people)
    ranked = sorted(people, key=lambda p: dial[p]['dysregulation'])
    low, high = ([r['weight'] for p in group for r in results(big, p).values()] for group in (ranked[:500], ranked[-500:]))
    assert mean(high) < mean(low) and pvariance(high) > pvariance(low), (mean(low), mean(high), pvariance(low), pvariance(high))
    stats = {'low_dys_mean_a': round(mean(low), 3), 'high_dys_mean_a': round(mean(high), 3),
             'low_dys_var_a': round(pvariance(low), 4), 'high_dys_var_a': round(pvariance(high), 4)}
    checks.append(f'2000 sampled agents on identical events: high dysregulation gives lower mean and higher variance of a {stats}')

    # Statistical: threat sensitivity, threat events vs neutral ones.
    threat = world(['speaker', *people], facets=facets, dial=dial)
    turns(threat, 'speaker', people, 4, text='{s} said: the bus was late again this morning, number {i}.')
    turns(threat, 'speaker', people, 4, start=.5, key='t', text='{s} said: someone is following me with a knife, number {i}.',
          extra=lambda p, i: {'valence': -.7, 'arousal': .7})
    threat.advance(1)
    def mean_a(group, prefix):
        return mean(r['weight'] for p in group for k, r in results(threat, p).items() if k.startswith(prefix))
    by_ts = sorted(people, key=lambda p: dial[p]['threat_sensitivity'])
    lo, hi = by_ts[:500], by_ts[-500:]
    tstats = {k: round(v, 3) for k, v in {'high_ts_threat': mean_a(hi, '@conversation:t:'), 'high_ts_neutral': mean_a(hi, '@conversation:x:'),
              'low_ts_threat': mean_a(lo, '@conversation:t:')}.items()}
    assert tstats['high_ts_threat'] > tstats['high_ts_neutral'] and tstats['high_ts_threat'] > tstats['low_ts_threat'], tstats
    checks.append(f'2000 sampled agents: high threat sensitivity attends more to threat events than to neutral ones, and more than low {tstats}')

    # Phase 3: drift. Bored listeners (stranger speaker, flat topic) vs interested ones (close speaker, goal match).
    groups = {'bored': [f'bored{i}' for i in range(200)], 'keen': [f'keen{i}' for i in range(200)]}
    long = world(['speaker', *groups['bored'], *groups['keen']])
    keen = lambda i: i.startswith('keen')
    long.attention_providers = {'closeness': lambda engine, i, j: 1.0 if keen(i) else .05,
                                'goal_match': lambda engine, i, view: 1.0 if keen(i) else 0.0}
    turns(long, 'speaker', [*groups['bored'], *groups['keen']], 120, gap_minutes=3,
          text='{s} said: the weather is mild again, number {i}.')
    long.advance(1)
    def tally(group):
        rs = [r for p in group for r in results(long, p).values()]
        return {'drift_periods': sum(long.agent(p)['attention_state'].get('drift_periods', 0) for p in group),
                'drifted_events': sum(r['drifted'] for r in rs), 'full': sum(r['tier'] == 'FULL' for r in rs)}
    bored_t, keen_t = tally(groups['bored']), tally(groups['keen'])
    assert bored_t['drift_periods'] > keen_t['drift_periods'] and bored_t['full'] < keen_t['full'], (bored_t, keen_t)
    assert keen_t['drift_periods'] > 0, 'interested listeners can drift too, just less'
    # Capture ends a drift; drift is resolved lazily at the next event only.
    e = world(['a', 'b'])
    turns(e, 'a', ['b'], 200, gap_minutes=3, text='{s} said: the weather is mild again, number {i}.')
    e.advance(.3 + 199 * 3 / 1440 + 1e-9)
    drifting = [k for k, r in results(e, 'b').items() if r['drifted']]
    assert drifting
    e.schedule('@conversation:x:shout', e.day + 1 / 1440, 'x', {'b': {'text': 'A said to B: are you listening?', 'source': 'a', 'addressed': ['b']}})
    e.advance(e.day + 2 / 1440)
    shout = e.agent('b')['memory_meta']['@conversation:x:shout']['attention']
    assert shout['captured'] and not shout['drifted'] and e.agent('b')['attention_state']['streams']['conversation:x']['drift_until'] is None
    checks.append(f'drift: bored listeners in a 120-turn stream drift more and keep fewer FULL traces than interested ones '
                  f'(bored {bored_t}, interested {keen_t}); capture ends a drift')

    # The researcher's addressed line (devsim.visit) is addressed to that person only.
    from tempfile import TemporaryDirectory
    from checks.check_household import fixture as household_fixture
    from devsim import visit
    with TemporaryDirectory() as d:
        guest, hpolicy = household_fixture(turns=4)
        control = Lifetime(guest, {**hpolicy, 'attention': {}}, scripted=True)
        control.inbox = Path(d) / 'inbox.jsonl'
        visit.say(Path(d), 'Please talk about the bicycle.', to='b', name='Kanishk')
        control.run(.8, Path(d) / 'world.json')
        line = guest.state['runtime']['visitor_log'][0]['event']
        heard = {p: guest.agent(p)['memory_meta'][line]['attention'] for p in guest.state['runtime']['visitor_log'][0]['hearers']}
        assert heard['b']['addressed'] and heard['b']['captured'] and not any(r['addressed'] for p, r in heard.items() if p != 'b')
    checks.append('a visitor line addressed to one person is captured for them and not addressed to the others who overhear it')

    # Phase 4: felt ignored, off by default.
    def ignored(flag):
        e = world(['mum', 'kid'], dial={'kid': {'dysregulation': 1}}, enabled=None)
        attention.configure(e, {'felt_ignored': flag})
        e.relate('mum', 'kid', 'parent', closeness=.8)
        turns(e, 'mum', ['kid'], 80, gap_minutes=3, text='{s} said: the weather is mild again, number {i}.')
        e.advance(1)
        return e.agent('mum')['relationships']['kid']['closeness'], e.state['attention_stats'].get('felt_ignored', [])
    (c_off, log_off), (c_on, log_on), (c_again, log_again) = ignored(False), ignored(True), ignored(True)
    assert c_off == .8 and not log_off and c_on < .8 and log_on and (c_on, log_on) == (c_again, log_again)
    assert abs(c_on - (.8 - CFG['ignored_penalty'] * len(log_on))) < 1e-9
    checks.append(f'felt ignored (flag, default off): a close speaker facing an inattentive listener loses closeness '
                  f'{len(log_on)} times over 80 turns via Engine.relate, each logged; off changes nothing')

    # Crowded scene: fewer traces than with the switch off, none lost for directly addressed events.
    def crowd(enabled):
        e = world(['host', *[f'g{i}' for i in range(30)]], enabled=enabled)
        guests = [f'g{i}' for i in range(30)]
        turns(e, 'host', guests, 20, extra=lambda p, i: {'addressed': [p]} if i % 5 == 0 and p == f'g{i}' else {})
        e.advance(1)
        kept = lambda p, pred: sum(1 for k, m in e.agent(p)['memory_meta'].items() if pred(k) and m.get('tier') not in sleep.HIDDEN)
        return (sum(kept(p, lambda k: True) for p in guests),
                sum(kept(f'g{i}', lambda k, i=i: k == f'@conversation:x:{i}') for i in range(0, 20, 5)))
    (on_all, on_addressed), (off_all, off_addressed) = crowd(True), crowd(False)
    assert on_all < .9 * off_all and on_addressed == off_addressed == 4, (on_all, off_all, on_addressed)
    checks.append(f'crowded scene (30 listeners, 20 turns): traces drop from {off_all} to {on_all}; addressed events all kept')

    # Cost: one allocation per (listener, event), only from Engine.advance; none from a tick loop.
    calls = []
    real = attention.allocate
    with patch('devsim.attention.allocate', side_effect=lambda *a: calls.append(a[1]) or real(*a)):
        for w in (10, 100):
            e = world(['s', *[f'w{i}' for i in range(w)]])
            calls.clear()
            e.schedule('broadcast', .5, 'x', {f'w{i}': {'text': 'S announced dinner.', 'source': 's'} for i in range(w)})
            e.advance(.6)
            assert len(calls) == w
        e = world(['s', 't'])
        calls.clear()
        e.advance(30)  # time passing with no events costs nothing
        assert not calls
    import devsim
    sites = [p.name for p in Path(devsim.__file__).parent.rglob('*.py') if 'attention.allocate(' in p.read_text()]
    assert sites == ['engine.py'] and inspect.getsource(Engine.advance).count('attention.allocate(') == 1
    checks.append('cost: exactly W allocations for an event with W listeners, none while time passes, one call site (Engine.advance)')

    source = inspect.getsource(attention).lower()
    assert not any(word in source for word in ('archetype', 'adhd', "['role']", 'agent_type', 'narciss', 'psychopath'))
    checks.append('no branch keyed on agent type, role or diagnosis; differences come from traits, dials, mood and arousal')

    result = {'passed': True, 'scope': 'synthetic engineering checks of design defaults (unverified); no calibrated attention claim',
              'checks': checks}
    RESULTS_DIR.joinpath('attention-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
