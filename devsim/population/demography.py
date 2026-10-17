"""Demography and joint events (design v2, build steps 4, 5 and 9's mortality link).

An unobserved stretch of a life is resolved by competing-risk hazards, piecewise constant over one-year age bands:
P(no event in [t0, t1]) = exp(-integral of the summed rates), so the next event time comes from one exponential
draw per event and its kind from the rates at that moment. Draws are keyed by (person, event number), so a life
resolved in one call or many has the same history. Marriage is a joint event: the husband comes from the implicit
population by compatibility and must be alive and free at that time and later (exact conditioning by rejection).
Calibration: the marriage scale is fitted only to the median age at first marriage, the fertility scale only to
adolescent fertility (NFHS-5 Maharashtra); the share married before 18 and total fertility are left as checks.
"""
from functools import lru_cache
from math import exp, log, sqrt

from .core import TRAITS, uniform

YEAR = 365.25


def _integral(f, lo, hi, steps=400):
    if hi <= lo:
        return 0.0
    width = (hi - lo) / steps
    return width * sum(f(lo + (k + .5) * width) for k in range(steps))


class Calibration:
    """Closed-form scales derived once from the config's anchors."""

    def __init__(self, cfg):
        self.cfg = cfg
        a, b, c, d = cfg['marriage_ramp_women']
        self.shape = lambda age: 0.0 if age < a else (age - a) / (b - a) if age < b else 1.0 if age < c else exp(-(age - c) / d)
        banded = lambda f: (lambda age: f(int(age) + .5))  # the same one-year bands the hazards use
        self.marriage_scale = log(2) / _integral(banded(self.shape), 0, cfg['median_age_first_marriage_women'])
        lo, flat, hi = cfg['fertility_shape']
        self.fertility = lambda age: 0.0 if age < lo or age >= hi else 1.0 if age < flat else (hi - age) / (hi - flat)
        married = lambda age: 1 - exp(-self.marriage_scale * _integral(banded(self.shape), 0, age, 100))
        teen = _integral(lambda age: married(age) * banded(self.fertility)(age), 15, 20, 50) / 5
        self.fertility_scale = cfg['adolescent_fertility_per_1000'] / 1000 / teen if teen else 0.0
        self.infant = -log(1 - cfg['infant_mortality_per_1000'] / 1000)
        self.child = -log((1 - cfg['under5_mortality_per_1000'] / 1000) / (1 - cfg['infant_mortality_per_1000'] / 1000)) / 4

    def mortality(self, age):
        if age < 1:
            return self.infant
        if age < 5:
            return self.child
        A, B, C = self.cfg['gompertz_makeham']
        return A + B * exp(C * age)


def initial_status(pop, pid):
    return {'t': pop.person(pid)['birth_day'], 'alive': True, 'death': None, 'spouse': None, 'widowed': False,
            'parity': 0, 'last_birth': None, 'events': 0, 'used': 0.0, 'job': None}


def isolation(pop, pid, t):
    """1 - integration index: base tie strengths weighted by tier, minus partners known dead or ties ruptured by t.
    shortcut: base strengths (not resolved contact histories) keep demography from recursing through every
    neighbor's life; resolve ties exactly if the mortality link ever needs it."""
    from .ties import base_tie
    cfg = pop.cfg
    strengths = []
    for other in pop.base_neighbors(pid):
        dead = pop.death_day(other, resolve=False)
        record = pop.state['ties'].get('|'.join(sorted((pid, other))))
        if (dead is not None and dead <= t) or (record and record['ruptured'] is not None and record['ruptured'] <= t):
            continue
        strengths.append(base_tie(pop, pid, other)['s0'])
    strengths.sort(reverse=True)
    cutoffs, weights = cfg['tiers'], cfg['integration_tier_weights']
    total = sum(s * weights[sum(rank >= c for c in cutoffs)] for rank, s in enumerate(strengths))
    return 1 - min(1.0, total / cfg['integration_reference'])


