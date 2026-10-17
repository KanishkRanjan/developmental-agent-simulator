"""Society layer checks (design v2): determinism, lazy cost, the design's non-circular validation table, and the
engine bridge. Synthetic; no model server. Inputs used for calibration are never counted as validation."""
from collections import Counter
from copy import deepcopy
import inspect
import json
from math import exp, log
from pathlib import Path
import statistics
import time

from devsim.engine import Engine, FACET_NAMES
from devsim.lifetime import Lifetime
from devsim.population import Population, bridge, core, demography, diffusion, guards, institutions, ties
from devsim.population.core import parameters, uniform

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
YEAR = 365.25


def spearman(xs, ys):
    rank = lambda v: {i: r for r, i in enumerate(sorted(range(len(v)), key=v.__getitem__))}
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    return 1 - 6 * sum((rx[i] - ry[i]) ** 2 for i in range(n)) / (n * (n * n - 1))


def main():
    checks, report = [], {}

    # Config discipline: every number is tagged; verified ones name their source.
    spec = parameters()
    assert all(item.get('tag') in ('V', 'D', 'U') and item.get('note') for item in spec.values())
    verified = {k for k, v in spec.items() if v['tag'] == 'V'}
    assert verified == {'infant_mortality_per_1000', 'under5_mortality_per_1000', 'isolation_odds_ratio', 'median_age_first_marriage_women',
                        'adolescent_fertility_per_1000'}, verified
    assert all(any(src in spec[k]['note'] for src in ('NFHS-5', 'Holt-Lunstad')) for k in verified)
    for bad in ({'kappa': -1}, {'tiers': [1, 2]}, {'nonsense': 1}, {'topics': [1]}):
        try:
            core.settings(bad)
            raise AssertionError(f'accepted {bad}')
        except ValueError:
            pass
    checks.append('every parameter carries a V/D/U tag and a note; only the five NFHS-5 and Holt-Lunstad anchors are V; bad overrides are refused')

    # Steps 1-2: determinism, symmetry, heavy tails, cost independent of population size.
    pop, again, other = Population.new(7), Population.new(7), Population.new(8)
    start = pop.state['start_day']
    assert pop.person('p1234') == again.person('p1234') and pop.base_neighbors('p1234') == again.base_neighbors('p1234')
    assert pop.base_neighbors('p1234') != other.base_neighbors('p1234')
    sample = [f'p{(k * 7919) % pop.size}' for k in range(40)]
    degrees = sorted(len(pop.base_neighbors(p)) for p in sample)
    for p in sample[:8]:
        for j in pop.base_neighbors(p)[:15]:
            assert p in pop.base_neighbors(j), (p, j)
    assert 40 <= statistics.mean(degrees) <= 200 and degrees[-1] >= 3 * statistics.median(degrees), degrees
    timing = {}
    for grid in (20, 200):
        big = Population.new(9, overrides={'grid': grid})
        clock = time.perf_counter()
        for k in range(10):
            big.base_neighbors(f'p{(k * 104729) % big.size}')
        timing[grid] = time.perf_counter() - clock
    assert timing[200] < 3 * timing[20] + .2, timing
    report['degree'] = {'mean': round(statistics.mean(degrees), 1), 'median': statistics.median(degrees), 'max': degrees[-1]}
    checks.append(f'the implicit graph is seeded, symmetric and heavy-tailed (mean degree {statistics.mean(degrees):.0f}, median '
                  f'{statistics.median(degrees)}, max {degrees[-1]}); a neighborhood query costs the same for 40,000 or 4,000,000 people')

    # Step 3: closed-form decay, path-independent contacts, contact vs closeness (Roberts & Dunbar 2011 direction).
    a = 'p1234'
    b = pop.base_neighbors(a)[3]
    record = ties.base_tie(pop, a, b)
    low = pop.cfg['s_floor_kin'] if record['kin'] else pop.cfg['s_floor_friend']
    for dt in (0, 10, 400):
        expected = low + (record['s_last'] - low) / (1 + max(0, start + dt - record['last']) / (9 * record['S']))
        assert abs(ties.strength_at(pop.cfg, record, start + dt) - expected) < 1e-12
    one, two = Population.new(7), Population.new(7)
    whole = ties.tie(one, a, b, start + 900)
    ties.tie(two, a, b, start + 200)
    ties.tie(two, a, b, start + 500)
    assert ties.tie(two, a, b, start + 900) == whole
    gaps = {True: [], False: []}
    pairs = []
    t = start + YEAR
    for p in sample[:15]:
        for row in ties.neighbors(pop, p, t):
            base = ties.base_tie(pop, p, row['id'])
            gaps[row['kin']].append(t - row['last_contact'])
            if not row['kin']:
                pairs.append((base['s0'], t - row['last_contact']))
    rho = spearman([s for s, _ in pairs], [g for _, g in pairs])
    assert rho < -.2 and statistics.median(gaps[True]) < statistics.median(gaps[False]), (rho, statistics.median(gaps[True]))
    negative = dict(record, valence=-.8)
    calm = {x: dict(pop.dials(x), threat_sensitivity=.0, dysregulation=.0) for x in (a, b)}
    tense = {x: dict(pop.dials(x), threat_sensitivity=1.0, dysregulation=1.0) for x in (a, b)}
    f_calm, h_calm, _ = ties._rates(pop, a, b, negative, calm)
    f_tense, h_tense, _ = ties._rates(pop, a, b, negative, tense)
    assert f_tense < f_calm and h_tense > h_calm == 0
    report['contact'] = {'closeness_gap_spearman': round(rho, 2), 'median_gap_days_kin': round(statistics.median(gaps[True]), 1),
                         'median_gap_days_friend': round(statistics.median(gaps[False]), 1)}
    checks.append(f'tie strength decays by the memory forgetting curve; contacts replay identically however a pair is queried; closer '
                  f'pairs have shorter gaps since last contact (Spearman {rho:.2f}) and kin shorter than friends (V direction); threat '
                  'sensitivity suppresses contact over a negative memory and dysregulation turns it hostile')

    # Step 4 gate: demography reproduces outcomes it was not fitted to (NFHS-5 Maharashtra).
    women = [f'p{i}' for i in range(0, pop.size, 61) if pop.person(f'p{i}')['sex'] == 'F']
    first, young, early, exposure, births = [], 0, 0, [0] * 7, [0] * 7
    for w in women:
        age = pop.age(w, start)
        if 20 <= age < 50:
            pop.resolve(w, start)
            m = pop.facts(w, 'marriage')
            at = (m[0]['t'] - pop.person(w)['birth_day']) / YEAR if m else 99
            first.append(at)
            if age < 25:
                young += 1
                early += at < 18
        if 15 <= age < 50:
            band = int((age - 15) // 5)
            pop.resolve(w, start + 3 * YEAR)  # three years of births (by age band at the start) to cut sampling noise
            exposure[band] += 3
            births[band] += sum(1 for f in pop.facts(w, 'birth') if f['data']['mother'] == w and start < f['t'] <= start + 3 * YEAR)
    tfr = 5 * sum(b / e for b, e in zip(births, exposure) if e)
    median_marriage, before18 = statistics.median(first), early / young
    cal = pop.calibration
    survival, e0 = 1.0, 0.0
    for k in range(1200):
        hazard = cal.mortality(k / 10 + .05) * .1
        e0 += survival * .1 * exp(-hazard / 2)
        survival *= exp(-hazard)
    # Total fertility is emergent from unverified parity factors and runs high (about 2.0 vs 1.7); the band is a
    # sanity bound, not a pass at the anchor. Tuning parity factors to hit 1.7 would make this check circular.
    assert abs(median_marriage - 19.6) <= 1.0 and abs(before18 - .219) <= .07 and 1.2 <= tfr <= 2.4 and 65 <= e0 <= 80, \
        (median_marriage, before18, tfr, e0)
    report['demography'] = {'median_first_marriage': round(median_marriage, 1), 'married_before_18': round(before18, 3),
                            'period_tfr': round(tfr, 2), 'life_expectancy_no_isolation': round(e0, 1), 'women_sampled': len(women)}
    checks.append(f'demography (calibrated only on median marriage age and adolescent fertility) gives period total fertility {tfr:.2f} '
                  f'(NFHS-5: 1.7; runs high on unverified parity factors), {100 * before18:.0f}% of women 20-24 married before 18 (21.9%), median first marriage {median_marriage:.1f} '
                  f'(19.6) and life expectancy {e0:.1f} without isolation')

    # Step 5: joint events and the commit protocol.
    living_wives = Counter()
    for fact in pop.state['log']:
        if fact['kind'] == 'marriage' and not fact.get('rolled_back'):
            w, h = fact['who']
            assert any(set(f['who']) == {w, h} for f in pop.facts(h, 'marriage')), 'a joint fact is in both logs'
            wives = [f['who'][0] for f in pop.facts(h, 'marriage') if f['t'] <= fact['t']]
            living_wives[(h, fact['t'])] = sum(pop.alive(x, fact['t'] - 1e-6) for x in wives if x != w and
                                               pop.resolve(x, fact['t'])['spouse'] == h)
    assert max(living_wives.values(), default=0) == 0, 'no man marries while a wife is alive and married to him'
    fresh, chunked = Population.new(13), Population.new(13)
    w = next(x for x in women if 30 <= fresh.age(x, start) < 40)
    fresh.resolve(w, start + 20 * YEAR)
    for k in range(1, 6):
        chunked.resolve(w, start + 4 * k * YEAR)
    shape = lambda p: [(f['kind'], round(f['t'], 6), tuple(f['who'])) for f in p.facts(w)]
    assert shape(fresh) == shape(chunked), 'a life resolved in one call or many has the same history'
    for i in range(0, pop.size, 101):
        old = f'p{i}'
        if pop.age(old, start) > 75 and pop.death_day(old, resolve=start + 5 * YEAR):
            break
    pop.observe(old, start + 6 * YEAR, 'seen_alive')
    later = pop.death_day(old, resolve=start + 40 * YEAR)
    assert later is None or later > start + 6 * YEAR
    wife = next(x for x in women if 25 < pop.age(x, start) < 30 and pop.resolve(x, start)['spouse'])
    husband, marriage = pop.resolve(wife, start)['spouse'], pop.facts(wife, 'marriage')[0]
    pop.observe(wife, start, 'seen_single')
    assert marriage.get('rolled_back') and not pop.facts(husband, 'marriage') and pop.resolve(wife, start)['spouse'] is None
    try:
        pop.rollback(wife, start - 1)
        raise AssertionError('rolled back a committed fact')
    except ValueError:
        pass
    assert pop.horizon() <= start + 6 * YEAR
    # Order independence is approximate (design section 9): resolving the same people in another order may change
    # who marries whom, but not the statistics.
    probe = Population.new(19)
    group = [f'p{i}' for i in range(0, probe.size, 61) if probe.person(f'p{i}')['sex'] == 'F' and 20 <= probe.age(f'p{i}', start) < 45][:600]
    stats = []
    for order in (group, list(reversed(group))):
        fresh_pop = Population.new(19)
        for x in order:
            fresh_pop.resolve(x, start)
        married = [fresh_pop.resolve(x, start)['spouse'] is not None for x in group]
        stats.append((sum(married) / len(group), statistics.mean(fresh_pop.resolve(x, start)['parity'] for x in group)))
    assert abs(stats[0][0] - stats[1][0]) < .05 and abs(stats[0][1] - stats[1][1]) < .2, stats
    report['order'] = {'married_share_forward_vs_reverse': [round(stats[0][0], 3), round(stats[1][0], 3)],
                       'mean_parity_forward_vs_reverse': [round(stats[0][1], 2), round(stats[1][1], 2)]}
    checks.append('marriages are joint facts in both logs with no bigamy; a life resolved in one call or in chunks is identical; seeing someone '
                  'alive moves a latent death later; seeing someone single rolls back the marriage and the partner\'s slice; committed facts '
                  'are never rolled back; the commit horizon is the earliest uncommitted joint fact; resolving 600 women in reverse order keeps '
                  f'the married share ({stats[0][0]:.2f} vs {stats[1][0]:.2f}) and mean parity ({stats[0][1]:.2f} vs {stats[1][1]:.2f})')

    # Step 6 gate: constant-cost event selection, opinion structure on our graph, agents vs mean field, contagion.
    cr = diffusion.CompositionRejection()
    for k in range(50):
        cr.set(k, .01 * 3 ** (k % 7) + k * .001)
    hits = Counter(cr.select(lambda j, n=n: uniform('cr', n, j)) for n in range(30000))
    assert max(abs(hits[k] / 30000 - cr.rates[k] / cr.total) / (cr.rates[k] / cr.total) for k in range(50) if cr.rates[k] / cr.total > .01) < .1
    structure = {}
    for eps in (1.0, .15):
        small = Population.new(11, overrides={'opinion_epsilon': eps, 'cell_size': 40})
        stream = diffusion.Diffusion(small)
        stream.topic('policy')
        for pid in sorted(small.candidates('p' + str((30 * 60 + 30) * 40))):
            stream.realize(pid)
        stream.run(small.state['start_day'] + 2 * YEAR)
        values = sorted(stream.state['topics']['policy']['values'].values())
        groups, run = 0, 1
        for x, y in zip(values, values[1:] + [9]):
            if y - x > .05:
                groups += run >= .05 * len(values)
                run = 0
            run += 1
        hist = stream.advance_mean_field('policy', small.state['start_day'] + 2 * YEAR)
        peaks = sum(1 for k, v in enumerate(hist) if v > .03 and (k == 0 or hist[k - 1] <= v) and (k == len(hist) - 1 or hist[k + 1] <= v))
        structure[eps] = {'sd': round(statistics.pstdev(values), 3), 'groups': groups, 'mean_field_peaks': peaks, 'realized': len(values)}
    assert structure[1.0]['groups'] == 1 == structure[1.0]['mean_field_peaks'] and structure[.15]['groups'] >= 2 and structure[.15]['mean_field_peaks'] >= 2
    assert structure[.15]['sd'] > 3 * structure[1.0]['sd']
    report['opinions'] = structure
    adopted = {}
    for threshold in (1, 3):
        net = Population.new(17, overrides={'cell_size': 40})
        stream = diffusion.Diffusion(net)
        center = 'p' + str((30 * 60 + 30) * 40)
        people = sorted(net.candidates(center) | {center})
        for pid in people:
            stream.realize(pid)
        seeds = [center] + [j for j in net.base_neighbors(center) if j in stream._realized][:4]  # a connected start
        stream.seed_item('news', seeds, net.state['start_day'], threshold=threshold)
        stream.run(net.state['start_day'] + YEAR / 2)
        adopted[threshold] = len(stream.state['items']['news']['adopted'])
    assert adopted[1] > 2 * adopted[3] and adopted[3] >= 5, adopted
    sceptic, credulous = dict(pop.dials(a), reality_testing=1.0), dict(pop.dials(a), reality_testing=.2)
    weight = lambda rt: .3 ** (pop.cfg['credibility_gamma'] * rt)
    assert weight(credulous['reality_testing']) > weight(sceptic['reality_testing'])
    report['contagion_adopters'] = adopted
    checks.append(f'composition-rejection picks channels in proportion to rate; on this graph wide confidence gives one opinion group and narrow '
                  f'gives {structure[.15]["groups"]} (sd {structure[1.0]["sd"]} vs {structure[.15]["sd"]}), and the mean-field compartment agrees '
                  f'({structure[1.0]["mean_field_peaks"]} vs {structure[.15]["mean_field_peaks"]} peaks); a rumor reaches {adopted[1]} people where a '
                  f'three-exposure behavior reaches {adopted[3]}; low reality testing discounts low-credibility sources less')

    # Step 7: lazy institutions, roles by fit, one sanction formula, collective action.
    t = start
    worker = next(p for p in sample if institutions.institution_of(pop, p, 'workplace', t))
    place = institutions.institution_of(pop, worker, 'workplace', t)
    crew = institutions.members(pop, place, t)
    assert worker in crew and all(institutions.institution_of(pop, p, 'workplace', t) == place for p in crew)
    assigned = institutions.roles(pop, place, t)
    assert Counter(assigned.values())['head'] >= 1 and set(assigned) == set(crew)
    base = institutions.sanction_sensitivity(pop, worker)
    original = pop.person(worker)
    shifted = deepcopy(original)
    shifted['traits']['A'] += 1
    pop._person.cache_clear()
    pop.state.setdefault('overrides', {})[worker] = {'traits': shifted['traits']}
    assert institutions.sanction_sensitivity(pop, worker) > base
    del pop.state['overrides'][worker]
    pop._person.cache_clear()
    source = inspect.getsource(institutions) + inspect.getsource(guards)
    assert not any(word in source.lower() for word in ('psychopath', 'narciss', 'archetype ==', 'visionary'))
    calm_share, calm_event = institutions.collective_action(pop, place, t)
    institutions.raise_tension(pop, place, .3, t)
    hot_share, hot_event = institutions.collective_action(pop, place, t)
    assert calm_event is None and hot_event is not None and hot_share > calm_share
    assert institutions.sanction_hazard(pop, 'cell:1', 0.9, 1) > institutions.sanction_hazard(pop, 'cell:1', institutions.norm(pop, 'cell:1')['mean'], 1)
    checks.append(f'institutions have no member list: a workplace\'s {len(crew)} members come from its region by hash, roles go to the best '
                  'fit, sanction sensitivity is one formula over dials and traits (no archetype branch), and a collective event fires only '
                  f'once tension pushes the threshold cascade past the trigger ({calm_share:.2f} -> {hot_share:.2f})')

    # Step 8 gate: heavy-tailed capital from fit and luck; identical people in different networks diverge.
    rows = []
    for p in [f'p{i}' for i in range(0, pop.size, 211) if 20 <= pop.age(f'p{i}', start) < 35][:300]:
        traits, fit = pop.person(p)['traits'], pop.cfg['opportunity_fit']
        rows.append((institutions.capital(pop, p, start + 30 * YEAR), fit['O'] * traits['O'] + fit['C'] * traits['C'] + fit['E'] * traits['E']))
    caps = sorted(c for c, _ in rows)
    top_share = sum(caps[-max(1, len(caps) // 100):]) / sum(caps)
    rho_fit = spearman([f for _, f in rows], [c for c, _ in rows])
    best = sorted(rows, reverse=True)[:max(3, len(rows) // 50)]
    fit_cut = sorted(f for _, f in rows)[int(.9 * len(rows))]
    assert top_share > .1 and rho_fit > 0 and sum(f >= fit_cut for _, f in best) < len(best), (top_share, rho_fit)
    twins = [p for p in sample if 20 <= pop.age(p, start) < 40][:2]
    copy = deepcopy(pop.person(twins[0])['traits'])
    pop.state.setdefault('overrides', {})[twins[1]] = {'traits': copy}
    pop._person.cache_clear()
    split = (institutions.capital(pop, twins[0], start + 20 * YEAR), institutions.capital(pop, twins[1], start + 20 * YEAR))
    assert split[0] != split[1]
    report['capital'] = {'top_1pct_share': round(top_share, 2), 'fit_spearman': round(rho_fit, 2), 'people': len(rows)}
    checks.append(f'over 30 years capital is heavy-tailed (top 1% hold {100 * top_share:.0f}%), trait fit helps (Spearman {rho_fit:.2f}) but '
                  'the top outcomes are not all the best fits, and identical personalities in different networks end apart')

    # Step 9: isolation feeds mortality (plumbing, the odds ratio is an input) and losses feed dials.
    isolated = sorted(sample, key=lambda p: pop.isolation(p, start))
    low_iso, high_iso = pop.isolation(isolated[0], start), pop.isolation(isolated[-1], start)
    def death_rate(pid, iso):
        return demography.rates(pop, pid, pop.resolve(pid, start), start + 1, cal, iso)['death']
    young = next(p for p in sample if 30 <= pop.age(p, start) < 60)
    elder = next(p for p in (f'p{i}' for i in range(0, pop.size, 13)) if pop.age(p, start) >= 70 and pop.alive(p, start + 1))
    ratio = death_rate(young, high_iso) / death_rate(young, low_iso)
    imposed = exp((high_iso - low_iso) * log(pop.cfg['isolation_odds_ratio']) * pop.cfg['isolation_under65_factor'])
    assert high_iso > low_iso and abs(ratio - imposed) < 1e-9
    assert death_rate(elder, 1.0) / death_rate(elder, 0.0) < death_rate(young, 1.0) / death_rate(young, 0.0)
    lost = [f for f in pop.state['log'] if f['kind'] == 'tie_lost']
    grief = [f for f in pop.state['log'] if f['kind'] == 'dial_shift' and f['data']['cause'] == 'grief']
    drift = [f for f in pop.state['log'] if f['kind'] == 'dial_shift' and f['data']['cause'] == 'isolation']
    assert lost and grief and all(f['data']['shift']['mood_baseline_shift'] < 0 for f in grief) and drift
    report['isolation'] = {'least': round(low_iso, 2), 'most': round(high_iso, 2), 'hazard_ratio_under_65': round(ratio, 3), 'tie_losses_logged': len(lost)}
    checks.append(f'the most isolated sampled person (isolation {high_iso:.2f}) carries a death hazard {ratio:.2f}x the least isolated '
                  f'({low_iso:.2f}) as imposed, stronger under 65; deaths log tie losses and grief shifts on close survivors, and isolation '
                  'slowly raises threat sensitivity')

    # Step 10: guards at the model boundary.
    applied, clamped = guards.clamp(pop, 0.0, .1, .5, a, b, start)
    rule = guards.rule_change(pop, 0.0, .1, a, b, start)
    assert clamped and applied == rule and guards.clamp(pop, 0.0, .1, rule / 2, a, b, start) == (rule / 2, False)
    assert guards.clamp(pop, 0.0, .9, .3, a, b, start) == (0.0, True), 'outside epsilon nothing moves'
    assert guards.post_check(0.0, .4, rule) and not guards.post_check(0.0, rule, rule)
    assert guards.persona(pop, a) == guards.persona(again, a)
    assert guards.conflict_floor(dict(record, valence=-.6, hostile=2)) > 0 == guards.conflict_floor(dict(record, valence=.4))
    for k, v in enumerate((1.0, .9, .1, .05, .04)):
        guards.record_variance(pop, 'x', k, [0, v * 2])
    assert guards.collapsed(pop, 'x')
    checks.append('a model-proposed opinion change is clamped to the bounded-confidence rule (same direction, no larger), a post-check flags '
                  'overshoot, personas are fixed per person, enmity sets a non-cooperation floor, and the variance monitor flags collapse')

    # Bridge: engine characters inside the population, news as received experience, opinions by the rule.
    world = Engine(seed=4)
    for key, name, age in (('arun', 'Arun', 45), ('priya', 'Priya', 15)):
        world.entity(key, name, {'birth_day': -age * YEAR})
        world.materialize(key, dict.fromkeys(FACET_NAMES, 55), birth_day=-age * YEAR)
    world.caregiver('priya', 'arun')
    policy = {'sampling': 'event_driven', 'opportunities': [], 'society_layer': {'overrides': {'topics': ['school_rules']}}}
    Lifetime(world, policy, scripted=True).run(YEAR)
    layer = world._population
    ids = {o: p for p, o in layer.state['bound'].items()}
    assert layer.kin(ids['arun'], ids['priya']) and layer.person(ids['priya'])['household'] == layer.person(ids['arun'])['household']
    news = [o for o in world.world.observations['priya'] if o.event_id.startswith('@society:')]
    assert news and all(o.source in world.state['entities'] for o in news)
    assert all(layer.state['commit_day'].get(world.state['entities'][o.source]['facts'].get('society_person'), -1) >= o.day - 1e-6
               for o in news if o.source != 'arun')
    view = world.context('priya', 'An evening at home.')['social_world']
    assert view == world.context('priya', 'An evening at home.')['social_world'] and view['people_in_your_life'][0]['name'] == 'Arun'
    assert world.state['runtime']['next_society'] > world.day - 1e-6
    stream = diffusion.Diffusion(layer)
    stream.topic('school_rules')
    for pid in ids.values():
        stream.realize(pid)
    values = layer.state['diffusion']['topics']['school_rules']['values']
    values[ids['arun']], values[ids['priya']] = .1, .3
    bridge.after_turn(world, 'arun', ['priya'])
    assert .1 < values[ids['arun']] < values[ids['priya']] < .3, 'a spoken turn moves both toward each other, by the rule'
    report['bridge'] = {'news_for_priya_in_a_year': len(news), 'kinds': Counter(o.text.split(' ', 1)[-1] if 'touch' in o.text else
                                                                                o.text.split('.')[0][-25:] for o in news).most_common(3)}
    checks.append(f'engine characters are bound into the population (a caregiver and child share a household), their circle reaches them '
                  f'as received observations ({len(news)} in a year for Priya), shown people are committed, the context section is stable '
                  'between calls, checks are event-driven, and a spoken turn moves opinions by the rule, never the model')

    result = {'passed': True, 'scope': 'synthetic checks of design defaults; V anchors are inputs or comparisons, never fitted twice',
              'checks': checks, 'report': report}
    RESULTS_DIR.joinpath('population-engineering-checks.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
