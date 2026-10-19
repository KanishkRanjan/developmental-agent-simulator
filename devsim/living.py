"""Living world, game style (The Sims as the model): needs, furnished rooms, whereabouts and free-time choices.

No model calls here. Needs fall lazily from the last update (nothing ticks); rooms are furnished from the catalog in
devsim/policies/living.json by room kind; each person knows where others are only from what they perceived. At
each inner thought (Lifetime._think) a person gets a short menu ranked like Sims advertisements (need relief minus a
travel penalty); the model picks from it, or a scripted run takes the top entry. Every number is a provisional
design default [D]. The surroundings that act on their own live in devsim/surroundings.py.
"""
from copy import deepcopy
import json
from math import floor

from . import POLICY_DIR
from . import household

CONFIG_PATH = POLICY_DIR / 'living.json'
NEEDS = ('hunger', 'energy', 'social', 'fun', 'hygiene')
LOW_WORDS = {'hunger': ('hungry', 'very hungry'), 'energy': ('tired', 'exhausted'), 'social': ('lonely', 'very lonely'),
             'fun': ('bored', 'very bored'), 'hygiene': ('in need of a wash', 'grubby and uncomfortable')}
SETTINGS = ('needs', 'social_per_turn', 'menu_size', 'stay_score', 'travel_penalty_per_minute', 'same_room_talk_bonus',
            'whereabouts_hours', 'bedtime_minutes_before', 'catalog', 'windows', 'happenings', 'news_topics', 'weather',
            'creature_kinds')
HAPPENING_KINDS = ('atmosphere', 'incident', 'offstage', 'news')
HOME_KINDS = ('bedroom', 'kitchen', 'living_room', 'bathroom')  # a site with any of these is someone's home


def parameters():
    return {k: v for k, v in json.loads(CONFIG_PATH.read_text()).items() if k != 'description'}


def configure(engine, overrides=None):
    """Store the living policy in the world config (checkpointed); a top-level key in overrides replaces the default."""
    from .engine import number
    overrides = overrides or {}
    if not isinstance(overrides, dict) or set(overrides) - set(SETTINGS):
        raise ValueError(f'living settings take only {SETTINGS}')
    settings = {**parameters(), **deepcopy(overrides)}
    validate(settings)
    if 'household' not in engine.state['config']:
        raise ValueError('The living world needs household rooms')
    current = engine.state['config'].get('living')
    if current is not None and current != settings:
        raise ValueError('Cannot silently replace living policy')
    engine.state['config']['living'] = settings


def validate(settings):
    from .engine import number
    if set(settings['needs']) != set(NEEDS):
        raise ValueError(f'needs must be exactly {NEEDS}')
    for name, rate in settings['needs'].items():
        if not isinstance(rate, dict) or set(rate) != {'awake_per_hour', 'asleep_per_hour', 'start'}:
            raise ValueError(f'need {name} takes awake_per_hour, asleep_per_hour and start')
        number(rate['awake_per_hour'], -1, 1, f'{name} awake_per_hour')
        number(rate['asleep_per_hour'], -1, 1, f'{name} asleep_per_hour')
        number(rate['start'], 0, 1, f'{name} start')
    for key, low, high in [('social_per_turn', 0, 1), ('menu_size', 2, 20), ('stay_score', 0, 5), ('travel_penalty_per_minute', 0, 1),
                           ('same_room_talk_bonus', 0, 5), ('whereabouts_hours', 0, 72), ('bedtime_minutes_before', 0, 120)]:
        number(settings[key], low, high, key)
    if not isinstance(settings['catalog'], dict):
        raise ValueError('catalog maps room kinds to objects')
    for kind, objects in settings['catalog'].items():
        validate_objects(objects, f'catalog.{kind}')
    if not isinstance(settings['windows'], list) or set(settings['windows']) - set(settings['catalog']):
        raise ValueError('windows lists room kinds from the catalog')
    if not isinstance(settings['happenings'], dict) or set(settings['happenings']) - set(settings['catalog']):
        raise ValueError('happenings map catalog room kinds to lists')
    for kind, rules in settings['happenings'].items():
        for rule in rules:
            validate_happening(rule, f'happenings.{kind}')
    if not isinstance(settings['news_topics'], list) or not all(isinstance(t, str) and t.strip() for t in settings['news_topics']):
        raise ValueError('news_topics is a list of short topics')
    weather = settings['weather']
    states = set(weather.get('transitions', {}))
    if weather.get('start') not in states or set(weather.get('texts', {})) != states:
        raise ValueError('weather needs start, transitions and texts over the same states')
    for state, row in weather['transitions'].items():
        if set(row) - states or abs(sum(row.values()) - 1) > 1e-9:
            raise ValueError(f'weather transitions from {state} must be probabilities over known states')
    number(weather['mean_hours'], .25, 48, 'weather mean_hours')
    number(weather['rain_travel_factor'], 1, 3, 'rain_travel_factor')
    for kind, spec in settings['creature_kinds'].items():
        if set(spec) != {'active_hours', 'mean_minutes', 'stay_chance', 'behaviours', 'play'} or not spec['behaviours']:
            raise ValueError(f'creature kind {kind} needs active_hours, mean_minutes, stay_chance, behaviours and play')
        number(spec['mean_minutes'], 1, 1440, 'creature mean_minutes')
        number(spec['stay_chance'], 0, 1, 'creature stay_chance')
        validate_activity(spec['play'], f'creature_kinds.{kind}.play')


