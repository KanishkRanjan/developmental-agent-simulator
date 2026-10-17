"""Opinion and rumor spread (design v2, build step 6).

Realized people hold opinions in simulation state; everyone else is one mean-field compartment per topic whose
distribution evolves by the same bounded-confidence rule, and a person drawn from it on first query. Conversations
between realized people are a stream of events picked by composition-rejection (Slepoy, Thompson & Plimpton 2008,
V as a method): constant cost per event however many people are active. Each conversation applies a Deffuant
update per topic (only if the two are within epsilon; the move is weighted by the source's credibility, discounted
less for low reality testing) and passes exposures for behaviors and rumors (complex contagion: adoption needs
enough distinct exposing ties within a window). The model never decides an opinion change (see guards.py).
"""
from math import floor, log

from .core import clip, normal, uniform
from .guards import rule_change

YEAR = 365.25


class CompositionRejection:
    """Channels binned by rate in powers of two; pick a bin in proportion to its total, then a channel in it by
    rejection (acceptance at least 1/2). Adding, changing or removing a channel is O(1)."""

    def __init__(self):
        self.bins, self.where, self.rates, self.totals = {}, {}, {}, {}

    @property
    def total(self):
        return sum(self.totals.values())

    def remove(self, cid):
        if cid not in self.where:
            return
        g, k = self.where.pop(cid)
        members = self.bins[g]
        last = members.pop()
        if last != cid:
            members[k] = last
            self.where[last] = (g, k)
        self.totals[g] -= self.rates.pop(cid)
        if not members:
            del self.bins[g], self.totals[g]

    def set(self, cid, rate):
        self.remove(cid)
        if rate <= 0:
            return
        g = floor(log(rate, 2))
        self.bins.setdefault(g, []).append(cid)
        self.where[cid] = (g, len(self.bins[g]) - 1)
        self.rates[cid] = rate
        self.totals[g] = self.totals.get(g, 0.0) + rate

    def select(self, draw):
        """draw(k) -> the k-th uniform for this event."""
        u = draw(0) * self.total
        for g in sorted(self.bins):
            if u < self.totals[g]:
                break
            u -= self.totals[g]
        members, cap = self.bins[g], 2.0 ** (g + 1)
        for attempt in range(1, 1000):
            cid = members[int(draw(2 * attempt - 1) * len(members)) % len(members)]
            if draw(2 * attempt) * cap < self.rates[cid]:
                return cid
        return members[0]


