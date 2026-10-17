"""The society layer inside a running world: engine characters bound to people of the implicit population.

A bound character keeps its own personality, age and dials; around it the implicit population supplies kin,
friends and acquaintances whose lives are resolved lazily. Society checks run only when something can be due (the
next contact among the character's closest ties, or at most bridge_max_gap_days later): deaths, fallings-out and
people getting in touch arrive as ordinary received observations, so appraisal, the hippocampal buffer and mood
handle them like any other experience. Anything shown is committed in the population's log. Conversations between
bound characters move their opinions by the bounded-confidence rule only; the model renders, it never decides.
"""
from copy import deepcopy
from statistics import NormalDist

from . import Population
from .core import uniform, TRAITS
from .guards import conflict_floor, persona, record_variance, rule_change

FEMALE = ('Aarti', 'Anjali', 'Asha', 'Deepa', 'Gauri', 'Kavita', 'Leela', 'Madhuri', 'Meena', 'Neha', 'Pooja', 'Prachi',
          'Rekha', 'Sangeeta', 'Shalini', 'Sneha', 'Sunita', 'Swati', 'Usha', 'Vaishali')
MALE = ('Ajay', 'Amol', 'Anil', 'Ashok', 'Ganesh', 'Kiran', 'Mahesh', 'Manoj', 'Nikhil', 'Prakash', 'Rahul', 'Rajesh',
        'Sachin', 'Sanjay', 'Santosh', 'Suresh', 'Tushar', 'Vijay', 'Vikas', 'Yogesh')
_NORMAL = NormalDist()


def configure(engine, overrides=None):
    """Attach a population to this world (checkpointed in engine.state). Archived worlds without it are unchanged."""
    settings = {'overrides': deepcopy(overrides or {})}
    current = engine.state['config'].get('society_layer')
    if current is not None:
        if current != settings:
            raise ValueError('Cannot silently replace society-layer policy')
        return population(engine)
    engine.state['society_layer'] = Population.new(engine.state['seed'], engine.day, overrides).state
    engine.state['config']['society_layer'] = settings
    return population(engine)


def population(engine):
    cached = getattr(engine, '_population', None)
    if cached is None or cached.state is not engine.state['society_layer']:
        engine._population = Population(engine.state['society_layer'])
    return engine._population


def name(pop, pid):
    names = FEMALE if pop.person(pid)['sex'] == 'F' else MALE
    return names[int(uniform(pop.seed, 'name', pid) * len(names))]


def entity_of(engine, pid):
    """The lightweight world identity for a population person (created when they first matter to a character)."""
    pop = population(engine)
    for key, entity in engine.state['entities'].items():
        if entity['facts'].get('society_person') == pid:
            return key
    key = 'pop-' + pid.replace('.', '-')
    engine.entity(key, name(pop, pid), {'society_person': pid, 'birth_day': pop.person(pid)['birth_day']})
    return key