def validate_objects(objects, label):
    from .engine import number
    if not isinstance(objects, dict):
        raise ValueError(f'{label} maps object ids to objects')
    for key, spec in objects.items():
        if not isinstance(spec, dict) or set(spec) != {'label', 'capacity', 'powered', 'activities'} or '/' in key:
            raise ValueError(f'{label}.{key} needs label, capacity, powered and activities')
        number(spec['capacity'], 1, 100, f'{label}.{key} capacity')
        for act, activity in spec['activities'].items():
            if '/' in act:
                raise ValueError('activity ids cannot contain /')
            validate_activity(activity, f'{label}.{key}.{act}', verb=True)


def validate_activity(activity, label, verb=False):
    from .engine import number
    keys = {'label', 'minutes', 'needs'} | ({'verb'} if verb else set())
    if not isinstance(activity, dict) or set(activity) - {'skill'} != keys or not all(isinstance(activity[k], str) for k in keys - {'minutes', 'needs'}):
        raise ValueError(f'{label} needs {sorted(keys)}')
    if 'skill' in activity:  # the activity is practice of a skill with these attributes (devsim/skills.py)
        from .skills import attributes
        attributes(activity['skill'])
    number(activity['minutes'], 1, 600, f'{label} minutes')
    if not isinstance(activity['needs'], dict) or set(activity['needs']) - set(NEEDS):
        raise ValueError(f'{label} needs map need names to changes')
    for value in activity['needs'].values():
        number(value, -1, 1, f'{label} need change')


def validate_happening(rule, label):
    from .engine import number
    allowed = {'id', 'kind', 'text', 'self_text', 'hours', 'rate_per_day', 'audible', 'effects', 'room'}
    if not isinstance(rule, dict) or set(rule) - allowed or not {'id', 'kind', 'text', 'hours', 'rate_per_day'} <= set(rule):
        raise ValueError(f'{label}: a happening needs id, kind, text, hours and rate_per_day')
    if rule['kind'] not in HAPPENING_KINDS or not isinstance(rule['text'], str) or '/' in rule['id']:
        raise ValueError(f'{label}.{rule["id"]}: kind is one of {HAPPENING_KINDS}')
    hours = rule['hours']
    if not isinstance(hours, list) or len(hours) != 2:
        raise ValueError(f'{label}.{rule["id"]}: hours are [start, end] within one day')
    number(hours[0], 0, 24, 'happening start hour')
    number(hours[1], hours[0] + 1e-6, 24, 'happening end hour')
    number(rule['rate_per_day'], 0, 100, 'happening rate_per_day')
    if ('{name}' in rule['text']) != ('self_text' in rule):
        raise ValueError(f'{label}.{rule["id"]}: a happening to someone ({{name}}) needs self_text, and only then')
    effects = rule.get('effects', {})
    if set(effects) - {'disable_powered', 'minutes', 'restore_text', 'route_delay_minutes', 'close_conversations', 'target_needs'}:
        raise ValueError(f'{label}.{rule["id"]}: unknown effect')
    if effects.get('disable_powered', 'site') not in ('site', 'room') or effects.get('close_conversations', 'site') != 'site':
        raise ValueError(f'{label}.{rule["id"]}: disable_powered is site or room; close_conversations is site')
    if ('disable_powered' in effects or 'route_delay_minutes' in effects) and 'minutes' not in effects:
        raise ValueError(f'{label}.{rule["id"]}: a lasting effect needs minutes')
    if 'minutes' in effects:
        number(effects['minutes'], 1, 1440, 'effect minutes')
    for value in effects.get('target_needs', {}).values():
        number(value, -1, 1, 'target need change')


