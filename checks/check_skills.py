"""Skill module checks (spec section 13): pure reads, practice, replay, ordering, spacing, testing, savings, near
transfer, feedback, self-perception, determinism, no special-casing, cost, the E2 averaging mechanism, strategy
shifts, and scenarios (busy novice vs gifted idle, tired, competence gate, emergent abandonment, pruning)."""
import ast
from copy import deepcopy
import hashlib
import json
from math import exp
from pathlib import Path
import re
from unittest.mock import patch

import numpy as np

from devsim import skills
from devsim.engine import Engine, FACET_NAMES
from devsim.lifetime import Lifetime

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def world(n=1, seed=5, overrides=None, hormones=False, names=None, facts=None):
    e = Engine(seed=seed)
    for i in range(n):
        key = f'p{i}'
        e.entity(key, (names or {}).get(key, key.title()), {'birth_day': -25 * 365.25, **(facts or {}).get(key, {})})
        e.materialize(key, dict.fromkeys(FACET_NAMES, 50), birth_day=-25 * 365.25)
    e.advance(0)
    if hormones:
        from devsim import hormones as h
        h.configure(e)
    skills.configure(e, overrides)
    return e


def digest(e):
    return hashlib.sha256(json.dumps(e.state, sort_keys=True, default=str).encode()).hexdigest()


def run(e, owner, key, times, **kw):
    return [skills.practice(e, owner, key, f'{key}:{i}', t=t, **kw) for i, t in enumerate(times)]


def fit_aic(n, y):
    """AIC of exponential A(1 - e^-bn) (2 parameters) and power A(1 - (1 + bn)^-c) (3), least squares on a grid."""
    def best(shapes, k):
        out = np.inf
        for f in shapes:
            A = (f @ y) / (f @ f) if f @ f else 0
            rss = float(((y - A * f) ** 2).sum())
            out = min(out, len(y) * np.log(rss / len(y) + 1e-300) + 2 * k)
        return out
    bs = np.geomspace(1e-3, 3, 160)
    expo = best([1 - np.exp(-b * n) for b in bs], 2)
    power = best([1 - (1 + b * n) ** -c for b in np.geomspace(1e-3, 30, 60) for c in np.geomspace(.05, 20, 60)], 3)
    return expo, power


