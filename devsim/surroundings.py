"""The surroundings acting on their own, game style: happenings by room, weather and creatures. No model calls,
except an optional one-sentence TV news line in live runs.

Happenings come from the catalog for each room's kind (devsim/policies/living.json) plus the scenario's own. Each one
recurs at its rate inside its hours, from seeded draws. Only people in the room, or within earshot for audible ones,
perceive it; atmosphere is delivered as routine, so a repeat reuses the person's earlier reaction. Incidents can put
objects out of order, delay journeys, interrupt conversations or hurt someone present. Rates are provisional [D].
"""
from math import floor

from . import household
from . import living


def happenings(engine):
    """{key: (room, rule)} for every room's catalog happenings and the scenario's extras."""
    cfg = engine.state['config']['living']
    rooms = engine.state['config']['household']['rooms']
    found = {}
    for key, spec in rooms.items():
        for rule in cfg['happenings'].get(spec.get('kind', 'other'), []):
            found[f'{key}/{rule["id"]}'] = (key, rule)
    for rule in engine.state['config']['household'].get('happenings', []):
        found[f'{rule["room"]}/{rule["id"]}'] = (rule['room'], rule)
    return found


def creatures(engine):
    return {c['id']: c for c in engine.state['config']['household'].get('creatures', [])}


def start(controller):
    engine = controller.engine
    cfg = engine.state['config']['living']
    state = living.state(engine)
    due = living.due(engine)
    for key, (_, rule) in happenings(engine).items():
        if f'hap|{key}' not in due and rule['rate_per_day'] > 0:
            due[f'hap|{key}'] = next_time(controller, rule, key, engine.day, 0)
    if state['weather'] is None:
        state['weather'] = {'state': cfg['weather']['start'], 'since': engine.day}
        due['weather|'] = engine.day + controller.rng('weather', 0).expovariate(1 / cfg['weather']['mean_hours']) / 24
    for cid, spec in creatures(engine).items():
        if cid not in state['creatures']:
            state['creatures'][cid] = {'room': spec['room']}
            due[f'pet|{cid}'] = engine.day + controller.rng('creature', cid, 0).expovariate(
                1 / cfg['creature_kinds'][spec['kind']]['mean_minutes']) / 1440


def next_time(controller, rule, key, after, n):
    """Seeded exponential gap at rate_per_day, moved into the rule's hours when it falls outside them.

    shortcut: moving a draw into the window keeps the daily count but not the exact process; fine for ambience."""
    rng = controller.rng('happening', key, n)
    t = after + rng.expovariate(rule['rate_per_day'])
    start, end = rule['hours']
    hour = (t - floor(t)) * 24
    if not start <= hour < end:
        t = floor(t) + (hour >= end) + (start + rng.uniform(0, end - start)) / 24
    return t


def perceivers(engine, room, audible):
    """Awake people in the room, and in rooms within earshot when the happening is audible."""
    rooms = engine.state['config']['household']['rooms']
    places = {room, *(rooms[room].get('audible_to', []) if audible else [])}
    return sorted(p for p in engine.state['agents'] if household.available(engine, p) and
                  any(household.present(engine, p, r) for r in places))


def site_rooms(engine, room):
    s = living.site(engine, room)
    return [r for r in engine.state['config']['household']['rooms'] if r == room or (s is not None and living.site(engine, r) == s)]


def step(controller, name, arg):
    if name == 'hap':
        return happen(controller, arg)
    if name == 'restore':
        return restore(controller, arg)
    if name == 'weather':
        return weather(controller)
    if name == 'pet':
        return wander(controller, arg)
    raise ValueError(f'Unknown living event {name}')


def happen(controller, key):
    engine = controller.engine
    room, rule = happenings(engine)[key]
    n = living.count(engine, f'hap-{key}')
    living.due(engine)[f'hap|{key}'] = next_time(controller, rule, key, engine.day, n + 1)
    people = perceivers(engine, room, rule.get('audible', False))
    rng = controller.rng('happening', key, n, 'what')
    target = None
    if '{name}' in rule['text']:
        here = [p for p in people if household.present(engine, p, room)]
        if not here:
            return  # nobody there for it to happen to
        target = rng.choice(here)
    if rule['kind'] in ('atmosphere', 'news') and not people:
        return
    effects = rule.get('effects', {})
    state = living.state(engine)
    if 'disable_powered' in effects:
        until = engine.day + effects['minutes'] / 1440
        rooms = site_rooms(engine, room) if effects['disable_powered'] == 'site' else [room]
        for r in rooms:
            for obj, spec in living.objects(engine, r).items():
                if spec['powered']:
                    state['out_of_order'][f'{r}/{obj}'] = until
        state['restores'][key] = {'rooms': rooms, 'text': effects.get('restore_text', 'Things were working again.')}
        living.due(engine)[f'restore|{key}'] = until
    if 'route_delay_minutes' in effects and living.site(engine, room):
        state['delays'][living.site(engine, room)] = {'until': engine.day + effects['minutes'] / 1440,
                                                     'minutes': effects['route_delay_minutes']}
    if effects.get('close_conversations'):
        rooms = set(site_rooms(engine, room))
        for talk_key, session in sorted(engine.state['runtime'].get('conversations', {}).items()):
            if session['status'] != 'closed' and session['spec'].get('room') in rooms:
                household.interrupt(controller, talk_key, 'interrupted: ' + rule['id'])
    if target is not None and effects.get('target_needs'):
        living.change_needs(engine, target, effects['target_needs'])
    if rule['kind'] == 'news':
        topic = rng.choice(engine.state['config']['living']['news_topics'])
        text = news_line(controller, topic) or rule['text'].format(topic=topic)
    else:
        text = rule['text'].format(name=engine.label(target) if target else '')
    observations = {p: {'text': rule['self_text'] if p == target else text,
                        'source': 'direct', 'kind': 'direct', **({'encountered': [target]} if target and p != target else {})}
                    for p in people}
    if observations:
        household.deliver(controller, f'@happening:{key}:{n}', f'A {rule["kind"]} in the surroundings, not caused by anyone simulated.',
                          observations, routine=rule['kind'] == 'atmosphere')


