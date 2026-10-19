"""Build a simulation from a step-by-step design (the control panel's New tab). No terminal needed.

A design (work/designs/<slug>/design.json) names places from templates, main and side characters, relationships, a
background crowd, modules, a duration and how to begin. build() turns it into a compiled world:
  1. one small model call per person fills what the design leaves open (facets implied by the description, up to 3
     first-person background sentences, and for main characters goals and one situation of their own). Small replies
     fit the 8k context; the one-shot draft of a whole world did not (18 October: its repair was cut off mid-reply);
  2. the scenario is assembled in the author vocabulary (room kinds, sites, routes, groups, routines) and compiled with
     author.compile_scenario, with higher limits for builder designs;
  3. personality sliders and relationships are applied to the compiled world;
  4. the beginning: either the model fills each adult's past (biography.expand) or a cheap scripted fast-forward
     ages everyone by N years before the live run starts (history labelled scripted).
Scripted builds (api=None) make no model call and keep sampled personalities.
"""
from copy import deepcopy
import json
from pathlib import Path
import re

from .engine import FACET_NAMES

ROOT = Path(__file__).resolve().parents[1]
DESIGNS = ROOT / 'work' / 'designs'
BUILDER_LIMITS = {'people': 30, 'situations': 60, 'background': 3, 'goals': 3}
FF_RATE_SCALE = .1  # fast-forward keeps one in ten situation occurrences: highlights, not a full life (design default)

# Places: rooms by kind for each template (homes get a bedroom per member).
TEMPLATES = {
    'home': {'label': 'home', 'rooms': [('kitchen', 'kitchen'), ('living_room', 'living room'), ('bathroom', 'bathroom')]},
    'school': {'label': 'school', 'rooms': [('classroom', 'classroom'), ('cafeteria', 'cafeteria'), ('lab', 'lab')]},
    'office': {'label': 'office', 'rooms': [('office', 'office')]},
    'hospital': {'label': 'hospital', 'rooms': [('ward', 'ward')]},
    'park': {'label': 'park', 'rooms': [('outdoors', 'park')]},
}
PLACE_ART = {
    'home': ['   /\\   ', '  /  \\  ', ' | [] | ', ' |_||_| '],
    'school': [' _____  ', '|ABC  | ', '|_____| ', ' |   |  '],
    'office': [' ____   ', '|=|=|=| ', '|=|=|=| ', '|_|_|_| '],
    'hospital': ['  ___   ', ' | + |  ', ' |___|  ', ' |   |  '],
    'park': ['  @@@   ', ' @@@@@  ', '   |    ', ' __|__  '],
}
# Daily hours: waking windows and, for a workplace, when the group gathers there.
HOURS = {
    'student': {'awake': [[7, 22]], 'start': 8.5, 'duration': 6.5, 'kind': 'class'},
    'works days': {'awake': [[6.5, 22.5]], 'start': 8.5, 'duration': 8.0, 'kind': 'staff'},
    'evening shift': {'awake': [[0, 1], [9, 24]], 'start': 14.5, 'duration': 8.25, 'kind': 'shift'},
    'at home': {'awake': [[6, 22]]},
}
FAMILY = {'parent of': None, 'grandparent of': None, 'sibling': ('sibling', .7, .6), 'partner': ('partner', .8, .8)}
CROWD = {'off': None, 'small': {'grid': 8}, 'large': {'grid': 16}}
CLASS_TOPICS = ['The school day', 'A surprise quiz', 'Plans for the weekend', 'Something funny online', 'Homework', 'The cafeteria food']


def slug(text):
    return re.sub(r'[^a-z0-9]+', '_', str(text).lower()).strip('_') or 'x'


def new_design(title):
    return {'title': title, 'summary': '', 'seed': 7, 'duration_days': 30, 'places': [], 'routes': {}, 'people': [],
            'relationships': [], 'crowd': 'off', 'modules': {'living': True, 'hormones': True, 'attention': True, 'sleep': True, 'skills': True},
            'begin': {'mode': 'fill', 'years': 0}}


def save(design):
    folder = DESIGNS / slug(design['title'])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'design.json').write_text(json.dumps(design, indent=2) + '\n')
    return folder


def load(folder):
    return json.loads((Path(folder) / 'design.json').read_text())


def saved_designs():
    return sorted(DESIGNS.glob('*/design.json'), key=lambda p: -p.stat().st_mtime) if DESIGNS.exists() else []


