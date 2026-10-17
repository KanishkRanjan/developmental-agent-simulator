"""Society layer core (design v2, build steps 1-2): seeded randomness, the committed-fact log, people and the
implicit graph. Nothing is stored per person until something happens to them: every base attribute and every
possible tie is a pure function of (seed, ids). Numbers come from devsim/policies/society-layer.json.
"""
from functools import lru_cache
from hashlib import sha256
import json
from math import exp, gcd, sqrt
from random import Random
from statistics import NormalDist

from .. import POLICY_DIR

CONFIG_PATH = POLICY_DIR / 'society-layer.json'
TRAITS = 'OCEAN'
DIALS = ('dysregulation', 'mood_baseline_shift', 'threat_sensitivity', 'reality_testing')
DIAL_RANGE = {'dysregulation': (0, 1), 'mood_baseline_shift': (-1, 1), 'threat_sensitivity': (0, 1), 'reality_testing': (0, 1)}
_NORMAL = NormalDist()


def parameters():
    return json.loads(CONFIG_PATH.read_text())['parameters']


def settings(overrides=None):
    """Full config: defaults with overrides, every value checked against its declared range or shape."""
    from ..engine import number
    spec = parameters()
    overrides = overrides or {}
    if not isinstance(overrides, dict) or set(overrides) - set(spec):
        raise ValueError(f'Unknown society-layer setting: {sorted(set(overrides) - set(spec))}')
    result = {key: overrides.get(key, item['value']) for key, item in spec.items()}
    for key, item in spec.items():
        value, default = result[key], item['value']
        if 'range' in item:
            number(value, *item['range'], key)
        elif 'choices' in item:
            if value not in item['choices']:
                raise ValueError(f'{key} must be one of {item["choices"]}')
        elif item.get('items') == 'name':
            if not isinstance(value, list) or len(value) > 20 or not all(isinstance(v, str) and 0 < len(v) <= 40 for v in value):
                raise ValueError(f'{key} must be a list of up to 20 short names')
        elif isinstance(default, list):
            if not isinstance(value, list) or len(value) != len(default) or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
                raise ValueError(f'{key} must be a list of {len(default)} numbers')
        elif isinstance(default, dict) and (not isinstance(value, dict) or set(value) != set(default)):
            raise ValueError(f'{key} must have the keys {sorted(default)}')
    return result


def _digest(keys):
    return sha256(repr(keys).encode()).digest()


def uniform(*keys):
    """A deterministic value in (0, 1) for these keys; no shared random state is consumed."""
    return (int.from_bytes(_digest(keys)[:7], 'big') + .5) / 2 ** 56


def normal(*keys):
    return _NORMAL.inv_cdf(uniform(*keys))


def rng(*keys):
    return Random(int.from_bytes(_digest(keys), 'big'))


def clip(value, low, high):
    return min(high, max(low, value))


def tie_key(a, b):
    return '|'.join(sorted((a, b)))