def validate_household(settings):
    """Room kind, site and objects; creatures and extra happenings (called by household.validate)."""
    defaults = parameters()
    rooms = settings['rooms']
    for key, room in rooms.items():
        if 'kind' in room and room['kind'] not in defaults['catalog']:
            raise ValueError(f'Room {key} kind must be one of {sorted(defaults["catalog"])}')
        if 'site' in room and (not isinstance(room['site'], str) or not room['site'].strip()):
            raise ValueError(f'Room {key} site is a short name such as home or school')
        validate_objects(room.get('objects', {}), f'rooms.{key}.objects')
    for rule in settings.get('happenings', []):
        validate_happening(rule, 'household.happenings')
        if rule.get('room') not in rooms:
            raise ValueError('An extra happening needs a known room')
    ids = set()
    for creature in settings.get('creatures', []):
        if not isinstance(creature, dict) or set(creature) != {'id', 'name', 'kind', 'rooms', 'room'} or creature['id'] in ids:
            raise ValueError('A creature needs a unique id, name, kind, rooms and a starting room')
        ids.add(creature['id'])
        if creature['kind'] not in defaults['creature_kinds'] or not creature['rooms'] or set(creature['rooms']) - set(rooms) \
                or creature['room'] not in creature['rooms']:
            raise ValueError(f'Creature {creature["id"]}: a known kind, known rooms and a starting room among them')


# State

def state(engine):
    return engine.state.setdefault('living', {'needs': {}, 'doing': {}, 'visits': {}, 'out_of_order': {}, 'delays': {},
                                              'creatures': {}, 'weather': None, 'restores': {}, 'counts': {}})


def due(engine):
    return engine.state['runtime'].setdefault('living_due', {})


def count(engine, key):
    counts = state(engine)['counts']
    counts[key] = counts.get(key, 0) + 1
    return counts[key] - 1


def start(controller):
    """Idempotent: needs, bedtimes and the surroundings' clocks (also on resume)."""
    engine = controller.engine
    cfg = engine.state['config']['living']
    living = state(engine)
    for owner, agent in engine.state['agents'].items():
        if agent['alive']:
            living['needs'].setdefault(owner, {'day': engine.day, 'values': {n: cfg['needs'][n]['start'] for n in NEEDS}})
            if home_room(engine, owner) is not None:
                due(engine).setdefault(f'bed|{owner}', next_bedtime(engine, owner, engine.day))
    from . import surroundings
    surroundings.start(controller)


# Needs

def windows(engine, owner):
    return engine.state['config']['household'].get('routines', {}).get(owner, {}).get('available_hours', [[0, 24]])


def segments(engine, owner, start, end):
    """(hours, awake) pieces of [start, end) in order, split at the person's waking-window edges."""
    spans = windows(engine, owner)
    bounds = sorted({0, 24, *(x for w in spans for x in w)})
    t = start
    while t < end:
        day = floor(t)
        hour = (t - day) * 24
        stop = min(end, day + min(b for b in bounds if b > hour + 1e-9) / 24)
        if stop <= t:
            stop = min(end, t + 1e-9)
        yield (stop - t) * 24, any(a <= hour < b for a, b in spans)
        t = stop