def news_line(controller, topic):
    """The one place the surroundings use the model: a TV news sentence on a listed topic (live runs only)."""
    if controller.scripted:
        return None
    from .engine import validated_json
    def check(result):
        line = result.get('line')
        if not isinstance(line, str) or not line.strip() or len(line) > 300:
            raise ValueError('line must be one short sentence')
    result = validated_json('Write one short sentence a TV newsreader says about the topic, in a fictional town. No real '
                            'people\'s names. Return JSON with line.', {'task': 'news_headline', 'topic': topic},
                            check, controller.api, controller.model, 120)
    return 'On the TV news: ' + result['line'].strip()


def restore(controller, key):
    engine = controller.engine
    record = living.state(engine)['restores'].pop(key, None)
    if record is None:
        return
    people = sorted({p for r in record['rooms'] for p in perceivers(engine, r, False)})
    if people:
        household.deliver(controller, f'@happening:{key}:restored-{living.count(engine, f"restore-{key}")}',
                          'Something in the surroundings works again.',
                          {p: {'text': record['text'], 'source': 'direct', 'kind': 'direct'} for p in people}, routine=True)


def weather(controller):
    """One seeded weather chain; people near a window or outside notice each change."""
    engine = controller.engine
    cfg = engine.state['config']['living']
    state = living.state(engine)
    n = living.count(engine, 'weather')
    rng = controller.rng('weather', n + 1)
    row = cfg['weather']['transitions'][state['weather']['state']]
    pick, total = rng.random(), 0.0
    new = sorted(row)[-1]
    for name in sorted(row):
        total += row[name]
        if pick < total:
            new = name
            break
    state['weather'] = {'state': new, 'since': engine.day}
    living.due(engine)['weather|'] = engine.day + rng.expovariate(1 / cfg['weather']['mean_hours']) / 24
    rooms = engine.state['config']['household']['rooms']
    people = sorted({p for r, spec in rooms.items() if spec.get('kind') in cfg['windows'] for p in perceivers(engine, r, False)})
    if people:
        household.deliver(controller, f'@weather:{n}', 'The weather changes.',
                          {p: {'text': cfg['weather']['texts'][new], 'source': 'direct', 'kind': 'direct'} for p in people}, routine=True)


def wander(controller, cid):
    """A creature's own little routine: it moves between its rooms and does cat or dog things; people present notice."""
    engine = controller.engine
    spec = creatures(engine)[cid]
    kind = engine.state['config']['living']['creature_kinds'][spec['kind']]
    state = living.state(engine)['creatures'][cid]
    n = living.count(engine, f'pet-{cid}')
    rng = controller.rng('creature', cid, n + 1)
    living.due(engine)[f'pet|{cid}'] = engine.day + rng.expovariate(1 / kind['mean_minutes']) / 1440
    hour = (engine.day - floor(engine.day)) * 24
    if not any(a <= hour < b for a, b in kind['active_hours']):
        return  # asleep somewhere
    moved = len(spec['rooms']) > 1 and rng.random() >= kind['stay_chance']
    if moved:
        state['room'] = rng.choice(sorted(r for r in spec['rooms'] if r != state['room']))
    doing = rng.choice(kind['behaviours'])
    name = f'{spec["name"]} the {spec["kind"]}'
    people = perceivers(engine, state['room'], False)
    for p in people:
        living.saw(engine, p, cid, state['room'])
    if people:
        household.deliver(controller, f'@creature:{cid}:{n}', 'A pet goes about its own routine.',
                          {p: {'text': f'{name} wandered in, {doing}.' if moved else f'{name} was {doing}.',
                               'source': 'direct', 'kind': 'direct'} for p in people}, routine=True)