def rates(pop, pid, status, t, cal, isolated):
    """Event hazards per year at time t for this status."""
    cfg, p = pop.cfg, pop.person(pid)
    if pid in pop.state['bound']:
        return {}  # an engine character's life is decided by the engine, not by these hazards
    # Piecewise constant over one-year age bands (evaluated at the band's middle), so how a life is split into
    # resolution calls never changes its hazards.
    age = int((t - p['birth_day']) / YEAR) + .5
    result = {}
    job = status.get('job')
    if job in ('unemployed', 'informal', 'formal'):
        effects, traits = cfg['job_trait_effects'], p['traits']
        for key, rate in cfg['job_rates_per_year'].items():
            source, target = key.split('>')
            if source == job:
                entry = target != 'unemployed' and (source == 'unemployed' or target == 'formal')
                result['job:' + target] = rate * exp(effects['C_entry'] * traits['C'] if entry else effects['N_loss'] * traits['N'] if target == 'unemployed' else 0)
    seen = max([pop.state['start_day'] if pop.is_base(pid) else -1e18] +
               [f['t'] for f in pop.facts(pid, 'seen_alive') if f['committed']])
    if t >= seen:  # exact conditioning on survival: base people are alive at the start, anyone seen is alive then
        multiplier = exp(isolated * log(cfg['isolation_odds_ratio']) * (cfg['isolation_under65_factor'] if age < 65 else 1))
        result['death'] = cal.mortality(age) * multiplier
    if p['sex'] == 'F':
        husband = status['spouse']
        free = husband is None or not pop.alive(husband, t)
        single_until = max([f['t'] for f in pop.facts(pid, 'seen_single') if f['committed']], default=-1e18)
        if free and t >= single_until:
            result['marriage'] = cal.marriage_scale * cal.shape(age) * (cfg['remarriage_factor'] if status['widowed'] or husband else 1)
        elif status['last_birth'] is None or t >= status['last_birth'] + cfg['birth_interval_years'] * YEAR:
            factors = cfg['parity_factors']
            result['birth'] = cal.fertility_scale * cal.fertility(age) * factors[min(status['parity'], len(factors) - 1)]
    return {k: v for k, v in result.items() if v > 0}


