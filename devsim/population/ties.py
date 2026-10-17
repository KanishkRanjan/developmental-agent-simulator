"""Tie strength and recontact (design v2, build step 3).

Strength decays in closed form between contacts with the memory forgetting curve,
s(dt) = floor + (s_last - floor) * (1 + dt / 9S)^-1; a friendly contact restores the tie to its peak (its closeness),
resets dt and multiplies S (the rehearsal rule); a hostile one lowers the peak.
Kin get a higher floor and a longer S (Roberts & Dunbar 2011, V for the direction only). Contacts are a hazard,
drawn only when the pair is asked about: candidate events come from per-year buckets at a capped rate and are
thinned to the current rate, so the realized history is the same whatever times the pair is queried at.
"""
from math import exp, floor as floor_of

from .core import clip, normal, tie_key, uniform
from statistics import NormalDist

YEAR = 365.25
_NORMAL = NormalDist()


def _poisson(mean, u):
    """Inverse-CDF Poisson draw from one uniform (normal approximation above mean 60)."""
    if mean > 60:
        return max(0, round(mean + mean ** .5 * _NORMAL.inv_cdf(u)))
    k, p = 0, exp(-mean)
    total = p
    while u > total and k < 10 * mean + 50:
        k += 1
        p *= mean / k
        total += p
    return k


def base_tie(pop, a, b):
    cfg, seed = pop.cfg, pop.seed
    key = tie_key(a, b)
    kin = pop.kin(a, b)
    if kin:
        s0 = cfg['strength_kin']
    else:
        closeness = pop.edge_probability(a, b)  # higher for nearer, more similar, more sociable pairs
        s0 = clip(cfg['strength_friend_mean'] * (.6 + .8 * closeness) * (.6 + .8 * uniform(seed, 'tie-s0', key)), .02, .95)
    pa, pb = pop.person(a), pop.person(b)
    stability = (cfg['stability_kin_days'] if kin else cfg['stability_friend_days']) * \
        exp(cfg['stability_conscientiousness'] * (pa['traits']['C'] + pb['traits']['C']) / 2)
    return {'kin': kin, 's0': s0, 'peak': s0, 's_last': s0, 'S': min(cfg['stability_max_days'], stability),
            'last': pop.state['start_day'] - (3 if kin else 30) * uniform(seed, 'tie-last', key),
            'arousal': .1 + .4 * uniform(seed, 'tie-arousal', key), 'valence': clip(.25 + .35 * normal(seed, 'tie-valence', key), -1, 1),
            'hostile': 0, 'contacts': 0, 'ruptured': None, 'resolved': pop.state['start_day']}


def strength_at(cfg, tie, t):
    if tie['ruptured'] is not None:
        return 0.0
    low = cfg['s_floor_kin'] if tie['kin'] else cfg['s_floor_friend']
    return low + (tie['s_last'] - low) / (1 + max(0.0, t - tie['last']) / (9 * tie['S']))


def _rates(pop, a, b, tie, dials):
    """Friendly, hostile and reconciliation hazards per year, from each side's personality and the shared memory."""
    cfg = pop.cfg
    negative = max(0.0, -tie['valence'])
    base = cfg['contact_rate_max_per_year'] * tie['s0'] ** cfg['contact_rate_exponent'] / 2
    friendly = hostile = 0.0
    for me in (a, b):
        e = pop.person(me)['traits']['E']
        friendly += base * exp(cfg['contact_extraversion'] * e) * (1 + cfg['contact_arousal_gain'] * tie['arousal']) \
            * exp(-cfg['avoidance'] * dials[me]['threat_sensitivity'] * negative)
        hostile += cfg['hostile_rate_per_year'] * dials[me]['dysregulation'] * negative
    reconcile = cfg['reconcile_rate_per_year'] * tie.get('strength_before_rupture', 0) if tie['ruptured'] is not None else 0.0
    return friendly, hostile, reconcile


def _cap(pop, a, b, tie):
    cfg = pop.cfg
    base = cfg['contact_rate_max_per_year'] * tie['s0'] ** cfg['contact_rate_exponent'] / 2
    friendly = sum(base * exp(cfg['contact_extraversion'] * pop.person(me)['traits']['E']) * (1 + cfg['contact_arousal_gain'] * tie['arousal'])
                   for me in (a, b))
    return max(friendly + 2 * cfg['hostile_rate_per_year'], cfg['reconcile_rate_per_year'], 1e-9)