def bind(engine, owner, pid=None):
    """Place an engine character in the population: a hashed nearby person of the same age, overridden with the
    character's own Big Five (domain means of its facets), birth day and dials."""
    pop = population(engine)
    agent = engine.agent(owner)
    if owner in pop.state['bound'].values():
        return next(p for p, o in pop.state['bound'].items() if o == owner)
    age = (engine.day - agent['birth_day']) / 365.25
    # The engine's family is the family: characters linked as caregiver and child share one population household
    # (and cell); the bound person's hashed base housemates stop counting as kin.
    related, frontier = set(), [owner]  # the whole family: caregiver links followed both ways (co-parents too)
    while frontier:
        key = frontier.pop()
        links = set(engine.state['entities'][key]['facts'].get('caregivers', [])) | \
            {k for k, e in engine.state['entities'].items() if key in e['facts'].get('caregivers', [])}
        frontier += [k for k in links - related - {owner}]
        related |= links - {owner}
    placed = [p for p, o in pop.state['bound'].items() if o in related]
    household = pop.person(placed[0])['household'] if placed else 'engine:' + owner
    if pid is None:
        cell = pop.person(placed[0])['cell'] if placed else int(uniform(pop.seed, 'bind-cell', owner) * pop.grid * pop.grid)
        people = sorted((f'p{i}' for i in range(cell * pop.cell_size, (cell + 1) * pop.cell_size)), key=lambda p: uniform(pop.seed, 'bind', owner, p))
        pid = min(people, key=lambda p: (abs(pop.age(p, engine.day) - age) > 3, p in pop.state['bound']))
    if pid in pop.state['bound']:
        raise ValueError('That population person is already bound to another character')
    facets = agent['facets']
    traits = {d: _NORMAL.inv_cdf(min(.999, max(.001, sum(facets[f'{d}{i}'] for i in range(1, 7)) / 600))) for d in TRAITS}
    base = pop.person(pid)['dials']
    pop.state.setdefault('overrides', {})[pid] = {'traits': traits, 'birth_day': agent['birth_day'], 'household': household,
                                                   'dials': {**base, **agent.get('dials', {})}}
    pop.state['bound'][pid] = owner
    pop._person.cache_clear()
    pop._neighbors.clear()
    engine.state['entities'][owner]['facts'].setdefault('society_person', pid)
    return pid


def _deliver_default(engine):
    def deliver(event_id, description, observations, routine=False):
        engine.schedule(event_id, engine.day, description, observations)
        engine.advance(engine.day)
    return deliver


def sync(engine, deliver=None):
    """Bring each bound character's social world up to now; returns the day of the next check (event-driven)."""
    from .ties import neighbors, tie, _resolve
    pop = population(engine)
    deliver = deliver or _deliver_default(engine)
    cfg, t = pop.cfg, engine.day
    synced = pop.state.setdefault('synced', {})
    next_check = t + cfg['bridge_max_gap_days']
    for pid, owner in sorted(pop.state['bound'].items()):
        if not engine.agent(owner)['alive']:
            continue
        last = synced.get(pid, pop.state['start_day'])
        rows = neighbors(pop, pid, t)
        close = rows[:int(cfg['bridge_top_ties'])]
        news = []
        for row in rows:
            other, death = row['id'], pop.death_day(row['id'])
            if death is not None and last < death <= t and row['strength'] >= .2:
                news.append(('died', other, row))
        previous = pop.state.setdefault('close', {})
        close_ids = {r['id'] for r in close} | set(previous.get(pid, []))  # a just-ruptured tie fell out of the top
        for kind in ('tie_ruptured', 'hostile_contact', 'reconciled'):  # fights matter as news only with close ties
            for fact in pop.facts(pid, kind):
                other = next(x for x in fact['who'] if x != pid)
                if last < fact['t'] <= t and not fact['committed'] and other in close_ids:
                    news.append((kind, other, next((r for r in rows if r['id'] == other), None)))
        heard = pop.state.setdefault('contact_news', {})
        touched = [r for r in close if last < r['last_contact'] <= t and r['alive'] and not r['ruptured']
                   and t - heard.get(f'{pid}|{r["id"]}', -1e18) >= cfg['bridge_contact_repeat_days']]
        news += [('contact', r['id'], r) for r in sorted(touched, key=lambda r: -r['strength'])[:int(cfg['bridge_contact_news_max'])]]
        for n, (kind, other, row) in enumerate(news):
            who = engine.label(entity_of(engine, other))
            strength = row['strength'] if row else .3
            text, valence, arousal = {
                'died': (f'I heard that {who} died.', -.8 * strength, .85),
                'tie_ruptured': (f'{who} and I had a serious falling-out; we are not speaking.', -.6, .7),
                'hostile_contact': (f'{who} and I had an angry exchange.', -.4, .6),
                'reconciled': (f'{who} and I made up after our falling-out.', .4, .5),
                'contact': (f'{who} got in touch with me.', .3 * (row['valence'] if row else 0) + .1, .3)}[kind]
            pop.state['news'] = pop.state.get('news', 0) + 1
            deliver(f'@society:{pid}:{pop.state["news"]}', 'News from the society layer reaches a character; it reports what they learned.',
                    {owner: {'text': text, 'source': entity_of(engine, other), 'kind': 'direct', 'valence': max(-1, min(1, valence)),
                             'arousal': arousal, 'importance': min(1, .3 + strength)}}, kind == 'contact')
            pop.commit(other, t)  # shown to a character: now immutable
            if kind == 'contact':
                heard[f'{pid}|{other}'] = t
            if kind == 'died':  # v4 review: characters without scenario-set dials silently skipped grief
                agent_dials = engine.agent(owner).setdefault('dials', {})
                agent_dials['mood_baseline_shift'] = max(-1, agent_dials.get('mood_baseline_shift', 0) + cfg['grief_mood_shift'] * strength)
        for kind in ('tie_ruptured', 'hostile_contact', 'reconciled'):
            for fact in pop.facts(pid, kind):
                if fact['t'] <= t:
                    fact['committed'] = True
        synced[pid] = t
        previous[pid] = [r['id'] for r in close]
        pop.state.setdefault('view', {})[pid] = _view(engine, pop, pid, close, t)
        for row in close:  # the next contact among close ties, found on a copy so stored ties stay at now
            if not row['alive'] or row['ruptured']:
                continue
            probe = deepcopy(tie(pop, pid, row['id']))
            before = probe['last']
            _resolve(pop, pid, row['id'], probe, t + cfg['bridge_max_gap_days'], quiet=True)
            if probe['last'] > before:
                next_check = min(next_check, probe['last'])
    for topic in cfg['topics']:
        values = pop.state.get('diffusion', {}).get('topics', {}).get(topic, {}).get('values', {})
        record_variance(pop, topic, t, values.values())
    return max(next_check, t + 1e-6)