def needs(engine, owner, day=None):
    """Satisfaction per need in [0, 1] (1 = fully met) at day; read-only."""
    day = engine.day if day is None else day
    cfg = engine.state['config']['living']['needs']
    record = state(engine)['needs'].get(owner)
    if record is None:
        return {n: cfg[n]['start'] for n in NEEDS}
    values = dict(record['values'])
    for hours, awake in segments(engine, owner, record['day'], day):
        for n in NEEDS:
            values[n] = min(1.0, max(0.0, values[n] - cfg[n]['awake_per_hour' if awake else 'asleep_per_hour'] * hours))
    return values


def change_needs(engine, owner, deltas):
    values = needs(engine, owner)
    for n, d in deltas.items():
        values[n] = min(1.0, max(0.0, values[n] + d))
    state(engine)['needs'][owner] = {'day': engine.day, 'values': values}


def words(engine, owner):
    """Low needs as plain language for the model; numbers stay internal."""
    values = needs(engine, owner)
    return [LOW_WORDS[n][values[n] < .15] for n in NEEDS if values[n] < .35]


def fatigue(engine, owner, now):
    """0 until energy falls below half, then up to 1: feeds attention's fatigue provider."""
    if 'living' not in engine.state['config'] or owner not in engine.state['agents']:
        return 0.0
    return max(0.0, (.5 - needs(engine, owner, now)['energy']) / .5)


# Map

def room(engine, key):
    return engine.state['config']['household']['rooms'][key]


def site(engine, key):
    return room(engine, key).get('site') if key else None


def objects(engine, key):
    """The room's furniture: the catalog for its kind, plus or replaced by the room's own objects."""
    cfg = engine.state['config']['living']
    spec = room(engine, key)
    return {**deepcopy(cfg['catalog'].get(spec.get('kind', 'other'), {})), **deepcopy(spec.get('objects', {}))}


def usable(engine, key, obj, spec):
    until = state(engine)['out_of_order'].get(f'{key}/{obj}')
    if until is not None and until > engine.day:
        return False
    users = sum(1 for d in state(engine)['doing'].values() if d['room'] == key and d.get('object') == obj and d['phase'] == 'busy')
    return users < spec['capacity']


def minutes_between(engine, a, b):
    """Travel minutes, 0 within a room or a site, None when unreachable (different sites without a route)."""
    if a is None or b is None:
        return None
    if a == b:
        return 0
    minutes = household.route_minutes(engine, a, b)
    if minutes:
        return minutes
    sa, sb = site(engine, a), site(engine, b)
    return 0 if sa is None or sb is None or sa == sb else None


def home_room(engine, owner):
    return engine.state['config']['household'].get('locations', {}).get(owner)


def allowed(engine, owner, key):
    """Public places, and one's own home; another household's home is off limits (smoke test: a classmate walked in
    from school and cooked in the family kitchen)."""
    s = site(engine, key)
    if s is None or s == site(engine, home_room(engine, owner)):
        return True
    return not any(spec.get('site') == s and spec.get('kind') in HOME_KINDS
                   for spec in engine.state['config']['household']['rooms'].values())


# Whereabouts

def saw(engine, observer, other, where):
    """observer now believes other is in room `where` (None: left, whereabouts unknown)."""
    if 'living' in engine.state['config'] and observer in engine.state['agents'] and observer != other:
        engine.agent(observer).setdefault('last_seen', {})[other] = [where, engine.day]


def whereabouts(engine, owner):
    """{person: (room, day)} from perception only: people here now, plus recent sightings and sounds."""
    hours = engine.state['config']['living']['whereabouts_hours']
    known = {p: tuple(v) for p, v in engine.agent(owner).get('last_seen', {}).items()
             if v[0] is not None and engine.day - v[1] <= hours / 24}
    here = household.location(engine, owner)
    for p in engine.state['agents']:
        if p != owner and household.present(engine, p, here):
            known[p] = (here, engine.day)
    return known


