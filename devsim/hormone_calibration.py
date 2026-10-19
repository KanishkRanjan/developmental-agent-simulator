"""Population-level calibration harness for the hormone module (no model calls).

    python3 -m devsim.hormone_calibration --agents 300 --out work/hormone-calibration.json

Builds a seeded population with spread Big Five facets and dials, sleeping 23:00-07:00, and runs one standard day
through the module's pure functions: the awakening rise, a standard stressor at 10:00, recovery, sleep pressure at
bedtime and on waking, and onset latency and efficiency on a calm night and after a late stressor. It reports
population summaries and how much of the between-agent spread in stress reactivity and wanting the declared inputs
explain (Big Five, dials, seeded traits) and how much a nuisance input adds (it should add nothing).
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from random import Random

import numpy as np

from . import hormones, sleep
from .engine import Engine, FACET_NAMES

STRESSOR = {'valence': -0.7, 'threat': 0.7 * 0.8, 'controllability': 0.5}


def population(n, seed=11, overrides=None):
    rng = Random(seed)
    e = Engine(seed=seed)
    for i in range(n):
        key = f'p{i}'
        facets = {f: min(100, max(0, rng.gauss(50, 15))) for f in FACET_NAMES}
        e.entity(key, key.title(), {'birth_day': -30 * 365.25, 'sex': rng.choice(['a', 'b'])})  # nuisance fact
        e.materialize(key, facets, birth_day=-30 * 365.25)
        sleep.set_dials(e, key, dysregulation=rng.random() * rng.choice([0, 1]), threat_sensitivity=rng.random() * rng.choice([0, 1]),
                        mood_baseline_shift=rng.uniform(-1, 1) * rng.choice([0, 1]), reality_testing=1 - rng.random() * rng.choice([0, 0, 1]))
    e.state['config']['household'] = {'rooms': {'home': {'label': 'home'}},
                                      'routines': {k: {'available_hours': [[7, 23]]} for k in e.state['agents']}}
    hormones.configure(e, overrides)
    return e


def standard_day(e, owner):
    ctx = hormones.context(e, owner)
    state = hormones.initial(ctx, 0.0)
    wake = 1 + 7 / 24
    minutes = [wake + m / 1440 for m in range(0, 121)]
    car_peak = int(np.argmax([hormones.baseline(ctx, t, False) for t in minutes]))
    at10 = 1 + 10 / 24
    snap = hormones.snapshot(state, ctx, at10)
    dx = hormones.stress_increment(ctx, snap, STRESSOR, 0.8, 0.0, 0)
    now = hormones.advance(state, at10, ctx)
    stressed = hormones.HormoneState(hormones.Level(now.stress_x.value + dx, at10), now.sleep_pressure, now.dopamine_tonic)
    calm_night = hormones.onset(stressed, ctx, 1 + 23 / 24, 2 + 7 / 24)
    late = hormones.advance(stressed, 1 + 22.5 / 24, ctx)
    late_snap = hormones.snapshot(late, ctx, late.stress_x.anchor)
    late_dx = hormones.stress_increment(ctx, late_snap, STRESSOR, 0.8, 0.0, 0)
    wired = hormones.HormoneState(hormones.Level(late.stress_x.value + late_dx, late.stress_x.anchor), late.sleep_pressure, late.dopamine_tonic)
    wired_night = hormones.onset(wired, ctx, 1 + 23 / 24, 2 + 7 / 24)
    closeness = Random(f'{owner}:closeness').random()
    v0, _ = hormones.expectation(e, owner, 'stranger', ctx)
    return {
        'car_peak_minutes': car_peak,
        'reactivity': dx,
        'S_peak': hormones.snapshot(stressed, ctx, at10).stress,
        'S_3h_later': hormones.snapshot(stressed, ctx, at10 + 3 / 24).stress,
        'P_bedtime': hormones.snapshot(stressed, ctx, 1 + 22.99 / 24).sleep_pressure,
        'P_waking': hormones.snapshot(stressed, ctx, 2 + 7 / 24).sleep_pressure,
        'latency_calm_min': (calm_night[0] - (1 + 23 / 24)) * 1440, 'efficiency_calm': calm_night[1],
        'latency_wired_min': (wired_night[0] - (1 + 23 / 24)) * 1440, 'efficiency_wired': wired_night[1],
        'wanting': v0 + ctx['p']['kappa_c'] * closeness + ctx['p']['N0'],
        'inputs': {'N': ctx['traits']['N'], 'O': ctx['traits']['O'], **ctx['dials'],
                   'z_reactivity': hormones.gauss(e.state['seed'], owner, 'trait', 'stress_reactivity'), 'closeness': closeness},
        'nuisance': float(e.state['entities'][owner]['facts']['sex'] == 'a'),
    }


def r2(y, columns):
    X = np.column_stack([np.ones(len(y)), *columns])
    fit, *_ = np.linalg.lstsq(X, y, rcond=None)
    residual = y - X @ fit
    return 1 - residual.var() / y.var()


def calibrate(n=300, seed=11, overrides=None):
    e = population(n, seed, overrides)
    rows = [standard_day(e, owner) for owner in sorted(e.state['agents'])]
    get = lambda key: np.array([r[key] for r in rows])
    inputs = lambda key: np.array([r['inputs'][key] for r in rows])
    p = e.state['config']['hormones']
    reactive = np.log(np.maximum(get('reactivity'), 1e-12))
    threat = STRESSOR['threat']
    declared = [np.log(1 + p['theta_ts'] * inputs('threat_sensitivity')), np.log(1 + p['theta_n'] * inputs('N')),
                np.log(1 + p['dys_gain'] * inputs('dysregulation')), inputs('z_reactivity'),
                np.log(threat + p['rt_bias'] * (1 - inputs('reality_testing')) * (1 - threat) * 0.8)]
    wanting_declared = [inputs('O'), inputs('closeness')]
    summary = lambda key: {'mean': float(get(key).mean()), 'sd': float(get(key).std()),
                           'p05': float(np.percentile(get(key), 5)), 'p95': float(np.percentile(get(key), 95))}
    # The stress readout's (1 - S) factor and the awakening rise are shared by everyone at 10:00, so log-reactivity is
    # linear in the declared terms up to that common offset.
    return {
        'agents': n, 'seed': seed,
        'car_peak_minutes': summary('car_peak_minutes'),
        'reactivity': summary('reactivity'), 'S_peak': summary('S_peak'), 'S_3h_later': summary('S_3h_later'),
        'P_bedtime': summary('P_bedtime'), 'P_waking': summary('P_waking'),
        'latency_calm_min': summary('latency_calm_min'), 'latency_wired_min': summary('latency_wired_min'),
        'efficiency_calm': summary('efficiency_calm'), 'efficiency_wired': summary('efficiency_wired'),
        'reactivity_r2_declared': float(r2(reactive, declared)),
        'reactivity_r2_added_by_nuisance': float(r2(reactive, [*declared, get('nuisance')]) - r2(reactive, declared)),
        'wanting_r2_declared': float(r2(get('wanting'), wanting_declared)),
        'wanting_r2_added_by_nuisance': float(r2(get('wanting'), [*wanting_declared, get('nuisance')]) - r2(get('wanting'), wanting_declared)),
        'scope': 'engineering calibration of design defaults; not empirical validation',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--agents', type=int, default=300)
    parser.add_argument('--seed', type=int, default=11)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = calibrate(args.agents, args.seed)
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