def check_design(design):
    """Problems a person can fix in the builder, in plain words (empty when it can be built)."""
    problems = []
    places = {p['id']: p for p in design['places']}
    ids = [p['id'] for p in design['people']]
    if not design['people']:
        problems.append('Add at least one main character.')
    if len(set(ids)) != len(ids):
        problems.append('Two people share a name; give them different names.')
    for person in design['people']:
        if places.get(person.get('home'), {}).get('template') != 'home':
            problems.append(f'{person["name"]} needs a home.')
        if person.get('hours') in ('student', 'works days', 'evening shift') and person.get('place') not in places:
            problems.append(f'{person["name"]} needs a school or workplace to go to.')
        if not 0 < float(person.get('age', 0)) <= 100:
            problems.append(f'{person["name"]} needs an age between 1 and 100.')
    if design['begin']['mode'] == 'fast_forward':
        for person in design['people']:
            if float(person['age']) - float(design['begin']['years']) < 1:
                problems.append(f'{person["name"]} would not be born yet {design["begin"]["years"]} years earlier.')
    return problems


# 1. Per-person fill

def fill_person(person, design, api, model):
    """One small model call: facets the description implies, background, and for main characters goals and a situation."""
    from .engine import number, validated_json
    main = person['role'] == 'main'
    homes_kinds = ['bedroom', 'kitchen', 'living_room']
    place = next((p for p in design['places'] if p['id'] == person.get('place')), None)
    kinds = homes_kinds + [k for k, _ in TEMPLATES[place['template']]['rooms']] if place else homes_kinds
    def check(result):
        facets = result.get('facets', {})
        if not isinstance(facets, dict) or len(facets) > 10 or set(facets) - set(FACET_NAMES):
            raise ValueError('facets maps up to 10 facet codes to percentiles')
        for v in facets.values():
            number(v, 0, 100, 'facet')
        bg = result.get('background', [])
        if not isinstance(bg, list) or len(bg) > 3 or not all(isinstance(s, str) and 0 < len(s) <= 220 for s in bg):
            raise ValueError('background is up to 3 short first-person sentences')
        if main:
            goals = result.get('goals', [])
            if not person.get('goals') and (not isinstance(goals, list) or not 1 <= len(goals) <= 3 or
                                            not all(isinstance(g, dict) and g.get('description') for g in goals)):
                raise ValueError('goals: 1-3 objects with a description')
            s = result.get('situation')
            if not isinstance(s, dict) or s.get('room_kind') not in kinds or not isinstance(s.get('situation'), str):
                raise ValueError(f'situation needs a situation text and a room_kind from {kinds}')
            hours = s.get('hours')
            if not isinstance(hours, list) or len(hours) != 2 or not 0 <= hours[0] < hours[1] <= 24:
                raise ValueError('situation hours are [start, end] within one day')
            options = s.get('options')
            if not isinstance(options, list) or len(options) != 2:
                raise ValueError('situation needs exactly 2 options')
            for o in options:
                for k in ('label', 'success_text', 'failure_text'):
                    if not isinstance(o.get(k), str) or not o[k].strip():
                        raise ValueError(f'each option needs {k}')
                number(o.get('success_probability'), 0, 1, 'success_probability')
                number(o.get('valence_success'), -1, 1, 'valence_success')
                number(o.get('valence_failure'), -1, 1, 'valence_failure')
    ask = ('Fill in a fictional person for a social simulation from the researcher\'s design. Return JSON with facets (up to '
           '10 facet codes from facet_codes to percentiles, only traits the description implies), background (up to 3 short '
           'first-person sentences they know about their own life, no other named people)' +
           (', goals (1-3 objects with description and priority 0-1, only if given_goals is empty), and situation: something '
            'they do on their own on an ordinary day, with situation (second person), room_kind (one of room_kinds), hours '
            '[start, end], and exactly 2 options, each with label, success_probability, valence_success, valence_failure '
            '(-1 to 1), success_text and failure_text (first person)' if main else '') + '.')
    context = {'task': 'fill_person', 'name': person['name'], 'age_years': person['age'], 'description': person.get('description', ''),
               'role': 'main character' if main else 'side character', 'given_goals': person.get('goals', []),
               'daily_life': person.get('hours', 'at home'), 'room_kinds': kinds, 'world': design.get('summary', ''),
               'facet_codes': list(FACET_NAMES)}
    return validated_json(ask, context, check, api, model, 900)