def name(engine, key):
    """A person's label, or a creature's name."""
    if key in engine.state['entities']:
        return engine.label(key)
    return next((f'{c["name"]} the {c["kind"]}' for c in engine.state['config']['household'].get('creatures', []) if c['id'] == key), key)


def talking(engine, owner):
    return any(s['status'] != 'closed' and owner in s['active'] for s in engine.state['runtime'].get('conversations', {}).values())


# Choosing

def menu(engine, owner):
    """Up to menu_size options, best first, ranked like Sims advertisements; 'stay' is always offered."""
    cfg = engine.state['config']['living']
    living = state(engine)
    here = household.location(engine, owner)
    values = needs(engine, owner)
    weight = {n: 2 * (1 - values[n]) ** 2 for n in NEEDS}
    relief = lambda deltas: sum(max(d, 0) * weight[n] - max(-d, 0) * .2 for n, d in deltas.items())
    penalty = cfg['travel_penalty_per_minute']
    doing = living['doing'].get(owner)
    busy = doing is not None and doing['phase'] == 'busy'
    options = [{'id': 'stay', 'label': f'carry on {doing["verb"]}' if busy else 'stay where you are',
                'score': cfg['stay_score'] + (.3 if busy else 0)}]
    if here is None:
        return options  # in transit
    label = lambda r: engine.state['config']['household']['rooms'][r]['label']
    away = lambda r, m: '' if r == here else f' ({label(r)}, {m:g} min away)' if m else f' ({label(r)})'
    for key in engine.state['config']['household']['rooms']:
        m = minutes_between(engine, here, key)
        sleepers = {p for p in engine.state['agents'] if home_room(engine, p) == key}
        if m is None or not allowed(engine, owner, key) or (room(engine, key).get('kind') == 'bedroom' and sleepers and owner not in sleepers):
            continue  # someone else's bedroom furniture is theirs; visiting them there to talk is still fine
        for obj, spec in objects(engine, key).items():
            if not usable(engine, key, obj, spec):
                continue
            for act, activity in spec['activities'].items():
                options.append({'id': f'do:{key}/{obj}/{act}', 'label': activity['label'] + away(key, m),
                                'score': relief(activity['needs']) - penalty * m})
    agent = engine.agent(owner)
    for p, (where, _) in whereabouts(engine, owner).items():
        if p not in engine.state['agents'] or not engine.agent(p)['alive']:
            continue
        m = minutes_between(engine, here, where)
        if m is None or not allowed(engine, owner, where) or (where != here and room(engine, where).get('kind') == 'bathroom'):
            continue  # nobody walks into an occupied bathroom to chat
        close = 1 + max(0, agent['relationships'].get(p, {}).get('closeness', 0))
        options.append({'id': f'talk:{p}', 'label': ('talk to ' if where == here else 'go and talk to ') + engine.label(p) + away(where, m),
                        'score': .25 * weight['social'] * close + (cfg['same_room_talk_bonus'] if where == here else 0) - penalty * m})
    present = {p for p, (where, _) in whereabouts(engine, owner).items() if where == here}
    channels = engine.state['config']['household'].get('channels', {})
    for p in sorted({m for c in channels.values() if owner in c['members'] for m in c['members']} - {owner} - present):
        if engine.agent(p)['alive']:
            close = 1 + max(0, agent['relationships'].get(p, {}).get('closeness', 0))
            options.append({'id': f'message:{p}', 'label': f'send {engine.label(p)} a message', 'score': .15 * weight['social'] * close})
    kinds = cfg['creature_kinds']
    for cid, creature in living['creatures'].items():
        spec = next(c for c in engine.state['config']['household'].get('creatures', []) if c['id'] == cid)
        if creature['room'] == here:
            play = kinds[spec['kind']]['play']
            options.append({'id': f'play:{cid}', 'label': f'{play["label"]} {spec["name"]} the {spec["kind"]}', 'score': relief(play['needs'])})
    home = home_room(engine, owner)
    if home and here != home and minutes_between(engine, here, home) == 0:
        options.append({'id': f'go:{home}', 'label': 'go to your own room' + away(home, 0), 'score': .05})
    # Activities compete for menu_size slots; people are always offered (up to five), since a reason to seek someone
    # out, such as worry, lives in the thought and not in the need scores.
    if 'skills' in engine.state['config']:  # wanting to practise (motivation; conscientiousness, anxiety, learned value)
        from . import skills
        practising = {o['id']: o for o in options if o['id'].startswith('do:')}
        verbs = {}
        for oid in practising:
            where, obj, act_id = oid[3:].split('/')
            spec = objects(engine, where)[obj]['activities'][act_id]
            if 'skill' in spec:
                verbs[oid] = spec['verb']
        if verbs:
            want = skills.practice_wanting(engine, owner, sorted(set(verbs.values())))
            weight = engine.state['config']['skills']['practice_menu_weight']
            for oid, verb in verbs.items():
                practising[oid]['score'] += weight * want[verb]
    rank = lambda items, n: sorted(items, key=lambda o: (-o['score'], o['id']))[:n]
    social = lambda o: o['id'].split(':')[0] in ('talk', 'message', 'play')
    if 'hormones' in engine.state['config']:  # learned wanting and tonic initiative shape whom to seek out
        from . import hormones
        people = [o for o in options if o['id'].split(':')[0] in ('talk', 'message')]
        want = hormones.wanting_scores(engine, owner, sorted({o['id'].split(':')[1] for o in people}))
        boost = hormones.initiative(engine, owner)
        weight = engine.state['config']['hormones']['menu_wanting_weight']
        for o in people:
            o['score'] = (o['score'] + weight * want[o['id'].split(':')[1]]) * boost
    things = rank([o for o in options[1:] if not social(o)], int(cfg['menu_size']) - 1)
    people = rank([o for o in options[1:] if social(o)], 5)
    return rank([options[0], *things, *people], len(options))


