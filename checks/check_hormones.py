"""Hormone-state checks: three variables, lazy closed-form advance, determinism, no special-casing, zero added model
calls, O(1) per event, and the spec's scenarios (tired but wired, sleep loss, group drift, zoned out, speech style)."""
import ast
from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path
from random import Random
import re
import time
from unittest.mock import patch

from devsim import attention, hormone_calibration, hormones, sleep
from devsim.attention import unit
from devsim.engine import Engine, FACET_NAMES
from devsim.lifetime import Lifetime

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
H = 1 / 24


def world(n=3, names=None, facts=None, attention_on=False, routine=True, seed=5):
    e = Engine(seed=seed)
    for i in range(n):
        key = f'a{i}'
        e.entity(key, (names or {}).get(key, key.title()), {'birth_day': -30 * 365.25, **(facts or {}).get(key, {})})
        e.materialize(key, dict.fromkeys(FACET_NAMES, 50), birth_day=-30 * 365.25)
    if routine:
        e.state['config']['household'] = {'rooms': {'home': {'label': 'home'}},
                                          'routines': {k: {'available_hours': [[7, 23]]} for k in e.state['agents']}}
    hormones.configure(e)
    if attention_on:
        attention.configure(e)
    return e


def say(e, key, day, source, listeners, valence=-.6, arousal=.7, **extra):
    e.schedule(key, day, 'A test event.', {p: {'text': f'{source} said something.', 'source': source, 'kind': 'direct',
                                              'valence': valence, 'arousal': arousal, **extra} for p in listeners})
    e.advance(day)


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


class CountingDict(dict):
    """Counts iteration over the agents table."""
    reads = 0

    def __iter__(self):
        CountingDict.reads += 1
        return super().__iter__()

    def items(self):
        CountingDict.reads += 1
        return super().items()

    def values(self):
        CountingDict.reads += 1
        return super().values()

    def keys(self):
        CountingDict.reads += 1
        return super().keys()