def scripted_fill(person, design):
    """No model: a sampled personality, the given goals (or one from the description) and a quiet evening situation."""
    out = {'facets': {}, 'background': []}
    if person['role'] == 'main':
        out['goals'] = person.get('goals') or [{'description': person.get('description') or 'Get through the day well.', 'priority': .6}]
        out['situation'] = {'situation': 'You have a quiet hour to yourself at home.', 'room_kind': 'bedroom', 'hours': [18, 21],
                            'options': [{'label': 'Do something you enjoy', 'success_probability': .8, 'valence_success': .4,
                                         'valence_failure': -.1, 'success_text': 'I enjoyed the hour.', 'failure_text': 'It did not help much.'},
                                        {'label': 'Rest', 'success_probability': 1, 'valence_success': .1, 'valence_failure': 0,
                                         'success_text': 'I rested.', 'failure_text': 'I rested.'}]}
    return out


# 2. Assembly

def rooms_for(design):
    """{room id: room spec}, {person id: home room}, {site: {kind: room id}}."""
    rooms, homes, by_site = {}, {}, {}
    for place in design['places']:
        site = place['id']
        kinds = by_site.setdefault(site, {})
        if place['template'] == 'home':
            members = [p for p in design['people'] if p.get('home') == site]
            shared = place.get('shared', {})  # person id -> person id whose bedroom they share
            for person in members:
                if person['id'] in shared:
                    continue
                key = f'{site}_{person["id"]}_room'
                names = [person['name'], *[m['name'] for m in members if shared.get(m['id']) == person['id']]]
                rooms[key] = {'label': ' and '.join(names) + "'s bedroom", 'kind': 'bedroom', 'site': site, 'audible_to': []}
                kinds.setdefault('bedroom', key)
            for person in members:
                homes[person['id']] = f'{site}_{shared.get(person["id"], person["id"])}_room'
        for kind, label in TEMPLATES[place['template']]['rooms']:
            key = f'{site}_{kind}'
            rooms[key] = {'label': f'{place["label"]} {label}', 'kind': 'living_room' if kind == 'living_room' else kind,
                          'site': site, 'audible_to': []}
            kinds.setdefault(kind, key)
        if place['template'] == 'home':  # a home's rooms hear its living room and kitchen
            shared_rooms = [kinds.get('kitchen'), kinds.get('living_room')]
            for key, room in rooms.items():
                if room['site'] == site:
                    room['audible_to'] = [r for r in shared_rooms if r and r != key]
    return rooms, homes, by_site