def act(controller, owner, choice, about, key):
    """Carry out a menu choice: walk, start an activity, go and talk, message, or play. Nothing for 'stay'."""
    engine = controller.engine
    living = state(engine)
    kind, _, target = choice.partition(':')
    if kind == 'stay':
        return
    if kind == 'go':
        living['doing'].pop(owner, None)
        household.travel(controller, owner, target, key)
        return
    if kind == 'message':
        household.start_conversation(controller, owner, target, {'topic': about or 'Checking in.', 'max_turns': 40}, f'msg-{key}')
        return
    if kind == 'talk':
        where = whereabouts(engine, owner)[target][0]
        arrival = household.travel(controller, owner, where, key)
        if arrival is not None:
            living['doing'].pop(owner, None)
            living['visits'][owner] = {'target': target, 'about': about or 'How are you doing?', 'key': key}
            due(engine)[f'visit|{owner}'] = arrival
        return
    if kind == 'do':
        where, obj, activity = target.split('/')
        spec = objects(engine, where)[obj]['activities'][activity]
        record = {'room': where, 'object': obj, 'verb': spec['verb'], 'minutes': spec['minutes'], 'needs': spec['needs'],
                  **({'skill': spec['skill']} if 'skill' in spec else {})}
    else:  # play
        creature = next(c for c in engine.state['config']['household']['creatures'] if c['id'] == target)
        play = engine.state['config']['living']['creature_kinds'][creature['kind']]['play']
        where = living['creatures'][target]['room']
        record = {'room': where, 'object': None, 'verb': f'playing with {creature["name"]} the {creature["kind"]}',
                  'minutes': play['minutes'], 'needs': play['needs']}
    arrival = household.travel(controller, owner, where, key)
    if arrival is not None:
        living['doing'][owner] = {**record, 'phase': 'going'}
        due(engine)[f'do|{owner}'] = arrival


# Timed steps

def step(controller, key):
    engine = controller.engine
    del due(engine)[key]
    name, _, arg = key.partition('|')
    if name == 'do':
        return doing(controller, arg)
    if name == 'visit':
        return visit(controller, arg)
    if name == 'bed':
        return bedtime(controller, arg)
    from . import surroundings
    surroundings.step(controller, name, arg)