class Population:
    """The implicit population. `state` is plain JSON (checkpointable); people and base ties are recomputed."""

    def __init__(self, state):
        self.state, self.cfg, self.seed = state, state['config'], state['seed']
        self.grid, self.cell_size = int(self.cfg['grid']), int(self.cfg['cell_size'])
        self.size = self.grid * self.grid * self.cell_size
        self._index = {}
        for n, fact in enumerate(state['log']):
            for who in fact['who']:
                self._index.setdefault(who, []).append(n)
        self._person = lru_cache(maxsize=200_000)(self._make_person)
        self._neighbors, self._calibration = {}, None
        self._permutations = self._make_permutations()

    @classmethod
    def new(cls, seed, start_day=0.0, overrides=None):
        return cls({'version': 1, 'seed': seed, 'start_day': float(start_day), 'config': settings(overrides),
                    'log': [], 'ties': {}, 'status': {}, 'born': {}, 'bound': {}})

    # Step 1: the committed-fact log.

    def add_fact(self, t, kind, who, data=None, committed=False):
        fact = {'id': len(self.state['log']), 't': float(t), 'kind': kind, 'who': list(who), 'data': data or {}, 'committed': committed}
        self.state['log'].append(fact)
        for person in fact['who']:
            self._index.setdefault(person, []).append(fact['id'])
        return fact

    def facts(self, pid, kind=None):
        """This person's facts in time order (the log is append-only; rolled-back facts are marked, never reused)."""
        rows = [self.state['log'][n] for n in self._index.get(pid, [])]
        return sorted((f for f in rows if not f.get('rolled_back') and (kind is None or f['kind'] == kind)), key=lambda f: (f['t'], f['id']))

    def commit(self, pid, until):
        """Shown to the user or read by another agent's model call: this person's facts up to `until` become immutable."""
        for fact in self.facts(pid):
            if fact['t'] <= until:
                fact['committed'] = True
        self.state.setdefault('commit_day', {})[pid] = max(until, self.state.get('commit_day', {}).get(pid, -1e18))

    def rollback(self, pid, from_t):
        """Undo this person's uncommitted facts from `from_t`, and the matching slices of joint partners.
        Committed facts are never rolled back; a conflict with one is an error for the caller."""
        undone, queue = [], [(pid, from_t)]
        while queue:
            who, t = queue.pop()
            for fact in self.facts(who):
                if fact['t'] >= t:
                    if fact['committed']:
                        raise ValueError(f'Cannot roll back committed fact {fact["id"]} ({fact["kind"]})')
                    fact['rolled_back'] = True
                    undone.append(fact['id'])
                    queue += [(other, fact['t']) for other in fact['who'] if other != who]
            self.state['status'].pop(who, None)  # demography re-resolves from the last remaining fact
        return undone

    def horizon(self):
        """Commit horizon (the global-virtual-time analogue): the earliest uncommitted joint fact, else +inf."""
        pending = [f['t'] for f in self.state['log'] if len(f['who']) > 1 and not f['committed'] and not f.get('rolled_back')]
        return min(pending, default=float('inf'))

    # Step 2: people and the implicit graph.

    def is_base(self, pid):
        return '.' not in pid and pid.startswith('p') and pid[1:].isdigit() and int(pid[1:]) < self.size

    def person(self, pid):
        return self._person(pid)

    def _make_person(self, pid):
        cfg, seed = self.cfg, self.seed
        if self.is_base(pid):
            i = int(pid[1:])
            cell = i // self.cell_size
            household = f'h{cell}.{(i % self.cell_size) // int(cfg["household_size"])}'
            weights = cfg['age_band_weights']
            u, band = uniform(seed, 'age', pid) * sum(weights), 0
            while band < len(weights) - 1 and u > weights[band]:
                u -= weights[band]
                band += 1
            age = 10 * band + 10 * uniform(seed, 'age-in-band', pid)
            birth_day = self.state['start_day'] - age * 365.25
            traits = {t: normal(seed, 'trait', pid, t) for t in TRAITS}
            mother = father = None
        else:
            birth = next(f for f in self.facts(pid, 'birth') if f['data'].get('child') == pid)
            mother, father = birth['data']['mother'], birth['data'].get('father')
            parent = self.person(mother)
            cell, household, birth_day = parent['cell'], parent['household'], birth['t']
            other = self.person(father)['traits'] if father else {t: normal(seed, 'trait', pid, 'other', t) for t in TRAITS}
            # shortcut: mid-parent value plus equal-variance noise, a design default (no heritability model here).
            traits = {t: (parent['traits'][t] + other[t]) / 2 + sqrt(.5) * normal(seed, 'trait', pid, t) for t in TRAITS}
        cx, cy = divmod(cell, self.grid)
        dials = {d: clip(cfg['dial_mean'][d] + cfg['dial_sd'][d] * normal(seed, 'dial', pid, d) + cfg['dial_neuroticism'][d] * traits['N'],
                         *DIAL_RANGE[d]) for d in DIALS}
        sigma = cfg['theta_sigma']
        theta = exp(sigma * normal(seed, 'theta', pid) - sigma * sigma / 2 + cfg['theta_extraversion'] * traits['E']
                    + cfg['theta_openness'] * traits['O'])
        person = {'id': pid, 'cell': cell, 'place': (cx + uniform(seed, 'x', pid), cy + uniform(seed, 'y', pid)),
                  'household': household, 'sex': 'F' if uniform(seed, 'sex', pid) < .5 else 'M', 'birth_day': birth_day,
                  'traits': traits, 'dials': dials, 'theta': theta, 'mother': mother, 'father': father}
        person.update(self.state.get('overrides', {}).get(pid, {}))  # an engine character bound to this person
        return person

    def dials(self, pid, t=None):
        """Dials at t (default: latest): base values plus logged shifts (tie loss, isolation, job loss)."""
        values = dict(self.person(pid)['dials'])
        for fact in self.facts(pid, 'dial_shift'):
            if t is not None and fact['t'] > t:
                break
            for d, delta in fact['data']['shift'].items():
                values[d] = clip(values[d] + delta, *DIAL_RANGE[d])
        return values

    def age(self, pid, day):
        return (day - self.person(pid)['birth_day']) / 365.25

    def latent(self, pid, day=None):
        p, cfg = self.person(pid), self.cfg
        age = self.age(pid, self.state['start_day'] if day is None else day)
        return ([cfg['w_place'] * p['place'][0], cfg['w_place'] * p['place'][1], cfg['w_age'] * age]
                + [cfg['w_traits'] * p['traits'][t] for t in TRAITS] + [cfg['w_dials'] * p['dials'][d] for d in DIALS])

    def kin(self, a, b):
        pa, pb = self.person(a), self.person(b)
        return pa['household'] == pb['household'] or b in (pa['mother'], pa['father']) or a in (pb['mother'], pb['father']) \
            or any(set(f['who']) == {a, b} for f in self.facts(a, 'marriage'))

    def edge_probability(self, a, b):
        if self.kin(a, b):
            return 1.0
        xa, xb = self.latent(a), self.latent(b)
        distance = sqrt(sum((u - v) ** 2 for u, v in zip(xa, xb)))
        return min(1.0, self.cfg['kappa'] * self.person(a)['theta'] * self.person(b)['theta'] * exp(-distance / self.cfg['h']))

    def base_edge(self, a, b):
        """The frozen base graph: symmetric, decided by a hash of the pair, free until the pair is asked about."""
        return a != b and uniform(self.seed, 'edge', *sorted((a, b))) < self.edge_probability(a, b)

    def _make_permutations(self):
        result = []
        for r in range(int(self.cfg['long_range_links'])):
            k = 0
            while True:
                a = 1 + int(uniform(self.seed, 'perm-a', r, k) * (self.size - 1))
                if gcd(a, self.size) == 1:
                    break
                k += 1
            result.append((a, int(uniform(self.seed, 'perm-b', r) * self.size), pow(a, -1, self.size)))
        return result

    def candidates(self, pid):
        """Who could be tied to this person: its cell and the 8 around it, long-range permutation partners (both
        directions, so discovery is symmetric), people born nearby, kin and spouses. Never all N people."""
        p = self.person(pid)
        cx, cy = divmod(p['cell'], self.grid)
        found = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < self.grid and 0 <= y < self.grid:
                    cell = x * self.grid + y
                    found.update(f'p{i}' for i in range(cell * self.cell_size, (cell + 1) * self.cell_size))
                    found.update(self.state['born'].get(str(cell), []))
        if self.is_base(pid):
            i = int(pid[1:])
            for a, b, inverse in self._permutations:
                found.update((f'p{(a * i + b) % self.size}', f'p{(inverse * (i - b)) % self.size}'))
        found.update(x for x in (p['mother'], p['father']) if x)
        for fact in self.facts(pid):
            if fact['kind'] in ('marriage', 'birth', 'tie_formed'):
                found.update(fact['who'])
        found.discard(pid)
        return found

    def base_neighbors(self, pid):
        """Ties in the frozen base graph plus kin and logged new ties; ruptures are applied by the tie layer.
        Cached until this person's own facts change (a marriage, birth or new tie can add a neighbor)."""
        version = (len(self._index.get(pid, [])), sum(len(v) for v in self.state['born'].values()))
        cached = self._neighbors.get(pid)
        if cached and cached[0] == version:
            return cached[1]
        result = sorted(j for j in self.candidates(pid) if self.base_edge(pid, j) or
                        any(set(f['who']) == {pid, j} for f in self.facts(pid, 'tie_formed')))
        if len(self._neighbors) > 50_000:
            self._neighbors.clear()
        self._neighbors[pid] = (version, result)
        return result

    # Demography (step 4) and isolation (step 9), in demography.py.

    @property
    def calibration(self):
        if self._calibration is None:
            from .demography import Calibration
            self._calibration = Calibration(self.cfg)
        return self._calibration

    def resolve(self, pid, until):
        from .demography import resolve
        return resolve(self, pid, until)

    def death_day(self, pid, resolve=False):
        """The death day if known (or, with resolve=True, after resolving this life to `resolve`'s day)."""
        status = self.resolve(pid, resolve) if resolve is not False else self.state['status'].get(pid)
        return status['death'] if status else None

    def alive(self, pid, t):
        status = self.resolve(pid, t)
        return status['death'] is None or status['death'] > t

    def observe(self, pid, t, kind):
        from .demography import observe
        return observe(self, pid, t, kind)

    def isolation(self, pid, t):
        from .demography import isolation
        return isolation(self, pid, t)
