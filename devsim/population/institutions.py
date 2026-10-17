"""Institutions, norms, collective action, income and the opportunity engine (design v2, build steps 7 and 8).

An institution stores rules, a role-size distribution and a membership generator, never a member list: a person
belongs to the institution of each type that a hash of (type, person) picks in their region, when eligible. Roles
go to the best fit (traits plus seniority). Norms are a community's behavior distribution and tightness; every
person's response to sanction comes from one formula over dials and traits (no archetype branch). Collective
action is a threshold cascade over members (Granovetter, unverified here). The opportunity engine compounds:
heavy-tailed opportunities arrive faster for people with more reachable institutions, success multiplies capital,
failure shrinks it (Pluchino, Biondo & Rapisarda 2018, V as a sufficient mechanism, not an explanation).
"""
from math import exp, floor, log

from .core import clip, normal, uniform
from .ties import YEAR, _poisson


def _logistic(x):
    return 1 / (1 + exp(-x))


# Membership and roles (step 7).

def region(pop, pid, kind):
    size = pop.cfg['institution_types'][kind]['region_cells']
    cx, cy = divmod(pop.person(pid)['cell'], pop.grid)
    return cx // size, cy // size


def eligible(pop, pid, kind, t):
    spec = pop.cfg['institution_types'][kind]
    if not pop.alive(pid, t) or not spec['min_age'] <= pop.age(pid, t) < spec['max_age']:
        return False
    return not spec['needs_job'] or pop.resolve(pid, t).get('job') in ('informal', 'formal')


def institution_of(pop, pid, kind, t):
    if not eligible(pop, pid, kind, t):
        return None
    rx, ry = region(pop, pid, kind)
    k = int(uniform(pop.seed, 'institution', kind, pid) * pop.cfg['institution_types'][kind]['per_region'])
    return f'{kind}:{rx}.{ry}:{k}'


def members(pop, institution, t):
    """Enumerate members by scanning only the institution's region (bounded, independent of population size)."""
    kind, place, _ = institution.split(':')
    rx, ry = map(int, place.split('.'))
    size = pop.cfg['institution_types'][kind]['region_cells']
    found = []
    for x in range(rx * size, min(pop.grid, (rx + 1) * size)):
        for y in range(ry * size, min(pop.grid, (ry + 1) * size)):
            cell = x * pop.grid + y
            people = [f'p{i}' for i in range(cell * pop.cell_size, (cell + 1) * pop.cell_size)] + pop.state['born'].get(str(cell), [])
            found += [p for p in people if institution_of(pop, p, kind, t) == institution]
    return found


def roles(pop, institution, t):
    """Role by rank of fit score: role traits plus seniority by age, plus a small personal draw."""
    kind = institution.split(':')[0]
    spec = pop.cfg['institution_types'][kind]
    people = members(pop, institution, t)
    def fit(pid, role):
        traits = pop.person(pid)['traits']
        return sum(w * traits[k] for k, w in spec['role_traits'].get(role, {}).items()) + spec['seniority_per_year'] * pop.age(pid, t) \
            + .3 * normal(pop.seed, 'role', institution, pid)
    result, remaining = {}, list(people)
    for role, share in spec['roles']:
        count = len(people) if role == spec['roles'][-1][0] else max(1 if share > 0 else 0, round(share * len(people)))
        remaining.sort(key=lambda p: (-fit(p, role), p))
        for pid in remaining[:count]:
            result[pid] = role
        remaining = remaining[count:]
    return result


# Norms and sanctions (step 7).

def norm(pop, community):
    low, high = pop.cfg['norm_tightness_range']
    return {'mean': clip(.5 * normal(pop.seed, 'norm-mean', community), -1, 1), 'sd': pop.cfg['norm_sd'],
            'tightness': low + (high - low) * uniform(pop.seed, 'norm-tight', community)}


def sanction_sensitivity(pop, pid):
    """One formula for everyone: dials and traits set how much sanction matters to this person."""
    w, dials, traits = pop.cfg['sanction_sensitivity'], pop.dials(pid), pop.person(pid)['traits']
    return _logistic(w['bias'] + w['threat_sensitivity'] * (dials['threat_sensitivity'] - .25) + w['A'] * traits['A'] + w['C'] * traits['C']
                     + w['dysregulation'] * (dials['dysregulation'] - .15))


def sanction_hazard(pop, community, action, visibility):
    """Per-year hazard of gossip, exclusion or rupture after a visible action at distance from the norm."""
    n = norm(pop, community)
    return pop.cfg['sanction_rate_per_year'] * n['tightness'] * clip(visibility, 0, 1) * abs(action - n['mean']) / n['sd']