def say(controller, event_id, observations, routine=True, target=None):
    household.deliver(controller, event_id, 'Everyday living: what people do and notice around them.',
                      {p: {'text': text, 'source': 'self' if p == owner else 'direct', 'kind': 'direct',
                           **({'encountered': [owner]} if p != owner else {}),
                           **({'outcome_target': target} if target and p == owner else {})}
                       for owner, texts in observations.items() for p, text in texts.items()}, routine=routine)


def doing(controller, owner):
    """Start an activity on arrival, or finish it; leaving the room before the end means it never completes."""
    engine = controller.engine
    living = state(engine)
    record = living['doing'].get(owner)
    if record is None or not engine.agent(owner)['alive']:
        return
    here = household.location(engine, owner)
    n = count(engine, f'do-{owner}')
    if here != record['room']:
        living['doing'].pop(owner)
        return
    if record['phase'] == 'going':
        spec = objects(engine, here).get(record['object']) if record['object'] else None
        if spec is not None and not usable(engine, here, record['object'], spec):
            living['doing'].pop(owner)
            say(controller, f'@living:{owner}:{n}', {owner: {owner: f'I wanted to use {spec["label"]}, but I could not right now.'}})
            return
        record['phase'] = 'busy'
        due(engine)[f'do|{owner}'] = engine.day + record['minutes'] / 1440
        others = [p for p in engine.state['agents'] if p != owner and household.present(engine, p, here) and household.available(engine, p)]
        for p in others:
            saw(engine, p, owner, here)
        say(controller, f'@living:{owner}:{n}', {owner: {owner: f'I started {record["verb"]}.',
                                                         **{p: f'{engine.label(owner)} started {record["verb"]}.' for p in others}}})
        return
    living['doing'].pop(owner)
    change_needs(engine, owner, record['needs'])
    if 'skill' in record and 'skills' in engine.state['config']:  # finishing it was practice
        from . import skills
        skills.practice(engine, owner, record['verb'], f'@living:{owner}:{n}', attrs=record['skill'])
    say(controller, f'@living:{owner}:{n}', {owner: {owner: f'I finished {record["verb"]}.'}},
        target='activity:' + (record['object'] or 'pet') + ':' + record['verb'])


def visit(controller, owner):
    """Arrived to talk to someone: start the conversation, or notice they are asleep, busy or gone."""
    engine = controller.engine
    plan = state(engine)['visits'].pop(owner, None)
    if plan is None or not engine.agent(owner)['alive']:
        return
    target, here = plan['target'], household.location(engine, owner)
    name = engine.label(target)
    if household.present(engine, target, here) and household.available(engine, target) and not talking(engine, target):
        household.start_conversation(controller, owner, target, {'topic': plan['about'], 'max_turns': 40}, f'visit-{plan["key"]}')
        return
    if not household.present(engine, target, here):
        text = f'I went to find {name}, but {name} was not there.'
        saw(engine, owner, target, None)
    elif not household.available(engine, target):
        text = f'I went to find {name}, but {name} was asleep.'
    else:
        text = f'I went to find {name}, but {name} was busy talking with someone.'
    say(controller, f'@living:{owner}:visit-{count(engine, f"visit-{owner}")}', {owner: {owner: text}})


def next_bedtime(engine, owner, after):
    """bedtime_minutes_before the end of the person's last waking window of the day, next after `after`."""
    end = max(b for _, b in windows(engine, owner)) / 24
    before = engine.state['config']['living']['bedtime_minutes_before'] / 1440
    day = floor(after)
    while day + end - before <= after:
        day += 1
    return day + end - before


def bedtime(controller, owner):
    """Near the end of the day a person heads back to their own room, walking or travelling home if needed."""
    engine = controller.engine
    if not engine.agent(owner)['alive']:
        return
    due(engine)[f'bed|{owner}'] = next_bedtime(engine, owner, engine.day + 1e-6)
    here, home = household.location(engine, owner), home_room(engine, owner)
    if here is None or here == home or talking(engine, owner) or minutes_between(engine, here, home) is None:
        return
    state(engine)['doing'].pop(owner, None)
    household.travel(controller, owner, home, f'bed-{owner}-{count(engine, f"bed-{owner}")}')