def tie(pop, a, b, until=None):
    """The pair's tie resolved up to `until` (default: as far as already resolved). Stored once touched."""
    key = tie_key(a, b)
    record = pop.state['ties'].get(key)
    if record is None:
        record = base_tie(pop, a, b)
    if until is not None and until > record['resolved']:
        record = dict(record)
        _resolve(pop, a, b, record, until)
        pop.state['ties'][key] = record
    return record


def _resolve(pop, a, b, record, until, quiet=False):
    """Replay candidate events in (resolved, until] in time order, thinning each to the hazard at that moment.
    quiet=True looks ahead on a copy without logging facts."""
    cfg, seed, key = pop.cfg, pop.seed, tie_key(a, b)
    a, b = sorted((a, b))
    end = min([until] + [d for d in (pop.death_day(a), pop.death_day(b)) if d is not None])
    cap = _cap(pop, a, b, record)
    start = record['resolved']
    for bucket in range(floor_of(start / YEAR), floor_of(max(start, end) / YEAR) + 1):
        lo, hi = bucket * YEAR, (bucket + 1) * YEAR
        count = _poisson(cap, uniform(seed, 'tie-count', key, bucket))
        times = sorted((lo + YEAR * uniform(seed, 'tie-time', key, bucket, n), n) for n in range(count))
        for t, n in times:
            if t <= start or t > end or t > hi:
                continue
            dials = {me: pop.dials(me, t) for me in (a, b)}
            friendly, hostile, reconcile = _rates(pop, a, b, record, dials)
            u = uniform(seed, 'tie-kind', key, bucket, n) * cap
            if record['ruptured'] is not None:
                if u < reconcile:
                    record.update(ruptured=None, s_last=record['strength_before_rupture'] / 2, last=t)
                    quiet or pop.add_fact(t, 'reconciled', (a, b))
                continue
            if u < friendly:
                record.update(s_last=record['peak'], S=min(cfg['stability_max_days'], record['S'] * (1 + cfg['contact_rehearsal_gain'])),
                              last=t, contacts=record['contacts'] + 1, valence=clip(record['valence'] + cfg['valence_friendly_gain'], -1, 1))
            elif u < friendly + hostile:
                s = strength_at(cfg, record, t)
                low = cfg['s_floor_kin'] if record['kin'] else cfg['s_floor_friend']
                record['peak'] = max(low, record['peak'] - cfg['contact_boost'])
                record.update(s_last=record['peak'], last=t, hostile=record['hostile'] + 1,
                              valence=clip(record['valence'] - cfg['valence_hostile_drop'], -1, 1))
                quiet or pop.add_fact(t, 'hostile_contact', (a, b))
                if uniform(seed, 'tie-rupture', key, bucket, n) < 1 - exp(-cfg['rupture_per_hostile'] * record['hostile']):
                    record.update(ruptured=t, strength_before_rupture=s)
                    quiet or pop.add_fact(t, 'tie_ruptured', (a, b))
    record['resolved'] = max(start, until)


def strength(pop, a, b, t):
    return strength_at(pop.cfg, tie(pop, a, b, t), t)


def neighbors(pop, pid, t):
    """This person's ties at t, strongest first, each with its tier (Dunbar-style rank bands, not targets)."""
    rows = []
    for other in pop.base_neighbors(pid):
        record = tie(pop, pid, other, t)
        rows.append({'id': other, 'strength': strength_at(pop.cfg, record, t), 'kin': record['kin'],
                     'ruptured': record['ruptured'] is not None, 'alive': pop.alive(other, t),
                     'valence': record['valence'], 'last_contact': record['last']})
    rows.sort(key=lambda r: (-r['strength'], r['id']))
    cutoffs = pop.cfg['tiers']
    for rank, row in enumerate(rows):
        row['tier'] = 1 + sum(rank >= c for c in cutoffs)
    return rows


def contact(pop, a, b, t, *, hostile=False):
    """A contact that happened in the foreground (the engine, a user): applied now and committed."""
    record = tie(pop, a, b, t)
    cfg = pop.cfg
    if hostile:
        record['peak'] = max(cfg['s_floor_kin'] if record['kin'] else cfg['s_floor_friend'], record['peak'] - cfg['contact_boost'])
        record.update(s_last=record['peak'], hostile=record['hostile'] + 1, valence=clip(record['valence'] - cfg['valence_hostile_drop'], -1, 1))
    else:
        record.update(s_last=record['peak'], S=min(cfg['stability_max_days'], record['S'] * (1 + cfg['contact_rehearsal_gain'])),
                      contacts=record['contacts'] + 1, valence=clip(record['valence'] + cfg['valence_friendly_gain'], -1, 1))
    record['last'] = t
    pop.add_fact(t, 'hostile_contact' if hostile else 'contact', (a, b), committed=True)
    return record