def main():
    checks = []
    e = world()
    ctx = hormones.context(e, 'a0')

    # Exactly three hormone variables.
    assert [f.name for f in fields(hormones.HormoneState)] == ['stress_x', 'sleep_pressure', 'dopamine_tonic']
    assert len(fields(hormones.HormoneState)) == 3
    checks.append('the hormone state has exactly three fields: stress_x, sleep_pressure, dopamine_tonic')

    # Lazy advance is a semigroup, across sleep and wake boundaries.
    rng = Random(3)
    for _ in range(300):
        t0 = rng.uniform(0, 3)
        state = hormones.HormoneState(hormones.Level(rng.uniform(0, 3), t0), hormones.Level(rng.random(), t0),
                                      hormones.Level(rng.uniform(-2, 2), t0))
        t1 = t0 + rng.uniform(0, 2)
        t2 = t1 + rng.uniform(0, 2)
        once, twice = hormones.advance(state, t2, ctx), hormones.advance(hormones.advance(state, t1, ctx), t2, ctx)
        for f in fields(hormones.HormoneState):
            assert close(getattr(once, f.name).value, getattr(twice, f.name).value), (f.name, state, t1, t2)
    checks.append('advance(advance(s, t1), t2) == advance(s, t2) for 300 random states and times spanning nights (relative 1e-9)')

    # Ranges, and sleep pressure rising awake and falling asleep.
    state = hormones.initial(ctx, 0.0)
    awake = [1 + (8 + m / 60) * H for m in range(0, 600, 7)]
    asleep = [1 + (23.6 + m / 60) * H for m in range(0, 400, 7)]
    ps = lambda ts: [hormones.snapshot(state, ctx, t).sleep_pressure for t in ts]
    assert all(b > a for a, b in zip(ps(awake), ps(awake)[1:])) and all(b < a for a, b in zip(ps(asleep), ps(asleep)[1:]))
    for t in [rng.uniform(0, 5) for _ in range(200)]:
        snap = hormones.snapshot(hormones.HormoneState(hormones.Level(rng.uniform(0, 20), 0), hormones.Level(rng.random(), 0),
                                                       hormones.Level(rng.uniform(-5, 5), 0)), ctx, t)
        assert 0 <= snap.stress < 1 and 0 <= snap.sleep_pressure <= 1 and -1 < snap.dopamine < 1
    checks.append('stress readout stays in [0, 1) and sleep pressure in [0, 1]; pressure strictly rises awake and falls asleep')

    # The awakening rise peaks tau_car after waking.
    p = ctx['p']
    wake = 1 + 7 * H
    car = lambda t: p['A_car'] * ((t - wake) * 24 / p['tau_car_h']) * 2.718281828459045 ** (1 - (t - wake) * 24 / p['tau_car_h'])
    minutes = [wake + m / 1440 for m in range(0, 121)]
    assert max(range(121), key=lambda m: car(minutes[m])) == round(p['tau_car_h'] * 60)
    total = max(range(121), key=lambda m: hormones.baseline(ctx, minutes[m], False))
    assert 30 <= total <= 45 and hormones.baseline(ctx, 1 + 3 * H, True) == ctx['b_floor']
    checks.append(f'the awakening rise peaks tau_car ({round(p["tau_car_h"] * 60)} min) after waking; the whole baseline peaks at '
                  f'{total} min, inside the verified 30-45 min window; asleep it sits at the floor')

    # Habituation shrinks repeats.
    snap = hormones.snapshot(state, ctx, 1 + 10 * H)
    steps = [hormones.stress_increment(ctx, snap, {'threat': .5, 'controllability': .5}, .7, 0, n) for n in range(4)]
    assert steps[0] > steps[1] > steps[2] > steps[3] and steps[2] < .15 * steps[0]
    checks.append('repeat increments fade within one or two exposures (habituation reuses the routine exposure count)')

    # Determinism: seeded by (seed, agent, event or night, purpose).
    assert unit(5, 'a0', 'ev', 'x') == unit(5, 'a0', 'ev', 'x') and unit(5, 'a0', 'ev', 'x') != unit(5, 'a0', 'ev', 'y')
    runs = []
    for _ in range(2):
        w = world()
        for i in range(30):
            say(w, f'e{i}', 1 + (8 + i / 3) * H, f'a{(i + 1) % 3}', [f'a{i % 3}'], valence=(-1) ** i * .5)
        runs.append({k: (a.get('hormones'), a.get('expectations')) for k, a in w.state['agents'].items()})
    assert runs[0] == runs[1]
    checks.append('same seed, agent, event and purpose give bit-identical results; a different purpose string changes the draw')

    # No special-casing: no forbidden identifiers, and names, facts and labels change nothing.
    source = Path(hormones.__file__).read_text()
    tree = ast.parse(source)
    words = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    words |= {a.arg for n in ast.walk(tree) if isinstance(n, ast.arguments) for a in n.args + n.kwonlyargs}
    words |= {w for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) for w in re.findall(r'[a-z_]+', n.value.lower())}
    assert not words & {'agent_type', 'archetype', 'role', 'sex', 'gender'}
    def stream(names=None, facts=None, labels=None):
        w = world(names=names, facts=facts)
        for a, b in (('a0', 'a1'), ('a1', 'a2')):
            w.relate(a, b, (labels or {}).get(a, 'friend'), trust=.6, closeness=.4)
        for i in range(20):
            say(w, f'e{i}', 1 + (9 + i / 4) * H, f'a{(i + 2) % 3}', ['a0', 'a1', 'a2'][:1 + i % 3], valence=(-1) ** i * .4)
        return {k: (a.get('hormones'), a.get('expectations')) for k, a in w.state['agents'].items()}
    assert stream() == stream(names={'a0': 'Zed', 'a1': 'Ann'}, facts={'a0': {'sex': 'f'}, 'a1': {'sex': 'm', 'occupation': 'nurse'}},
                              labels={'a0': 'caregiver', 'a1': 'rival'})
    report = hormone_calibration.calibrate(300)
    assert report['reactivity_r2_declared'] > .95 and report['reactivity_r2_added_by_nuisance'] < 1e-3
    assert report['wanting_r2_declared'] > .999 and report['wanting_r2_added_by_nuisance'] < 1e-9
    RESULTS_DIR.joinpath('hormone-calibration.json').write_text(json.dumps(report, indent=2) + '\n')
    checks.append(f'no agent-type, archetype, role, sex or gender identifier in the module; names, identity facts and tie labels '
                  f'change nothing; across 300 seeded agents the declared inputs explain {report["reactivity_r2_declared"]:.3f} of '
                  f'reactivity and {report["wanting_r2_declared"]:.3f} of wanting, a nuisance fact adds '
                  f'{report["reactivity_r2_added_by_nuisance"]:.1e}')

    # Zero added model calls.
    from checks.check_household import fixture, stub
    counts = []
    for extra in ({}, {'hormones': {}}):
        f, policy = fixture()
        calls = []
        with patch('devsim.engine.request_json', side_effect=lambda *a, **k: calls.append(1) or stub(*a, **k)):
            Lifetime(f, {**policy, **extra}).run(.8)
        counts.append(len(calls))
    assert counts[0] == counts[1] > 0, counts
    checks.append(f'a stubbed household run makes the same number of model calls with and without the module ({counts[0]})')

    # O(1) per event: time does not grow with agent count, and nothing iterates over the agents table.
    def per_event(n):
        w = world(n)
        say(w, 'warm', 1 + 8 * H, 'a1', ['a0'])
        start = time.perf_counter()
        for i in range(200):
            hormones.on_event(w, 'a0', {'id': f'x{i}', 'day': 1 + (8 + i / 100) * H}, {'text': 'x', 'source': 'a1', 'valence': -.3, 'arousal': .5})
        return (time.perf_counter() - start) / 200
    small, large = per_event(5), per_event(400)
    assert large < 3 * small, (small, large)
    w = world(50)
    w.state['agents'] = CountingDict(w.state['agents'])
    CountingDict.reads = 0
    hormones.on_event(w, 'a0', {'id': 'y', 'day': 1 + 9 * H}, {'text': 'x', 'source': 'a1', 'valence': -.3, 'arousal': .5})
    hormones.read(w, 'a0', 1 + 10 * H)
    hormones.wanting_scores(w, 'a0', ['a1', 'a2'])
    assert CountingDict.reads == 0
    checks.append(f'per-event cost is flat in agent count ({small * 1e6:.0f} us at 5 agents, {large * 1e6:.0f} us at 400) and no '
                  'event, read or wanting call iterates over the agents')

    # Scenario (a): tired but wired.
    e = world()
    ctx = hormones.context(e, 'a0')
    base = hormones.advance(hormones.initial(ctx, 0.0), 1 + 22.5 * H, ctx)
    tired = hormones.onset(base, ctx, 1 + 23 * H, 2 + 7 * H)
    wired = hormones.onset(hormones.HormoneState(hormones.Level(2.0, base.stress_x.anchor), base.sleep_pressure, base.dopamine_tonic),
                           ctx, 1 + 23 * H, 2 + 7 * H)
    assert hormones.snapshot(base, ctx, 1 + 23 * H).sleep_pressure > .6
    assert wired[0] > tired[0] and wired[1] < tired[1]
    stressed = hormones.HormoneState(hormones.Level(2.0, base.stress_x.anchor), base.sleep_pressure, base.dopamine_tonic)
    assert hormones.snapshot(stressed, ctx, 2 + 7 * H).sleep_pressure > hormones.snapshot(base, ctx, 2 + 7 * H).sleep_pressure
    off = world()
    off.state['config']['hormones']['wired_override'] = False
    octx = hormones.context(off, 'a0')
    assert hormones.onset(stressed, octx, 1 + 23 * H, 2 + 7 * H)[1] == 1.0
    checks.append('tired but wired: high sleep pressure plus high stress gives a longer onset, lower efficiency and more pressure '
                  'left in the morning than high pressure alone; the flag turns it off')

    # Scenario (b): sleep loss lowers attention capacity.
    caps = []
    for P in (.1, .95):
        w = world(attention_on=True)
        hormones.store(w, 'a0', hormones.HormoneState(hormones.Level(0.0, 1 + 9 * H), hormones.Level(P, 1 + 9 * H), hormones.Level(0.0, 1 + 9 * H)))
        w.advance(1 + 9 * H)
        caps.append(attention.allocate(w, 'a0', {'id': '@conversation:z:0', 'day': 1 + 9 * H},
                                       {'text': 'A1 said hi.', 'source': 'a1', 'kind': 'direct'}).capacity)
    assert caps[1] < caps[0], caps
    checks.append(f'a sleep-deprived listener has lower attention capacity (K {caps[1]:.2f} vs {caps[0]:.2f} rested)')

    # Scenario (c): group drift; (d): zoned out learns nothing.
    e = world()
    ctx = hormones.context(e, 'a0')
    e.relate('a0', 'a1', 'friend', trust=.8, closeness=.9)
    for _ in range(25):
        hormones.learn(e, 'a0', 'group:old', -.6, 1.0, ctx)
        v, _ = hormones.expectation(e, 'a0', 'a1', ctx)
        hormones.learn(e, 'a0', 'a1', v, 1.0, ctx)  # the friend is exactly as expected: prediction error ~ 0
    w = hormones.wanting_scores(e, 'a0', ['group:old', 'group:new', 'a1'])
    assert w['group:new'] > w['group:old'] and w['a1'] > w['group:new']
    assert hormones.leave_chance(e, 'a0', 'group:old', ['group:new']) > 0 and hormones.leave_chance(e, 'a0', 'a1', ['group:new']) == 0
    before = deepcopy(e.agent('a0').get('expectations'))
    hormones.learn(e, 'a0', 'group:old', 1.0, hormones.tier_weight(ctx['p'], attention.AttentionResult(0.1, attention.NONE)), ctx)
    assert e.agent('a0')['expectations'] == before
    checks.append('group drift: repeated disappointment sinks a group below a new one with an optimistic prior, a close friend '
                  'with ~0 prediction error stays most wanted, and leaving becomes possible; an unattended outcome teaches nothing')

    # Scenario (e): speech style.
    p = e.state['config']['hormones']
    grid = [i / 20 for i in range(20)]
    levels = [hormones.style_level(p, s) for s in grid]
    assert levels == sorted(levels) and levels[0] == 0 and levels[-1] == 2
    snap = lambda s, P=.2: hormones.Snapshot(0, s, 0, 0, 0, P, 0, P, 0, 0, False, 0)
    strong = hormones.style_directive(p, snap(.8))
    assert 'fragmented' in strong and 'as much as you normally would' in strong
    assert not any(w in hormones.style_directive(p, snap(s)).lower() for s in grid for w in ('shorter', 'brief', 'fewer words', 'say less'))
    assert 'tired' in hormones.style_directive(p, snap(.1, .9)).lower() and hormones.style_directive(p, snap(.1)) == ''
    checks.append('the style directive is monotone in stress (none, mild, strong), never asks for shorter speech by default, and '
                  'adds the tired line only under high sleep pressure')

    # Integration: events store their stress, mood deepens under stress, sleep quality pays for a stressed bedtime.
    e = world()
    say(e, 'calm', 1 + 9 * H, 'a1', ['a0'], valence=-.5, arousal=.1)
    say(e, 'hit', 1 + 9.01 * H, 'a1', ['a2'], valence=-.9, arousal=1)
    say(e, 'hit2', 1 + 9.02 * H, 'a1', ['a2'], valence=-.5, arousal=.1)
    meta = lambda who, ev: e.agent(who)['memory_meta'][ev]['hormones']
    assert meta('a2', 'hit2')['S'] > meta('a0', 'calm')['S'] and meta('a2', 'hit')['dx'] > 0
    assert hormones.mood_scale(e, e.agent('a2')['memory_meta']['hit2'], -.5) > hormones.mood_scale(e, e.agent('a0')['memory_meta']['calm'], -.5)
    assert e.agent('a0')['expectations']['a1']['n'] == 1
    qs = []
    for late in (False, True):
        w = world()
        sleep.configure(w)
        if late:
            say(w, 'fight', 1 + 22.9 * H, 'a1', ['a0'], valence=-1, arousal=1)
        say(w, 'note', 1 + 22.95 * H, 'a2', ['a0'], valence=0, arousal=0)
        w.advance(2 + 8 * H)
        qs.append(w.agent('a0')['sleep']['last_q'])
    assert qs[1] < qs[0], qs
    checks.append('each received event records stress at that moment and teaches an expectation of its source; negative mood '
                  'impulses deepen with stress; the sleep module pays for a stressed bedtime through sleep efficiency')

    # Default-safe: no household, attention or sleep module.
    lone = world(routine=False)
    say(lone, 'x', 1 + 9 * H, 'a1', ['a0'])
    snap = hormones.read(lone, 'a0', 1 + 12 * H)
    assert not snap.asleep and snap.sleep_pressure > 0 and hormones.capacity_factor(lone, 'a0', 1) == 1.0
    try:
        hormones.configure(world(), {'nonsense': 1})
        raise AssertionError('bad setting accepted')
    except ValueError:
        pass
    checks.append('runs standalone with safe defaults (no routine: never asleep; no attention or sleep module); unknown settings are rejected')

    result = {'passed': True, 'scope': 'synthetic hormone-module engineering checks; constants are tagged, mostly [D]/[U]', 'checks': checks}
    RESULTS_DIR.joinpath('hormones-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