class Diffusion:
    """Stream state lives in pop.state['diffusion']; the selection structure is rebuilt from it after a load."""

    def __init__(self, pop):
        self.pop, self.cfg = pop, pop.cfg
        self.state = pop.state.setdefault('diffusion', {'t': pop.state['start_day'], 'n': 0, 'next': None, 'realized': [],
                                                         'topics': {}, 'items': {}})
        self.cr = CompositionRejection()
        for pid in self.state['realized']:
            self.cr.set(pid, self.rate(pid))
        self._realized = set(self.state['realized'])

    # Mean field for people not yet realized.

    def _bins(self):
        n = int(self.cfg['mean_field_bins'])
        return [-1 + 2 * k / (n - 1) for k in range(n)]

    def topic(self, name):
        topics = self.state['topics']
        if name not in topics:
            centers, sd = self._bins(), self.cfg['opinion_initial_sd']
            weights = [pow(2.718281828, -(x / sd) ** 2 / 2) if sd else float(x == 0) for x in centers]
            total = sum(weights)
            topics[name] = {'values': {}, 'hist': [w / total for w in weights], 'hist_t': self.state['t']}
        return topics[name]

    def advance_mean_field(self, name, t):
        topic, cfg = self.topic(name), self.cfg
        centers, eps, mu = self._bins(), cfg['opinion_epsilon'], cfg['opinion_mu']
        step = cfg['mean_field_step_days']
        nearest = lambda x: min(range(len(centers)), key=lambda k: abs(centers[k] - x))
        while topic['hist_t'] + step <= t:
            p = topic['hist']
            share = min(1.0, cfg['interaction_rate_per_year'] * step / YEAR)  # chance a person talks in this step
            new = [(1 - share) * w for w in p]
            for a, pa in enumerate(p):
                if pa < 1e-12:
                    continue
                for b, pb in enumerate(p):
                    target = a if abs(centers[a] - centers[b]) >= eps else nearest(centers[a] + mu * (centers[b] - centers[a]))
                    new[target] += share * pa * pb
            total = sum(new)  # pair mixing amplifies rounding (x(1+share) per step): renormalize
            new = [x / total for x in new]
            change = sum(abs(x - y) for x, y in zip(new, p))
            topic['hist'], topic['hist_t'] = new, topic['hist_t'] + step
            if change < 1e-7:  # settled: later steps change nothing
                topic['hist_t'] = t
        return topic['hist']

    # Realized people.

    def rate(self, pid):
        e = self.pop.person(pid)['traits']['E']
        return self.cfg['interaction_rate_per_year'] * pow(2.718281828, self.cfg['interaction_extraversion'] * e)

    def realize(self, pid):
        if pid in self._realized:
            return
        t = self.state['t']
        for name in self.state['topics']:
            hist, centers = self.advance_mean_field(name, t), self._bins()
            u, k = uniform(self.pop.seed, 'realize', pid, name), 0
            while k < len(hist) - 1 and u > hist[k]:
                u -= hist[k]
                k += 1
            self.state['topics'][name]['values'][pid] = centers[k]
        self.state['realized'].append(pid)
        self._realized.add(pid)
        self.cr.set(pid, self.rate(pid))
        self.state['next'] = None  # the total rate changed: the pending waiting time is redrawn (memoryless)

    def opinion(self, pid, name, t):
        """A person's opinion at t: realizes them if needed and runs the stream up to t."""
        self.topic(name)
        self.realize(pid)
        self.run(t)
        return self.state['topics'][name]['values'][pid]

    def seed_item(self, name, adopters, t, *, threshold=None, threat=False):
        """Start a behavior or rumor: threshold 1 spreads on one exposure (a rumor); None uses the config mean."""
        item = self.state['items'].setdefault(name, {'threshold': threshold, 'threat': threat, 'adopted': {}, 'exposures': {}})
        for pid in adopters:
            self.realize(pid)
            item['adopted'].setdefault(pid, t)

    def threshold(self, name, pid):
        item = self.state['items'][name]
        if item['threshold'] is not None:
            return item['threshold']
        return max(1, round(self.cfg['adoption_threshold_mean'] + .7 * normal(self.pop.seed, 'threshold', name, pid)))

    def run(self, until):
        """Process conversations up to `until`. Each event's draws are keyed by its number, so a run is replayable."""
        pop, cfg, state = self.pop, self.cfg, self.state
        while self.cr.total > 0:
            n = state['n']
            if state['next'] is None:
                state['next'] = state['t'] + -log(uniform(pop.seed, 'conv-wait', n, state['t'])) / self.cr.total * YEAR
            if state['next'] > until:
                break
            t = state['t'] = state['next']
            state['next'], state['n'] = None, n + 1
            speaker = self.cr.select(lambda k: uniform(pop.seed, 'conv-pick', n, k))
            self._conversation(speaker, t, n)
        state['t'] = max(state['t'], until)

    def _conversation(self, i, t, n):
        pop, cfg = self.pop, self.cfg
        from .ties import base_tie
        partners = [j for j in pop.base_neighbors(i) if j in self._realized]
        j = None
        if partners:
            weights = [base_tie(pop, i, j)['s0'] for j in partners]
            u = uniform(pop.seed, 'conv-partner', n) * sum(weights)
            for j, w in zip(partners, weights):
                u -= w
                if u <= 0:
                    break
        for name, topic in self.state['topics'].items():
            values = topic['values']
            if j is None:  # nobody realized nearby: talk with the compartment (a draw from its distribution)
                hist, centers = self.advance_mean_field(name, t), self._bins()
                u, k = uniform(pop.seed, 'conv-mf', n, name), 0
                while k < len(hist) - 1 and u > hist[k]:
                    u -= hist[k]
                    k += 1
                other, credibility = centers[k], .65
            else:
                other, credibility = values[j], .3 + .7 * uniform(pop.seed, 'credibility', j)
            mine = values[i]
            if j is None:
                if abs(mine - other) < cfg['opinion_epsilon']:
                    weight = credibility ** (cfg['credibility_gamma'] * pop.dials(i, t)['reality_testing'])
                    values[i] = clip(mine + cfg['opinion_mu'] * weight * (other - mine), -1, 1)
            else:
                values[i], values[j] = rule_change(pop, mine, other, i, j, t), rule_change(pop, other, mine, j, i, t)
        if j is not None:
            for name in self.state['items']:
                self._expose(name, i, j, t, n)
                self._expose(name, j, i, t, n)

    def _expose(self, name, listener, source, t, n):
        item = self.state['items'][name]
        if source not in item['adopted'] or listener in item['adopted']:
            return
        chance = .5 * (1 + self.cfg['threat_rate_gain'] * self.pop.dials(listener, t)['threat_sensitivity']) if item['threat'] else .5
        if uniform(self.pop.seed, 'expose', name, n, listener) >= min(1.0, chance):
            return
        window = self.cfg['contagion_window_days']
        seen = [e for e in item['exposures'].get(listener, []) if t - e[1] <= window and e[0] != source] + [[source, t]]
        item['exposures'][listener] = seen
        if len({e[0] for e in seen}) >= self.threshold(name, listener):
            item['adopted'][listener] = t