def pluralistic_gap(pop, community, private_opinions):
    """Stated norm minus the mean private opinion of members: pluralistic ignorance when large."""
    values = list(private_opinions)
    return norm(pop, community)['mean'] - sum(values) / len(values) if values else 0.0


# Collective action (step 7).

def raise_tension(pop, institution, amount, t):
    pop.add_fact(t, 'tension', (institution,), {'amount': amount})


def tension(pop, institution, t):
    return sum(f['data']['amount'] for f in pop.facts(institution, 'tension') if f['t'] <= t)


def collective_action(pop, institution, t):
    """Threshold cascade: people join once the joined share reaches their threshold minus the tension.
    Returns the equilibrium share and, past the trigger, logs a collective event (committed to the institution)."""
    mean, sd = pop.cfg['collective_threshold']
    people = members(pop, institution, t)
    if not people:
        return 0.0, None
    pressure = tension(pop, institution, t)
    thresholds = sorted(clip(mean + sd * normal(pop.seed, 'threshold', institution, p), 0, 1) - pressure for p in people)
    share = 0.0
    for _ in range(len(people) + 1):
        joined = sum(1 for x in thresholds if x <= share) / len(people)
        if joined <= share:
            break
        share = joined
    event = None
    if share >= pop.cfg['collective_trigger_fraction']:
        joined = [p for p, x in zip(sorted(people, key=lambda p: clip(mean + sd * normal(pop.seed, 'threshold', institution, p), 0, 1)),
                                    thresholds) if x <= share]
        event = pop.add_fact(t, 'collective_event', (institution, *joined[:50]), {'share': share, 'participants': len(joined)})
    return share, event


# Income and the opportunity engine (step 8).

def income(pop, pid, t):
    """Monthly income now: lognormal around the job state's median, fixed per job spell."""
    status = pop.resolve(pid, t)
    median = pop.cfg['income_median_monthly'].get(status.get('job') or 'unemployed', 0)
    spell = len(pop.facts(pid, 'job_change'))
    return median * exp(pop.cfg['income_sigma'] * normal(pop.seed, 'income', pid, spell)) if median else 0.0


def reachable(pop, pid, t):
    """Distinct institutions among this person's ties (knowing the right people)."""
    # shortcut: age eligibility only; checking each tie's job and survival resolves every neighbor's life
    # (about a second per person). Use institution_of per tie if exact reach ever matters.
    found = set()
    for other in pop.base_neighbors(pid)[:60]:
        for kind, spec in pop.cfg['institution_types'].items():
            if spec['min_age'] <= pop.age(other, t) < spec['max_age']:
                rx, ry = region(pop, other, kind)
                found.add((kind, rx, ry, int(uniform(pop.seed, 'institution', kind, other) * spec['per_region'])))
    return len(found)


def capital(pop, pid, until):
    """Capital at `until`, from multiplicative opportunity outcomes since the start (path independent: arrivals
    come from per-year hashed buckets thinned to the person's rate)."""
    cfg, seed = pop.cfg, pop.seed
    record = pop.state.setdefault('capital', {}).get(pid) or {'C': 1.0, 't': pop.state['start_day'], 'wins': 0, 'tries': 0}
    if until <= record['t']:
        return record['C']
    record = dict(record)
    traits, fit = pop.person(pid)['traits'], cfg['opportunity_fit']
    links = reachable(pop, pid, record['t'])
    rate = cfg['opportunity_rate_per_year'] * (1 + cfg['opportunity_reach_gain'] * links)
    chance = _logistic(fit['bias'] + fit['O'] * traits['O'] + fit['C'] * traits['C'] + fit['E'] * traits['E'] + fit['connections'] * log(1 + links))
    allies = _logistic(cfg['cooperation']['bias'] + cfg['cooperation']['A'] * traits['A'])
    death = pop.death_day(pid, resolve=until)
    end = min(until, death) if death else until
    for bucket in range(floor(record['t'] / YEAR), floor(end / YEAR) + 1):
        count = _poisson(rate, uniform(seed, 'opp-count', pid, bucket))
        for n in sorted(range(count), key=lambda n: uniform(seed, 'opp-time', pid, bucket, n)):
            t = bucket * YEAR + YEAR * uniform(seed, 'opp-time', pid, bucket, n)
            if not record['t'] < t <= end:
                continue
            size = uniform(seed, 'opp-size', pid, bucket, n) ** (-1 / cfg['opportunity_size_alpha'])  # Pareto >= 1
            record['tries'] += 1
            if uniform(seed, 'opp-win', pid, bucket, n) < chance * allies:
                record['C'] *= 1 + cfg['capital_gain'] * (size - 1 + .1)
                record['wins'] += 1
            else:
                record['C'] *= 1 - cfg['capital_loss'] * min(1.0, size / 4)
    record['t'] = until
    pop.state['capital'][pid] = record
    return record['C']