def main():
    checks = []
    NO_SHIFT = {'strategy_shift': False}

    # Pure reads, practice, zero attention, replay, semigroup.
    e = world()
    run(e, 'p0', 'salsa dancing', [0, 1, 2, 3])
    before = digest(e)
    values = [skills.level(e, 'p0', 'salsa dancing', 3 + d) for d in (0, 1, 5, 30, 300)]
    skills.performance(e, 'p0', 'salsa dancing', 10)
    skills.context(e, 'p0')
    assert digest(e) == before and all(0 <= v < 1 for v in values) and values == sorted(values, reverse=True)
    a, b = skills.level(e, 'p0', 'salsa dancing', 5), skills.level(e, 'p0', 'salsa dancing', 9)
    assert b == skills.level(e, 'p0', 'salsa dancing', 9) and a >= b
    step = skills.practice(e, 'p0', 'salsa dancing', 'more', t=4, attention=.8)
    assert step['level'] > step['level_before']
    s_before, l_before = skills.state_of(e, 'p0', 'salsa dancing').S, skills.level(e, 'p0', 'salsa dancing', 5)
    skills.practice(e, 'p0', 'salsa dancing', 'zoned', t=5, attention=0)
    assert skills.state_of(e, 'p0', 'salsa dancing').S == s_before and abs(skills.level(e, 'p0', 'salsa dancing', 5) - l_before) < 1e-12
    stored = e.agent('p0')['skills']['salsa danc']
    assert skills.replay(stored, skills.cfg(e)) == stored
    skills.set_level(e, 'p0', 'salsa dancing', .5, t=6)  # a researcher's edit restarts the replay record
    skills.practice(e, 'p0', 'salsa dancing', 'after-edit', t=7, attention=1)
    stored = e.agent('p0')['skills']['salsa danc']
    assert skills.replay(stored, skills.cfg(e)) == stored and skills.level(e, 'p0', 'salsa dancing', 7) > .5 * exp(-1 / stored['S']) - 1e-9
    checks.append('reads are pure and decay monotonically in [0, 1); practice raises the level; zero attention changes neither '
                  'level nor stability; replaying the event log reproduces the stored state exactly; reads compose')

    # Ordering of decay by attributes (E12), same person, skill key and draws in separate worlds.
    def retained(attrs):
        w = world(overrides=NO_SHIFT)
        run(w, 'p0', 'task', [0, 2, 4, 6, 8], attrs=attrs, attention=1)
        return skills.level(w, 'p0', 'task', 40)
    for name in ('cognitive', 'open_loop', 'accuracy_graded'):
        low = retained({name: .1})
        high = retained({name: .9})
        assert high < low, (name, low, high)
    checks.append('with identical histories, more cognitive, more open-loop and more accuracy-graded skills retain less after '
                  'the same idle time (E12 ordering, coefficients free)')

    # Spacing (E8) and testing (E9).
    def at_test(times, mode='retrieval'):
        w = world(overrides=NO_SHIFT)
        run(w, 'p0', 'vocabulary', times, mode=mode, attention=1)
        return skills.level(w, 'p0', 'vocabulary', times[-1] + 60), skills.state_of(w, 'p0', 'vocabulary').S
    spaced, massed = at_test([0, 3, 6, 9, 12, 15]), at_test([15 + i / 200 for i in range(6)])
    assert spaced[0] > massed[0] and spaced[1] > massed[1]
    assert at_test([0, 3, 6, 9], 'retrieval')[1] > at_test([0, 3, 6, 9], 'restudy')[1]
    checks.append(f'spaced practice keeps more at a 60-day test than the same practice massed ({spaced[0]:.3f} vs {massed[0]:.3f}); '
                  'retrieval builds more stability than restudy (directions E8, E9)')

    # Savings (E13): relearning after decay, and after pruning, beats first learning.
    def count_to(w, key, start, target=.6):
        for i in range(400):
            step = skills.practice(w, 'p0', key, f'{key}:{start}:{i}', t=start + i * .05, attention=.5)
            if step['level'] >= target:
                return i + 1
        return 400
    w = world(overrides=NO_SHIFT)
    first = count_to(w, 'juggling', 0)
    assert skills.level(w, 'p0', 'juggling', 399) < .05  # faded before relearning
    again = count_to(w, 'juggling', 400)
    assert again < first
    pruned = world(overrides={**NO_SHIFT, 'eps_recency_days': 30})
    count_to(pruned, 'juggling', 0)
    skills.practice(pruned, 'p0', 'whistling', 'w', t=400, attention=1)  # practising something else prunes the faded skill
    assert 'juggl' in pruned.agent('p0')['skill_savings'] and 'juggl' not in pruned.agent('p0')['skills']
    assert count_to(pruned, 'juggling', 401) < count_to(world(overrides=NO_SHIFT), 'juggling', 401)
    checks.append(f'relearning after near-total decay takes fewer practices than first learning ({again} vs {first}); a pruned '
                  'skill keeps a savings record and relearns faster than a never-seen one (E13 direction)')

    # Near transfer only (E24).
    w = world(overrides=NO_SHIFT)
    run(w, 'p0', 'salsa dancing', [0, 1, 2, 3, 4, 5], attention=1)
    assert skills.transfer_boost(w, 'p0', 'opera singing', 5) == 1.0
    assert skills.transfer_boost(w, 'p0', 'salsa dancing lessons', 5) > 1.0
    checks.append('near transfer only: a related skill speeds learning; below the similarity cutoff the boost is exactly zero')

    # Feedback moderator (E21).
    def gain(feedback):
        w = world(overrides=NO_SHIFT)
        return run(w, 'p0', 'chess', [0], feedback=feedback, attention=1)[0]['level']
    assert gain('task') >= gain('none') >= gain('self')
    checks.append('task-focused feedback gives at least the gain of none, self-focused at most (E21 direction)')

    # Self-perception calibrated to r = .29 (E22) in a reference population of new skills.
    w = world(n=1)
    rng = np.random.default_rng(3)
    true_levels, seen = [], []
    for i in range(1500):
        key = f'skill {i}'
        skills.create(w, 'p0', key, 0)
        w.agent('p0')['skills'][skills.normalize_label(key)]['L'] = float(rng.random())
        true_levels.append(skills.level(w, 'p0', key, 0))
        seen.append(skills.perceived(w, 'p0', key, f'q{i}', 0))
    w.state['config']['skills']['max_skills_per_agent'] = 200
    r = float(np.corrcoef(true_levels, seen)[0, 1])
    assert abs(r - .29) < .06, r
    checks.append(f'perceived skill correlates r = {r:.2f} with true skill across a reference population (target .29, E22); '
                  'no built-in overconfidence')

    # Determinism, and seeding purposes are independent.
    def history(seed=5, swap=None):
        w = world(seed=seed, overrides=NO_SHIFT)  # shift draws are still made, so their seeding can be swapped in isolation
        real = skills.rng
        with patch('devsim.skills.rng', lambda engine, owner, key, purpose: real(engine, owner, (key, 'x') if purpose == swap else key, purpose)):
            run(w, 'p0', 'kite flying', [0, 1, 2, 3, 4, 5, 6, 7])
        return w.agent('p0')['skills'][skills.normalize_label('kite flying')]
    one, two = history(), history()
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)
    shifted = history(swap='strategy_shift')
    assert (shifted['alpha'], shifted['S0']) == (one['alpha'], one['S0']) and [x['success'] for x in shifted['log']] == [x['success'] for x in one['log']]
    assert [x['shift_u'] for x in shifted['log']] != [x['shift_u'] for x in one['log']]
    assert history(seed=6)['alpha'] != one['alpha']
    checks.append('the same seed and events give byte-identical states and logs; changing one seeding purpose changes only its own draws')

    # No special-casing and no skill list.
    source = Path(skills.__file__).read_text()
    tree = ast.parse(source)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    strings = ' '.join(n.value.lower() for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str))
    assert not names & {'agent_type', 'archetype', 'role', 'sex', 'gender', 'occupation'}
    assert not re.search(r'\b(dancing|singing|typing|cooking|chess|piano|robot|football|dsa)\b', strings)
    def outcome(names=None, facts=None):
        w = world(n=2, names=names, facts=facts)
        for p in ('p0', 'p1'):
            run(w, p, 'pottery', [0, 1, 2, 3])
        return {p: w.agent(p)['skills'] for p in ('p0', 'p1')}
    assert outcome() == outcome(names={'p0': 'Zed'}, facts={'p0': {'occupation': 'potter', 'sex': 'f'}})
    checks.append('no type, role, sex, occupation or name branch and no list of skills in the module; renaming people or adding '
                  'identity facts changes nothing')

    # Cost: nothing runs while idle; reads are O(1); no added model calls.
    w = world()
    run(w, 'p0', 'knitting', [0])
    calls = []
    with patch('devsim.skills.practice', side_effect=lambda *a, **k: calls.append('practice')), \
            patch('devsim.skills.apply', side_effect=lambda *a, **k: calls.append('apply')):
        Lifetime(w, {'sampling': 'event_driven', 'opportunities': [], 'skills': {}}, scripted=True).run(200)
    assert not calls
    from checks.check_household import fixture, stub
    counts = []
    for extra in ({}, {'skills': {}}):
        f, policy = fixture()
        made = []
        with patch('devsim.engine.request_json', side_effect=lambda *a, **k: made.append(1) or stub(*a, **k)):
            Lifetime(f, {**policy, **extra}).run(.8)
        counts.append(len(made))
    assert counts[0] == counts[1] > 0
    checks.append(f'a long idle stretch performs no skill computation; a stubbed run makes the same model calls with and without '
                  f'the module ({counts[0]})')

    # E2 mechanism: gamma-rate exponentials look exponential alone and power-law on average.
    w = world(n=1, overrides={**NO_SHIFT, 'aptitude_mode': 'off', 'ceiling0': 1.0})
    trials = np.arange(1, 81)
    curves = []
    for i in range(300):
        key = f'motor task {i}'
        curve = []
        for n in trials:
            curve.append(skills.practice(w, 'p0', key, f'{key}:{n}', t=0, attention=1)['level'])
        curves.append(curve)
    noise = np.random.default_rng(7).normal(0, .005, (300, len(trials)))
    individual = [fit_aic(trials, np.array(c) + z) for c, z in zip(curves[:40], noise[:40])]
    share = sum(x < y for x, y in individual) / len(individual)
    mean = np.mean(curves, axis=0)
    pop_exp, pop_pow = fit_aic(trials, mean)
    assert share > .7 and pop_pow < pop_exp, (share, pop_exp, pop_pow)
    checks.append(f'with gamma-distributed rates, {share:.0%} of individual curves fit an exponential better than a power function '
                  f'(AIC) while the population mean fits a power function better (E2 mechanism, not the science)')

    # Strategy shifts: visible jumps in individuals, a smooth mean.
    w = world(n=1, overrides={'h_shift': .2, 'aptitude_mode': 'off'})
    curves = []
    for i in range(200):
        key = f'puzzle {i}'
        curves.append([skills.practice(w, 'p0', key, f'{key}:{n}', t=0, attention=1)['level'] for n in range(40)])
    curves = np.array(curves)
    drops = (np.diff(curves, axis=1) < -1e-9).sum()
    smooth = np.abs(np.diff(curves.mean(axis=0), 2)).max()
    assert drops > 50 and smooth < .02, (drops, smooth)
    checks.append(f'strategy shifts make visible dips in individual curves ({drops} across 200 learners) while the population '
                  f'mean stays smooth (largest second difference {smooth:.3f})')

    # Busy novice vs gifted idle: practice volume alone does not decide level.
    w = world(n=30, overrides=NO_SHIFT)
    rows = []
    for i in range(30):
        n = 3 + (i * 7) % 25
        run(w, f'p{i}', 'drawing', [k * .5 for k in range(n)], attention=1)
        rows.append((n, skills.level(w, f'p{i}', 'drawing', n * .5)))
    inverted = sum(1 for a in rows for b in rows if a[0] < b[0] and a[1] > b[1])
    assert inverted > 0
    checks.append(f'practice volume alone does not decide level: {inverted} pairs where the one who practised less is better '
                  '(aptitude and per-skill draws matter, E25)')

    # Tired but practising: performance dips, stored skill does not.
    w = world(overrides=NO_SHIFT)
    run(w, 'p0', 'typing practice', [0, 1, 2, 3, 4], attention=1)
    stored = skills.level(w, 'p0', 'typing practice', 5)
    tired = skills.performance(w, 'p0', 'typing practice', 5, ctx=(.2, .95))
    rested = skills.performance(w, 'p0', 'typing practice', 5, ctx=(0.0, 0.0))
    assert tired < stored == rested == skills.level(w, 'p0', 'typing practice', 5)
    checks.append('high sleep pressure lowers performance below stored skill, which does not change; rested performance equals it')

    # Competence gate: below the threshold the model is told how not knowing feels, never to be wrong; the log decides.
    w = world()
    check = skills.competence_check(w, 'p0', 'heart surgery', .4, 'gate-1')
    text = skills.skill_directive(skills.cfg(w), check['tier'], check['passed'])
    assert check == {'skill': 'heart surgery', 'tier': 'none', 'performance': 0.0, 'passed': False}
    assert 'do not know' in text and not re.search(r'\b(wrong|incorrect|false|mislead|fabricate)\b', text.lower().replace('never invent', ''))
    assert w.state['skill_checks'][-1]['event'] == 'gate-1'
    situation = {'id': 'fix', 'actor': 'p0', 'situation': 'The robot is broken.', 'rate_per_year': 365 * 4,
                 'options': [{'id': 'try', 'label': 'Try to fix it', 'success_probability': 1.0, 'valence_success': .6,
                              'valence_failure': -.6, 'success_text': 'I fixed it.', 'failure_text': 'I could not fix it.',
                              'skill': {'key': 'robot repair', 'difficulty': .9}}]}
    w = world(hormones=True)
    Lifetime(w, {'sampling': 'event_driven', 'opportunities': [situation], 'skills': {}, 'hormones': {}}, scripted=True).run(2)
    tries = [c for c in w.state['skill_checks'] if c['skill'] == 'robot repair']
    texts = [o.text for o in w.world.observations['p0'] if o.event_id.endswith('-fix')]
    assert tries and all(not c['passed'] for c in tries) and texts and all(t == 'I could not fix it.' for t in texts)
    assert w.agent('p0')['expectations']['skill:robot repair']['V'] < .15
    checks.append('the competence gate decides success outside the model (a novice fails a hard repair although the scenario '
                  'said 100%), logs every check, and its directive describes not knowing without asking for wrong content')

    # Emergent abandonment: repeated failure lowers wanting until the softmax stops choosing it.
    from devsim import hormones
    w = world(hormones=True)
    picks = []
    for k in range(25):
        hormones.learn(w, 'p0', 'skill:violin', -.6, 1.0, hormones.context(w, 'p0'))
        picks.append(hormones.choose(w, 'p0', ['skill:violin', 'skill:painting'], f'pick{k}'))
    want = skills.practice_wanting(w, 'p0', ['violin', 'painting'])
    later = [hormones.choose(w, 'p0', ['skill:violin', 'skill:painting'], f'later{k}') for k in range(300)]
    share = later.count('skill:violin') / len(later)
    assert want['violin'] < want['painting'] and share < .05, share
    checks.append(f'abandonment emerges: repeated failure lowers the learned value and wanting, and the softmax then picks that '
                  f'practice only {share:.0%} of the time (no abandonment hazard exists)')

    # Sensitivity sweep over [U] parameters.
    def scenario(overrides):
        w = world(overrides={**NO_SHIFT, **overrides})
        run(w, 'p0', 'sweep skill', [0, 2, 4, 6, 8], attention=1)
        return {'level_at_8': skills.level(w, 'p0', 'sweep skill', 8), 'level_at_60': skills.level(w, 'p0', 'sweep skill', 60)}
    report = skills.sensitivity_sweep(scenario, {'alpha_mean': [.05, .15, .4], 'k_s': [.5, 1.2, 3], 's0_mean_days': [1, 3, 10]})
    assert set(report) == {'alpha_mean', 'k_s', 's0_mean_days'} and report['alpha_mean']['level_at_8'][0] < report['alpha_mean']['level_at_8'][1]
    RESULTS_DIR.joinpath('skills-sensitivity.json').write_text(json.dumps(report, indent=2) + '\n')
    checks.append('a sensitivity sweep reports outcome ranges across placeholder parameters (results/skills-sensitivity.json)')

    result = {'passed': True, 'scope': 'skill module engineering checks; [U] magnitudes are placeholders, see docs/PARAMETERS.md',
              'checks': checks}
    RESULTS_DIR.joinpath('skills-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