def assemble(design, fills):
    """The scenario spec in the author vocabulary, from the design and the per-person fills."""
    rooms, homes, by_site = rooms_for(design)
    people_by_id = {p['id']: p for p in design['people']}
    years = float(design['begin']['years']) if design['begin']['mode'] == 'fast_forward' else 0.0
    people, situations = [], []
    caregivers = {}
    for rel in design['relationships']:
        if rel['type'] in ('parent of', 'grandparent of'):
            caregivers.setdefault(rel['b'], []).append(rel['a'])
    routines, groups, routes = {}, {}, []
    for person in design['people']:
        fill = fills[person['id']]
        goals = person.get('goals') or fill.get('goals') or []
        goal_items = [{'id': g.get('id') or slug(g['description'])[:24], 'description': g['description'],
                       'priority': float(g.get('priority', .6))} for g in goals[:3]]
        entry = {'id': person['id'], 'name': person['name'], 'age_years': float(person['age']) - years,
                 'facets': fill.get('facets', {}), 'facet_basis': person.get('description', '')[:300] or 'builder design',
                 'goals': goal_items, 'private_background': fill.get('background', [])[:3],
                 **({'caregivers': caregivers[person['id']]} if caregivers.get(person['id']) else {})}
        people.append(entry)
        hours = HOURS[person.get('hours', 'at home')]
        routines[person['id']] = {'available_hours': hours['awake'], 'response_minutes': [2, 10]}
        if 'kind' in hours:
            site = person['place']
            key = f'{site}_{hours["kind"]}'
            place_room = by_site[site].get('classroom') or next(iter(by_site[site].values()))
            group = groups.setdefault(key, {'label': f'{next(p["label"] for p in design["places"] if p["id"] == site)} {hours["kind"]}',
                                            'place': place_room, 'members': [],
                                            'meetings': {'first_day': 0, 'start_hour': hours['start'], 'duration_hours': hours['duration'],
                                                         'every_days': 1, 'topic': CLASS_TOPICS if hours['kind'] == 'class' else 'The working day'}})
            group['members'].append(person['id'])
        situation = fill.get('situation')
        if situation and goal_items:
            site = person['home'] if situation['room_kind'] in ('bedroom', 'kitchen', 'living_room') else person.get('place')
            room = homes[person['id']] if situation['room_kind'] == 'bedroom' else by_site.get(site, {}).get(situation['room_kind'])
            room = room or homes[person['id']]
            situations.append({'id': f'{person["id"]}_own', 'actor': person['id'], 'situation': situation['situation'],
                               'rate_per_year': 150, 'room': room, 'hours': situation['hours'], 'goal_id': goal_items[0]['id'],
                               'options': [{'id': f'o{i}', 'label': o['label'], 'success_probability': o['success_probability'],
                                            'valence_success': o['valence_success'], 'valence_failure': o['valence_failure'],
                                            'success_text': o['success_text'], 'failure_text': o['failure_text'],
                                            'progress_gain': .1 if i == 0 else 0.0, 'duration_hours': .5}
                                           for i, o in enumerate(situation['options'])]})
    sites = [p['id'] for p in design['places']]
    first_room = lambda site: next(k for k, r in rooms.items() if r['site'] == site)
    homes_sites = [p['id'] for p in design['places'] if p['template'] == 'home']
    for home in homes_sites:
        for site in sites:
            if site != home and next(p for p in design['places'] if p['id'] == site)['template'] != 'home':
                minutes = int(design['routes'].get(f'{home}|{site}', design['routes'].get(f'{site}|{home}', 20)))
                routes.append({'a': first_room(home), 'b': first_room(site), 'minutes': minutes})
    channels = {}
    for home in homes_sites:
        members = [p['id'] for p in design['people'] if p.get('home') == home]
        if len(members) >= 2:
            channels[f'{home}_chat'] = {'label': f'{next(p["label"] for p in design["places"] if p["id"] == home)} family chat',
                                        'members': members}
    for group in groups.values():  # a group of one is a solo shift: presence without a conversation
        group['members'] = sorted(set(group['members']))
    spec = {'title': design['title'], 'summary': design.get('summary') or design['title'], 'seed': int(design.get('seed', 7)),
            'duration_years': max(1e-3, float(design['duration_days']) / 365.25), 'people': people,
            'household': {'rooms': rooms, 'locations': {p['id']: homes[p['id']] for p in design['people']}, 'routines': routines,
                          'routes': routes, 'groups': groups, **({'channels': channels} if channels else {})},
            'situations': situations, 'interventions': [],
            'assumptions': ['Built with the control panel builder: places from templates, routines from daily-hours templates, '
                            'one model-filled situation per main character; numbers are design defaults.']}
    return spec


def relationship_values(kind):
    from .visit import RELATIONSHIPS, OTHER_RELATIONSHIP
    if FAMILY.get(kind):
        return FAMILY[kind]
    return RELATIONSHIPS.get(kind, (kind, *OTHER_RELATIONSHIP))


def apply_design(engine, design):
    """Sliders become facets (a Big Five slider sets its six facets unless fine-tuned), relationships both ways."""
    for person in design['people']:
        agent = engine.agent(person['id'])
        for domain, value in (person.get('sliders') or {}).items():
            if value is None:
                continue
            for k in range(1, 7):
                agent['facets'][f'{domain}{k}'] = float(value)
        for code, value in (person.get('facets') or {}).items():
            agent['facets'][code] = float(value)
        agent['initial_facets'] = dict(agent['facets'])
    for rel in design['relationships']:
        if rel['type'] in ('parent of', 'grandparent of'):  # the caregiver link is in the spec; give it family warmth
            for owner, other in ((rel['a'], rel['b']), (rel['b'], rel['a'])):
                record = engine.agent(owner)['relationships'].get(other, {})
                engine.relate(owner, other, record.get('role', 'family'), trust=.7, closeness=.6)
            continue
        role, trust, closeness = relationship_values(rel['type'])
        engine.relate(rel['a'], rel['b'], role, trust=trust, closeness=closeness)
        engine.relate(rel['b'], rel['a'], role, trust=trust, closeness=closeness)


def policy_for(design, policy):
    modules = design.get('modules', {})
    out = deepcopy(policy)
    if not modules.get('living', True):
        out.pop('living', None)
    for key in ('hormones', 'attention', 'sleep', 'skills'):
        if modules.get(key, True):
            out[key] = {}
    crowd = CROWD.get(design.get('crowd', 'off'))
    if crowd:
        out['society_layer'] = {'overrides': crowd}
    if design['begin']['mode'] == 'fill':
        out['background_expansion'] = {'default': {'mode': 'generative', 'id': 'personal-history-v1', 'min_age': 18,
                                                   'fields': ['education', 'residence', 'occupation', 'interests']}}
    return out