def resolve(pop, pid, until):
    """Advance this person's life to `until` (days); returns the status. Joint facts written by others apply too."""
    status = pop.state['status'].get(pid)
    if status is None:
        status = initial_status(pop, pid)
        for fact in pop.facts(pid):  # rebuild after a rollback or load: replay logged demographic facts
            if fact['kind'] in ('marriage', 'birth', 'death', 'job_change') and fact['t'] <= until:
                _apply(pop, pid, status, fact)
        pop.state['status'][pid] = status
    if not status['alive'] or until <= status['t']:
        return status
    cal = pop.calibration
    while status['alive'] and status['t'] < until:
        t = status['t']
        age = pop.age(pid, t)
        if 18 <= age < 60 and status.get('job') in (None, 'none'):
            u, shares, job = uniform(pop.seed, 'job-entry', pid), pop.cfg['job_initial_shares'], 'formal'
            for job, share in zip(('unemployed', 'informal', 'formal'), shares):
                if u < share:
                    break
                u -= share
            status['job'] = job
        elif age >= 60 and status.get('job') not in (None, 'retired'):
            status['job'] = 'retired'
        incoming = [f for f in pop.facts(pid) if f['kind'] in ('marriage', 'birth') and t < f['t'] <= until
                    and pid not in (f['data'].get('initiator'), f['data'].get('mother'))]
        stop = min([until, (int(pop.age(pid, t)) + 1) * YEAR + pop.person(pid)['birth_day']] +
                   [f['t'] for f in incoming] +
                   ([status['last_birth'] + pop.cfg['birth_interval_years'] * YEAR] if status['last_birth'] and
                    status['last_birth'] + pop.cfg['birth_interval_years'] * YEAR > t else []) +
                   ([pop.state['start_day']] if t < pop.state['start_day'] else []))
        stop = max(stop, t + 1e-9)
        if t >= pop.state['start_day'] and status.get('iso_at') != status['events']:
            # Isolation is taken at the start of each event search and kept until the person's next event, so a life
            # resolved in one call or many sees the same values. Time spent isolated since the last value raises
            # threat sensitivity slowly (design default; no verified effect size).
            if status.get('iso_t') is not None and status.get('iso', 0) > 0 and pid not in pop.state['bound']:
                drift = pop.cfg['isolation_threat_per_year'] * status['iso'] * (t - status['iso_t']) / YEAR
                if drift > 1e-4:
                    pop.add_fact(t, 'dial_shift', (pid,), {'shift': {'threat_sensitivity': drift}, 'cause': 'isolation'})
            status.update(iso=pop.isolation(pid, t), iso_at=status['events'], iso_t=t)
        current = rates(pop, pid, status, t, cal, status.get('iso', 0.0) if t >= pop.state['start_day'] else 0.0)
        total = sum(current.values())
        need = -log(uniform(pop.seed, 'demo-E', pid, status['events'])) - status['used']
        span = (stop - t) / YEAR
        if total * span < need:
            status.update(t=stop, used=status['used'] + total * span)
            for fact in incoming:
                if fact['t'] <= stop:
                    _apply(pop, pid, status, fact)
            continue
        when = t + need / total * YEAR
        u, kind = uniform(pop.seed, 'demo-kind', pid, status['events']) * total, None
        for kind, rate in sorted(current.items()):
            if u < rate:
                break
            u -= rate
        status.update(t=when, used=0.0, events=status['events'] + 1)
        _event(pop, pid, status, kind, when)
    return status


def _apply(pop, pid, status, fact):
    if fact['kind'] == 'death':
        status.update(alive=False, death=fact['t'])
    elif fact['kind'] == 'marriage':
        status.update(spouse=next(w for w in fact['who'] if w != pid), widowed=False)
    elif fact['kind'] == 'job_change':
        status['job'] = fact['data']['to']
    elif fact['kind'] == 'birth' and fact['data']['mother'] == pid:
        status.update(parity=status['parity'] + 1, last_birth=fact['t'])
    status['t'] = max(status['t'], fact['t'])


def _event(pop, pid, status, kind, when):
    if kind.startswith('job:'):
        target = kind[4:]
        pop.add_fact(when, 'job_change', (pid,), {'from': status['job'], 'to': target})
        if target == 'unemployed' and when >= pop.state['start_day']:
            pop.add_fact(when, 'dial_shift', (pid,), {'shift': pop.cfg['job_loss_shift'], 'cause': 'job_loss'})
        status['job'] = target
    elif kind == 'death':
        pop.add_fact(when, 'death', (pid,))
        status.update(alive=False, death=when)
        if when >= pop.state['start_day']:
            grieve(pop, pid, when)
    elif kind == 'marriage':
        husband = choose_spouse(pop, pid, when, status['events'])
        if husband is None:
            return  # nobody eligible nearby: the hazard simply did not lead to a marriage this time
        if status['spouse']:
            status['widowed'] = True
        pop.add_fact(when, 'marriage', (pid, husband), {'initiator': pid})
        status['spouse'] = husband
        if husband in pop.state['status']:
            pop.state['status'][husband]['spouse'] = pid
    elif kind == 'birth':
        father = status['spouse']
        if when < pop.state['start_day']:
            pop.add_fact(when, 'birth', (pid, father), {'mother': pid, 'father': father, 'child': None})
        else:  # a new person: lives in the mother's household and cell
            child = f'{pid}.{status["parity"]}'
            pop.add_fact(when, 'birth', (pid, father, child), {'mother': pid, 'father': father, 'child': child})
            pop.state['born'].setdefault(str(pop.person(pid)['cell']), []).append(child)
        status.update(parity=status['parity'] + 1, last_birth=when)