def _view(engine, pop, pid, close, t):
    from .ties import tie
    ties = []
    for row in close:
        record = tie(pop, pid, row['id'])
        closeness = 'very close' if row['strength'] > .6 else 'close' if row['strength'] > .35 else 'friendly' if row['strength'] > .15 else 'distant'
        ties.append({'name': engine.label(entity_of(engine, row['id'])), 'relation': 'family' if row['kin'] else 'friend or acquaintance',
                     'closeness': closeness, **({'alive': False} if not row['alive'] else {}),
                     **({'non_cooperation_floor': conflict_floor(record)} if conflict_floor(record) else {})})
    opinions = {topic: round(values[pid], 2) for topic, data in pop.state.get('diffusion', {}).get('topics', {}).items()
                for values in [data['values']] if pid in values}
    return {'persona': persona(pop, pid), 'people_in_your_life': ties, **({'opinions': opinions} if opinions else {})}


def context(engine, owner):
    """Cheap context section for a bound character (computed at the last check, so repeated context builds agree)."""
    pop = population(engine)
    pid = engine.state['entities'][owner]['facts'].get('society_person')
    return deepcopy(pop.state.get('view', {}).get(pid)) if pid in pop.state['bound'] else None


def after_turn(engine, speaker, listeners):
    """A spoken turn between bound characters: their opinions move by the bounded-confidence rule (never the model)."""
    from .diffusion import Diffusion
    pop = population(engine)
    ids = {o: p for p, o in pop.state['bound'].items()}
    if speaker not in ids or not pop.cfg['topics']:
        return
    stream = Diffusion(pop)
    for topic in pop.cfg['topics']:
        stream.topic(topic)
    for person in [ids[speaker], *(ids[l] for l in listeners if l in ids)]:
        stream.realize(person)
    stream.run(engine.day)
    for listener in listeners:
        if listener in ids:
            a, b = ids[speaker], ids[listener]
            for topic in pop.cfg['topics']:
                values = pop.state['diffusion']['topics'][topic]['values']
                values[b], values[a] = rule_change(pop, values[b], values[a], b, a, engine.day), rule_change(pop, values[a], values[b], a, b, engine.day)