def next_build_folder(home):
    """compiled, then compiled-2, compiled-3 ...: a rebuild never overwrites a world that runs may point at."""
    folder, n = home / 'compiled', 1
    while folder.exists() and any(folder.iterdir()):
        n += 1
        folder = home / f'compiled-{n}'
    return folder


# 3. Build

def build(design, api=None, model=None, progress=lambda text, fraction=None: None, out=None):
    """Design -> compiled world in out (default: the next free work/designs/<slug>/compiled[-N]). Returns the output folder."""
    from .author import compile_scenario
    problems = check_design(design)
    if problems:
        raise ValueError(' '.join(problems))
    folder = Path(out) if out else next_build_folder(DESIGNS / slug(design['title']))
    if folder.exists() and any(folder.iterdir()):
        raise ValueError(f'{folder} already holds a build; change the title or remove it')
    steps = len(design['people']) + 3 + (1 if design['begin']['mode'] != 'none' else 0)
    done = 0
    fills = {}
    for person in design['people']:
        progress(f'imagining {person["name"]} ({person["role"]})', done / steps)
        fills[person['id']] = fill_person(person, design, api, model) if api else scripted_fill(person, design)
        done += 1
    progress('laying out the world', done / steps)
    spec = assemble(design, fills)
    engine, policy, report = compile_scenario(spec, dry_run=False, limits=BUILDER_LIMITS)
    apply_design(engine, design)
    policy = policy_for(design, policy)
    done += 1
    mode = design['begin']['mode']
    if mode == 'fill' and api:
        from .biography import expand
        adults = [p for p in design['people'] if float(p['age']) >= 18]
        for person in adults:
            progress(f'writing {person["name"]}\'s past', done / steps)
            expand(engine, person['id'], policy['background_expansion']['default'], api=api, model=model)
    elif mode == 'fast_forward' and float(design['begin']['years']) > 0:
        engine = fast_forward(engine, policy, float(design['begin']['years']), lambda t, f: progress(t, (done + f) / steps))
    done += 1
    policy['horizon_days'] = engine.day + float(design['duration_days'])  # counted from where the live run starts
    if mode == 'fast_forward':
        report['scripted_history'] = {'years': float(design['begin']['years']), 'policy': 'builder_fast_forward_scripted',
                                      'note': 'situation highlights (one in ten), development and sleep only; no conversations'}
    progress('saving', done / steps)
    folder.mkdir(parents=True, exist_ok=True)
    engine.save(folder / 'initial.json')
    (folder / 'policy.json').write_text(json.dumps(policy, indent=2) + '\n')
    (folder / 'scenario.json').write_text(json.dumps(spec, indent=2) + '\n')
    (folder / 'design.json').write_text(json.dumps(design, indent=2) + '\n')
    (folder / 'assumptions.json').write_text(json.dumps(report, indent=2, default=str) + '\n')
    progress('ready', 1.0)
    return folder


def fast_forward(engine, policy, years, progress):
    """Age the world by years cheaply: situations (one in ten), development and sleep only; scripted choices.
    Afterwards the run state is cleared so the live policy starts fresh at the target ages."""
    from .lifetime import Lifetime
    quick = {k: deepcopy(v) for k, v in policy.items() if k not in ('household', 'living', 'inner_thoughts', 'society_layer',
                                                                     'background_expansion', 'attention', 'hormones')}
    for opportunity in quick['opportunities']:
        opportunity.pop('room', None)
        opportunity.pop('hours', None)
        opportunity['rate_per_year'] = opportunity['rate_per_year'] * FF_RATE_SCALE
        for option in opportunity['options']:
            option.pop('contact', None)
            option.pop('contact_text', None)
            option.pop('conversation', None)
    controller = Lifetime(engine, quick, scripted=True)
    end = engine.day + years * 365.25
    while engine.day < end - 1e-9:
        controller.run(min(end, engine.day + 30))
        progress(f'fast-forward: year {(engine.day - (end - years * 365.25)) / 365.25:.1f} of {years:g}',
                 (engine.day - (end - years * 365.25)) / (years * 365.25))
    engine.state.pop('runtime', None)
    return engine