def choose_spouse(pop, woman, when, n):
    """Joint resolution: a husband from the implicit population by compatibility and age gap, alive and unmarried
    at `when` with no later marriage in his own log (a draw that contradicts his facts is rejected)."""
    cfg = pop.cfg
    mean, sd, low, high = cfg['spouse_age_gap']
    w_age = pop.age(woman, when)
    w_latent = pop.latent(woman)
    weighted = []
    for man in sorted(pop.candidates(woman)):
        p = pop.person(man)
        gap = pop.age(man, when) - w_age
        if p['sex'] != 'M' or not low <= gap <= high or not pop.is_base(man) and pop.age(man, when) < 18:
            continue
        distance = sqrt(sum((x - y) ** 2 for x, y in zip(pop.latent(man), w_latent)))
        weighted.append((exp(-distance / cfg['spouse_latent_scale'] - ((gap - mean) / sd) ** 2 / 2), man))
    attempt = 0
    while weighted and attempt < 12:
        total = sum(w for w, _ in weighted)
        u = uniform(pop.seed, 'spouse', woman, n, attempt) * total
        for k, (w, man) in enumerate(weighted):
            u -= w
            if u <= 0:
                break
        marriages = pop.facts(man, 'marriage')
        future = any(f['t'] >= when for f in marriages)
        taken = any(pop.alive(next(x for x in f['who'] if x != man), when) for f in marriages if f['t'] < when)
        single = any(f['t'] >= when for f in pop.facts(man, 'seen_single') if f['committed'])
        if pop.alive(man, when) and not taken and not future and not single:
            return man
        weighted.pop(k)
        attempt += 1
    return None


@lru_cache(maxsize=64)
def calibration_for(config_json):
    import json
    return Calibration(json.loads(config_json))


def observe(pop, pid, t, kind):
    """A committed observation from the foreground ('seen_alive' or 'seen_single' at day t). Latent facts that
    contradict it are rolled back (with their joint partners' slices) and the life is resampled under the new
    constraint. Contradicting a committed fact is an error: committed facts are never rolled back."""
    if kind not in ('seen_alive', 'seen_single'):
        raise ValueError('Observations are seen_alive or seen_single')
    resolve(pop, pid, t)
    if kind == 'seen_alive':
        conflict = [f for f in pop.facts(pid, 'death') if f['t'] <= t]
    else:
        conflict = [f for f in pop.facts(pid, 'marriage') if f['t'] <= t and pop.alive(next(x for x in f['who'] if x != pid), t)]
    if conflict:
        pop.rollback(pid, min(f['t'] for f in conflict))
    fact = pop.add_fact(t, kind, (pid,), committed=True)
    resolve(pop, pid, t)
    return fact


def grieve(pop, dead, when):
    """Close survivors take a grief shock to their mood baseline, scaled by the tie and buffered by their remaining
    closest ties; each loss is also logged as a 'tie_lost' fact (the memory hook for engine characters)."""
    from .ties import base_tie
    for survivor in pop.base_neighbors(dead):
        s0 = base_tie(pop, dead, survivor)['s0']
        if s0 < .3 or pop.death_day(survivor) is not None and pop.death_day(survivor) <= when:
            continue
        others = sorted((base_tie(pop, survivor, o)['s0'] for o in pop.base_neighbors(survivor) if o != dead), reverse=True)[:5]
        buffer = sum(others) / 5
        pop.add_fact(when, 'tie_lost', (survivor, dead), {'strength': s0})
        pop.add_fact(when, 'dial_shift', (survivor,), {'shift': {'mood_baseline_shift': pop.cfg['grief_mood_shift'] * s0 * (1 - buffer)},
                                                         'cause': 'grief'})
