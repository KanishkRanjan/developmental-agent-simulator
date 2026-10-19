"""Scenario authoring: plain-language setting -> reviewable spec -> validated world and policy.

draft:   the local model proposes scenario.json in a small supported vocabulary.
compile: deterministic code (no model) validates the spec, builds initial.json and
         policy.json, and dry-runs the policy with the scripted provider.

Every generated number is a labeled scenario assumption. People, starting
experiences and interventions are scenario declarations for a fictional world,
not verified facts about real people.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import time

from . import cognition
from . import household

TALK_CAP = 40  # the household validator's upper bound
from .engine import FACET_NAMES, Engine, number, validated_json

ID = re.compile(r'^[a-z][a-z0-9_-]{0,31}$')
# shortcut: the local server's context (RESUME.md) and a conservative 3 characters per token; read the server's
# /props instead if the model or context size changes.
CONTEXT_TOKENS = 8192
LIMITS = {'people': 8, 'facets': 10, 'background': 3, 'goals': 3, 'situations': 12, 'options': 4,
          'interventions': 12, 'rate_per_year': 365, 'dry_run_years': 3}
SITUATION_KEYS = {'id', 'actor', 'situation', 'rate_per_year', 'min_age', 'max_age', 'cues', 'goal_id', 'options', 'requires_facts',
                  'room', 'hours'}
OPTION_KEYS = {'id', 'label', 'success_probability', 'valence_success', 'valence_failure', 'success_text',
               'failure_text', 'contact', 'contact_text', 'importance', 'arousal', 'progress_gain', 'duration_hours',
               'effects_success', 'effects_failure', 'conversation', 'skill'}
PROTECTED_FACTS = {'birth_day', 'biological_parents', 'caregivers', 'name'}
COMPILER_DEFAULTS = [
    'Facets a person\'s spec leaves out are set to the 50th percentile (neutral), not sampled.',
    'Planning uses elapsed activity calendars with an 8-hour daily activity budget.',
    'Age-appropriate action constraints are on (infants act nonverbally).',
    'Private background lines are seeded as internal day-0 experiences with provenance scenario_authoring; they are authored, not simulated history.',
    'Interventions are controller-scheduled world events delivered only to their listed recipients.',
    'Live runs use semantic recall over the local Graphiti index (private full-text fallback, recorded, if the service is unavailable); the scripted dry run skips graph indexing.',
    f'Recurring situations are capped at {LIMITS["rate_per_year"]} occurrences per year.',
    'Face-to-face conversation replies take 0.25-2 minutes unless a routine sets in_person_response_minutes; response_minutes is the written-message delay.',
    'Live runs use situational personality: each person gets model-written if-then signatures from their tendencies (one about repeated situations), and each decision is preceded by a construal that can activate them; temporary shifts recover with a 1-day half-life.',
    'Live runs consolidate every 8 unconsolidated received episodes per person into tentative gists (lessons and patterns), so repeated experiences are summarized rather than only stored side by side.',
    'Every person gets a unique Instagram-style handle (name plus 4 digits, e.g. @priya0123) and is shown to others as "Priya (@priya0123)", so two people can share a name; a shared name alone stays ambiguous in speech and testimony.',
    'Memory (provisional engineering choices): each appraisal also writes a one-sentence gist; exact words are recalled for 1 day, '
    'then only the gist (fuzzy-trace theory). Recall is sampled with odds exp(2 x score) rather than always taking the top match. '
    'A strong mood makes new memories up to 1.5x more durable. Background recall happens 12 times a year at middle neuroticism, '
    'about 0.4x to 2.7x across the neuroticism range, leaning toward negative memories as neuroticism rises.',
]
VOCABULARY = {
    'title': 'short string', 'summary': 'one paragraph', 'seed': 'integer',
    'duration_years': 'run horizon in years, above 0 and at most 120 (two months is 0.17)',
    'people': f'1-{LIMITS["people"]} objects: id (lowercase slug), name, age_years (0-100), optional facets (up to '
              f'{LIMITS["facets"]} facet codes -> percentile 0-100, only where the setting implies a trait), facet_basis '
              f'(why), caregivers (ids of older people in the scenario), goals (up to {LIMITS["goals"]}: id, description, '
              f'priority 0-1), private_background (up to {LIMITS["background"]} first-person sentences the person already knows), '
              'facts (starting state flags {key: true|false|number|short text}, e.g. {"club_member": false})',
    'household': 'optional environment. rooms {room_id: {label, audible_to: [room_ids], kind (bedroom, kitchen, living_room, '
                 'bathroom, classroom, cafeteria, lab, office, ward, outdoors or other: it decides the furniture and everyday '
                 'happenings), site (the building: each family\'s home, school, a workplace)}} are places, including places away '
                 'from home (a school lab, a ward); give every person a home: locations {person: room_id} is where they sleep '
                 '(a bedroom, shared or not, or a living room for a fold-out bed), and family members share a home site; '
                 'optional creatures [{id, name, kind (cat or dog), rooms (on one home site), room}] for pets; routines {person: {available_hours: '
                 '[[start, end]] within one day in increasing order (awake 23:00-07:00 is [[0, 7], [23, 24]]), '
                 'response_minutes: [min, max] (written-message reply delay), optional in_person_response_minutes: [min, max] '
                 '(pause before a face-to-face reply; real replies follow within seconds, e.g. [0.05, 0.2], at least 0.05)}}; routes [{a, b, minutes}] (travel time between sites: one route between '
                 'any rooms of two sites joins them; rooms of one site are a short walk apart); '
                 'groups {group_id: {label, place, members, meetings: {first_day (whole day), start_hour (0-24, when members set off; they arrive after the route time), '
                 'duration_hours (counted from arrival), every_days, topic (one opening topic, or for frequent meetings a list of '
                 'several varied topics used in turn, e.g. a lesson, weekend plans, a test)}}} for '
                 'institutions and clubs (a school class, a work team, a club); channels {channel_id: {label, members}} for '
                 'written messaging such as a family chat; invitations [{id, day, group, invitee, inviter}] (acceptance sets '
                 'the fact member_<group_id> = true); conversations [{id, day (the fraction is the time of day: 28.8 is day 28 at 19:12; '
                 'at least two participants must be awake then), room or channel (participants come to the room), participants, topic}], or an interview: {id, day, room or channel, participants [interviewer, interviewee], '
                 'interviewer, questions (1-10), topic, max_turns = 2 x questions}',
    'situations': f'up to {LIMITS["situations"]} recurring situations: id, actor, situation (second person), rate_per_year '
                  f'(0-{LIMITS["rate_per_year"]}), optional min_age/max_age/cues/goal_id, optional room (a household room id: '
                  'it only happens while the actor is there) and hours ([start, end] within one day, e.g. lunch [11.5, 13.5]), options (2-{LIMITS["options"]}): '
                  'id, label, success_probability, valence_success, valence_failure (-1 to 1), success_text, failure_text '
                  '(first person), optional contact (person id) with contact_text (what the contact experiences), '
                  'importance, arousal, progress_gain (toward goal_id), duration_hours, optional skill {key (a short label of what the option '
                  'exercises, e.g. "robotics", "singing"), difficulty 0-1}: success then comes from the person\'s own skill and the attempt '
                  'is practice; effects_success/effects_failure '
                  '({facts: {person: {key: value}}, relationship_role: role the actor and contact now share}); optional '
                  'requires_facts {person: {key: value}}: the situation can only occur while these facts hold (use it for '
                  'situations that follow an intervention or an earlier choice, or membership: {"member_club": true}); '
                  'an option with a contact may add conversation {topic, questions?} to start a talk or interview with them',
    'interventions': f'up to {LIMITS["interventions"]} scheduled events: id, day (0 to duration), description, '
                     'observations {person: {text (first person), kind direct|testimony, source "direct" or a person id}}, '
                     'optional sets_facts {person: {key: value}} (state the event changes, e.g. {"priya": {"invited": true}})',
    'assumptions': 'list of strings: everything you assumed that the setting did not state',
}


def _fail(label, message):
    raise ValueError(f'{label}: {message}')


def _keys(value, label, required, optional=()):
    if not isinstance(value, dict):
        _fail(label, 'must be an object')
    missing, extra = set(required) - set(value), set(value) - set(required) - set(optional)
    if missing or extra:
        _fail(label, f'missing {sorted(missing)}' if missing else f'unsupported {sorted(extra)}')


def _id(value, label):
    if not isinstance(value, str) or not ID.match(value):
        _fail(label, 'ids are lowercase slugs (letters, digits, - or _), up to 32 characters')
    return value


def _text(value, label, limit=600):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        _fail(label, f'needs nonempty text up to {limit} characters')
    return value.strip()


def _list(value, label, limit):
    if not isinstance(value, list) or len(value) > limit:
        _fail(label, f'must be a list of at most {limit}')
    return value


def _facts(value, label, people, nested=True):
    """{person: {key: scalar}} (or {key: scalar} with nested=False); returns (person, key, value) triples."""
    if not isinstance(value, dict):
        _fail(label, 'must be an object')
    groups = value.items() if nested else [(None, value)]
    found = []
    for owner, facts in groups:
        where = f'{label}.{owner}' if nested else label
        if nested and owner not in people:
            _fail(where, 'must be a scenario person')
        if not isinstance(facts, dict) or not facts or len(facts) > 8:
            _fail(where, 'needs 1-8 facts')
        for key, item in facts.items():
            if not isinstance(key, str) or not ID.match(key) or key in PROTECTED_FACTS:
                _fail(f'{where}.{key}', 'fact keys are lowercase slugs and cannot rewrite identity or family')
            if not (isinstance(item, (bool, int, float)) or (isinstance(item, str) and 0 < len(item) <= 80)):
                _fail(f'{where}.{key}', 'value is true, false, a number or text up to 80 characters')
            if isinstance(item, float):
                number(item, -1e9, 1e9, f'{where}.{key}')
            found.append((owner, key, item))
    return found


def numbers(value, path=''):
    """Every numeric leaf with its JSON path: the generated numbers a reviewer must own."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [{'path': path, 'value': value}]
    items = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else []
    return [n for key, item in items for n in numbers(item, f'{path}.{key}' if path else str(key))]


def _check_rooms_and_roles(spec, ages):
    """Social plausibility the engine cannot see: whose room is whose, and whether each goal can be acted on."""
    home = spec.get('household', {})
    names = {p['id']: p['name'] for p in spec['people']}
    carers = {p['id']: set(p.get('caregivers', [])) for p in spec['people']}
    for room, cfg in home.get('rooms', {}).items():
        owners = [k for k, n in names.items() if re.match(re.escape(n) + r"'s\b", cfg['label'])]
        owner = owners[0] if len(owners) == 1 else None  # two people share the name: the label names neither
        for person, where in home.get('locations', {}).items():
            # An infant's caregiver may start in the infant's room; nobody else starts in someone's own room.
            if where == room and owner and person != owner and not (ages[owner] < 3 and person in carers[owner]):
                _fail(f'household.locations.{person}', f'{room} is labelled "{cfg["label"]}"; give {names[person]} '
                      'their own room (people return to their starting room after trips)')
    # Each person with goals needs something of their own to do. v5 run: only Priya had situations, so Rohan, who
    # only ever talked, invented "I ran simulations last night" and then built on his own invention every day.
    acting = {s['actor'] for s in spec.get('situations', [])}
    for person in spec['people']:
        if person.get('goals') and person['id'] not in acting:
            _fail(f'people.{person["id"]}.goals', f'{person["name"]} has goals but nothing of their own to do: add a situation '
                  'with them as actor (what they do between conversations: practice, work, a hobby, a chore), or drop the goals')


def _check_living_map(spec):
    """With room kinds and sites the world is lived in: everyone sleeps somewhere, and can get to their groups."""
    home = spec.get('household', {})
    rooms = home.get('rooms', {})
    if not any('kind' in r or 'site' in r for r in rooms.values()):
        return False
    for key, room in rooms.items():
        if 'kind' not in room or 'site' not in room:
            _fail(f'household.rooms.{key}', 'give every room a kind and a site (such as home or school), or none of them')
    names = {p['id']: p['name'] for p in spec['people']}
    sites = lambda key: rooms[key]['site']
    linked = {frozenset((sites(r['a']), sites(r['b']))) for r in home.get('routes', [])}
    for person in spec['people']:
        start = home.get('locations', {}).get(person['id'])
        if start is None or rooms[start]['kind'] not in ('bedroom', 'living_room'):
            _fail(f'household.locations.{person["id"]}', f'give {person["name"]} a home: their starting room is where they '
                  'sleep (a bedroom, or a living room for a fold-out bed), on a home site with a route to school or work')
    invited = {}
    for rule in home.get('invitations', []):
        invited.setdefault(rule['group'], set()).add(rule['invitee'])
    for key, group in home.get('groups', {}).items():
        place = sites(group['place'])
        for member in sorted(set(group.get('members', [])) | invited.get(key, set())):
            mine = sites(home['locations'][member])
            if mine != place and frozenset((mine, place)) not in linked:
                _fail('household.routes', f'{names[member]} cannot get from {mine} to {place} for {group["label"]}: add a route '
                      'between a room of each site')
    return True


def compile_scenario(spec, *, dry_run=True, limits=None):
    """Validate a spec and build (engine, policy, report). Raises ValueError naming the bad field.
    limits raises the draft limits for designs that did not come from one model reply (the control panel builder)."""
    global LIMITS
    if limits:
        saved, LIMITS = LIMITS, {**LIMITS, **limits}
        try:
            return compile_scenario(spec, dry_run=dry_run)
        finally:
            LIMITS = saved
    _keys(spec, 'scenario', {'title', 'summary', 'seed', 'duration_years', 'people'},
          {'household', 'situations', 'interventions', 'assumptions'})
    _text(spec['title'], 'title', 120); _text(spec['summary'], 'summary', 2000)
    if isinstance(spec['seed'], bool) or not isinstance(spec['seed'], int):
        _fail('seed', 'must be an integer')
    horizon = number(spec['duration_years'], 1e-3, 120, 'duration_years') * 365.25
    people = _list(spec['people'], 'people', LIMITS['people'])
    if not people:
        _fail('people', 'needs at least one person')
    e = Engine(seed=spec['seed'])
    e.state['config']['identity_handles'] = True  # unique @handles, so two people may share a name
    ages, produced = {}, set()
    places = spec.get('household', {}) if isinstance(spec.get('household'), dict) else {}
    groups = places.get('groups', {}) if isinstance(places.get('groups', {}), dict) else {}
    initial_members = {}
    for group_id, group in groups.items():
        if not isinstance(group_id, str) or not ID.match(group_id):
            _fail(f'household.groups.{group_id}', 'group ids are lowercase slugs')
        for member in group.get('members', []) if isinstance(group, dict) and isinstance(group.get('members', []), list) else []:
            initial_members.setdefault(member, {})['member_' + group_id] = True
    for rule in places.get('invitations', []) if isinstance(places.get('invitations', []), list) else []:
        if isinstance(rule, dict):
            produced.update({(rule.get('invitee'), f'member_{rule.get("group")}', True),
                             (rule.get('invitee'), f'member_{rule.get("group")}', False)})
    for i, person in enumerate(people):
        label = f'people[{i}]'
        _keys(person, label, {'id', 'name', 'age_years'},
              {'facets', 'facet_basis', 'caregivers', 'goals', 'private_background', 'facts'})
        key = _id(person['id'], label + '.id')
        if key in ages:
            _fail(label, f'duplicate person id {key}')
        if key in initial_members:
            person = {**person, 'facts': {**initial_members[key], **person.get('facts', {})}}
        ages[key] = number(person['age_years'], 0, 100, label + '.age_years')
        start = ({k: v for _, k, v in _facts(person['facts'], label + '.facts', (), nested=False)}
                 if 'facts' in person and person['facts'] != {} else {})
        produced.update((key, k, v) for k, v in start.items())
        e.entity(key, _text(person['name'], label + '.name', 80), {'birth_day': -ages[key] * 365.25, **start})
    for i, person in enumerate(people):
        label, key = f'people[{i}]', person['id']
        facets = person.get('facets', {})
        if not isinstance(facets, dict) or len(facets) > LIMITS['facets'] or set(facets) - set(FACET_NAMES):
            _fail(label + '.facets', f'up to {LIMITS["facets"]} codes from {sorted(FACET_NAMES)}')
        if facets:
            _text(person.get('facet_basis'), label + '.facet_basis')
        e.materialize(key, {**dict.fromkeys(FACET_NAMES, 50), **{k: number(v, 0, 100, f'{label}.facets.{k}')
                                                               for k, v in facets.items()}},
                      birth_day=-ages[key] * 365.25)
    for i, person in enumerate(people):
        label, key = f'people[{i}]', person['id']
        for adult in _list(person.get('caregivers', []), label + '.caregivers', 4):
            if adult not in ages or ages[adult] <= ages[key]:
                _fail(label + '.caregivers', f'{adult!r} must be an older person in the scenario')
            e.caregiver(key, adult)
        for j, goal in enumerate(_list(person.get('goals', []), label + '.goals', LIMITS['goals'])):
            _keys(goal, f'{label}.goals[{j}]', {'id', 'description', 'priority'})
            e.goal(key, _id(goal['id'], f'{label}.goals[{j}].id'), _text(goal['description'], f'{label}.goals[{j}]'),
                   priority=number(goal['priority'], 0, 1, f'{label}.goals[{j}].priority'))
        for j, line in enumerate(_list(person.get('private_background', []), label + '.private_background', LIMITS['background'])):
            e.schedule(f'scenario-background-{key}-{j}', 0, 'Scenario-authored starting experience; not simulated history.',
                       {key: {'text': _text(line, f'{label}.private_background[{j}]'), 'source': 'self', 'kind': 'internal',
                              'importance': .6, 'provenance': 'scenario_authoring'}})
    ivs = []
    for i, iv in enumerate(_list(spec.get('interventions', []), 'interventions', LIMITS['interventions'])):
        label = f'interventions[{i}]'
        _keys(iv, label, {'id', 'day', 'description', 'observations'}, {'sets_facts'})
        ivs.append(_id(iv['id'], label + '.id'))
        if not isinstance(iv['observations'], dict) or not iv['observations'] or set(iv['observations']) - set(ages):
            _fail(label + '.observations', 'map scenario people to what each perceives')
        observed = {}
        for owner, obs in iv['observations'].items():
            _keys(obs, f'{label}.observations.{owner}', {'text'}, {'kind', 'source', 'valence', 'arousal', 'importance'})
            kind, source = obs.get('kind', 'direct'), obs.get('source', 'direct')
            if kind not in ('direct', 'testimony') or source not in {'direct', *ages} or (
                    kind == 'testimony' and source in ('direct', owner)):
                _fail(f'{label}.observations.{owner}', 'kind is direct|testimony; source is "direct" or a person id; '
                                                       'testimony needs another person as its source')
            observed[owner] = {**obs, 'kind': obs.get('kind', 'direct'), 'source': obs.get('source', 'direct'),
                               'text': _text(obs['text'], f'{label}.observations.{owner}.text'), 'provenance': 'scenario_authoring'}
        sets = _facts(iv.get('sets_facts', {}), label + '.sets_facts', ages) if 'sets_facts' in iv else []
        produced.update(sets)
        changes = {}
        for owner, k, v in sets:
            changes.setdefault(owner, {})[k] = v
        e.schedule('scenario-' + iv['id'], number(iv['day'], 0, horizon, label + '.day'),
                   _text(iv['description'], label + '.description'), observed, facts=changes)
    if len(set(ivs)) != len(ivs):
        _fail('interventions', 'duplicate intervention id')
    opportunities, needed = [], []
    for i, situation in enumerate(_list(spec.get('situations', []), 'situations', LIMITS['situations'])):
        label = f'situations[{i}]'
        _keys(situation, label, {'id', 'actor', 'situation', 'rate_per_year', 'options'}, SITUATION_KEYS)
        _id(situation['id'], label + '.id'); _text(situation['situation'], label + '.situation')
        if situation['actor'] not in ages:
            _fail(label + '.actor', 'must be a scenario person')
        number(situation['rate_per_year'], 0, LIMITS['rate_per_year'], label + '.rate_per_year')
        if 'room' in situation and situation['room'] not in spec.get('household', {}).get('rooms', {}):
            _fail(label + '.room', 'must be a household room id')
        if 'hours' in situation:
            window = situation['hours']
            if not isinstance(window, list) or len(window) != 2:
                _fail(label + '.hours', 'needs [start, end] within one day')
            number(window[0], 0, 24, label + '.hours start'); number(window[1], window[0] + 1e-6, 24, label + '.hours end')
        options = situation['options']
        if not isinstance(options, list) or not 2 <= len(options) <= LIMITS['options']:
            _fail(label + '.options', f'needs 2-{LIMITS["options"]} options')
        for j, option in enumerate(options):
            olabel = f'{label}.options[{j}]'
            _keys(option, olabel, {'id', 'label', 'success_probability', 'valence_success', 'valence_failure',
                                   'success_text', 'failure_text'}, OPTION_KEYS)
            _id(option['id'], olabel + '.id')
            if 'contact' in option and (option['contact'] not in ages or option['contact'] == situation['actor']):
                _fail(olabel + '.contact', 'must be another scenario person')
            if ('contact' in option) != ('contact_text' in option):
                _fail(olabel, 'contact and contact_text go together')
            for field, low, high in [('success_probability', 0, 1), ('valence_success', -1, 1), ('valence_failure', -1, 1),
                                     ('importance', 0, 1), ('arousal', 0, 1), ('progress_gain', 0, 1), ('duration_hours', 0, 24)]:
                if field in option:
                    number(option[field], low, high, f'{olabel}.{field}')
        compiled = deepcopy(situation)
        required = compiled.pop('requires_facts', None)
        if required is not None:
            needed += [(f'{label}.requires_facts', fact) for fact in _facts(required, label + '.requires_facts', ages)]
        for j, option in enumerate(compiled['options']):
            if required is not None:
                option['requires'] = {'facts': deepcopy(required)}
            for branch in ('effects_success', 'effects_failure'):
                if branch not in option:
                    continue
                where = f'{label}.options[{j}].{branch}'
                _keys(option[branch], where, (), {'facts', 'relationship_role'})
                if not option[branch]:
                    _fail(where, 'needs facts or relationship_role')
                effects = {}
                if 'facts' in option[branch]:
                    sets = _facts(option[branch]['facts'], where + '.facts', ages)
                    produced.update(sets)
                    effects['facts'] = deepcopy(option[branch]['facts'])
                if 'relationship_role' in option[branch]:
                    if 'contact' not in option:
                        _fail(where + '.relationship_role', 'needs a contact, who shares the new role with the actor')
                    effects['relationships'] = [{'a': situation['actor'], 'b': option['contact'],
                                                 'role': _text(option[branch]['relationship_role'], where + '.relationship_role', 60)}]
                option[branch] = effects
        opportunities.append(compiled)
    for where, fact in needed:
        if fact not in produced:
            settable = sorted(f'{k}={v!r}' for owner, k, v in produced if owner == fact[0])
            _fail(where, f'{fact[0]}.{fact[1]} = {fact[2]!r} is never set by people facts, interventions, option effects or '
                         f'invitations, so this situation could never occur. Facts that can be set for {fact[0]}: '
                         f'{", ".join(settable) or "none"}')
    policy = {'description': f'{spec["title"]}: authored scenario. All rates, probabilities, valences, ages and facet '
                             'percentiles are scenario assumptions, not measured values.',
              'sampling': 'event_driven', 'opportunities': opportunities,
              'planning': {'calendar_mode': 'elapsed', 'hours_per_day': 8},
              'expression': {'age_appropriate_actions': True},
              'cognition': {'semantic_recall': True, 'indexed_retrieval': True, 'graphiti_retrieval': True,
                            **cognition.MEMORY_DEFAULTS},
              'consolidation_batch_size': 8, 'inner_thoughts': {'mean_minutes': 3}, 'relationship_learning': {}, 'situational_personality': {'recovery_half_life_days': 1},
              'horizon_days': horizon}
    from .lifetime import Lifetime
    try:
        if 'household' in spec:
            household.validate(e, spec['household'])
            _check_rooms_and_roles(spec, ages)
            if _check_living_map(spec):
                policy['living'] = {}  # needs, furniture, free-time choices and the surroundings (devsim/living.py)
            policy['household'] = deepcopy(spec['household'])
            for routine in policy['household'].get('routines', {}).values():
                # Face-to-face replies follow within seconds; the line's own length is added by the engine. A drafted
                # 1-5 minutes would leave a silence before every line once the clock runs in real time.
                low, high = routine.get('in_person_response_minutes', [.05, .2])
                routine['in_person_response_minutes'] = [min(low, .25), max(min(high, .5), min(low, .25))]
        # Talks end on their own after a silent round, so max_turns is only a safety cap; a drafted 4 cut every
        # school-day talk to one line each in the v5 run. Interviews keep their two turns per question.
        talks = [*policy.get('household', {}).get('conversations', []),
                 *(g['meetings'] for g in policy.get('household', {}).get('groups', {}).values() if 'meetings' in g),
                 *(o['conversation'] for opp in opportunities for o in opp.get('options', []) if 'conversation' in o)]
        for talk in talks:
            if 'questions' not in talk:
                talk['max_turns'] = TALK_CAP
        else:
            _check_rooms_and_roles(spec, ages)
        e.advance(0)
        probe = deepcopy(e)
        scripted = deepcopy(policy)
        scripted['cognition']['graphiti_retrieval'] = False  # as simulate --scripted: no unused graph view caches
        scripted['cognition']['semantic_matching'] = False  # scripted choices ignore memories; no service needed
        # Scripted free-time choices every 20 minutes for every person would make the dry run very long; the living
        # world is still configured and its surroundings run (its behaviour has its own check suite).
        scripted.pop('inner_thoughts', None)
        controller = Lifetime(probe, scripted, scripted=True)  # full policy validation against this world
    except ValueError as exc:
        _fail('household' if 'household' in spec and 'household' not in policy else 'policy', str(exc))
    report = {'title': spec['title'], 'duration_days': horizon,
              'model_stated_assumptions': list(spec.get('assumptions', [])), 'compiler_defaults': COMPILER_DEFAULTS,
              'generated_numbers': [n for n in numbers(spec) if n['path'] != 'seed']}
    if dry_run:
        days = min(horizon, LIMITS['dry_run_years'] * 365.25)
        controller.run(days)
        report['scripted_dry_run'] = {'days': days, 'provider': 'scripted_engineering_fixture',
            'resolved_actions': sum(a['status'] == 'resolved' for a in probe.state['actions']),
            'applied_events': sum(ev['status'] == 'applied' for ev in probe.state['events']),
            'pending_events': len(probe.state['pending']),
            'conversations': {k: s['status'] for k, s in probe.state['runtime'].get('conversations', {}).items()},
            'scope': 'checks that the policy runs; scripted choices skip model cognition'}
    return e, policy, report


def draft(setting, *, api, model):
    """Ask the local model for a spec; it must compile before it is accepted."""
    context = {'task': 'author_scenario', 'setting': _text(setting, 'setting', 6000), 'vocabulary': VOCABULARY,
               'facet_codes': FACET_NAMES, 'limits': LIMITS}
    system = ('Turn the researcher\'s setting into a scenario spec for a fictional developmental social simulation. '
              'Use only the supplied vocabulary; return a single JSON object with its top-level keys. Every person with goals needs at least one situation of their own, so they have a life to '
              'talk about. Otherwise keep it small: only '
              'people, situations and events the setting needs. Do not add biography, diagnoses or events the setting does '
              'not imply; list every guess in assumptions. Numbers are provisional scenario choices, not measurements. '
              'Facet percentiles are optional and only for traits the setting describes. Situation texts address the actor '
              'as "you"; success and failure texts are first person. Infants (under 2) need nonverbal options. '
              'Ids are lowercase slugs. Day 0 is the start; household hours are 0-24. Give each person a plausible room '
              'of their own to start in (people return there after trips). Model daily routines such as school days or work '
              'shifts as groups with meetings. Anyone a situation or group expects people to interact with (classmates, '
              'colleagues) must be a person in people. Written messages, such as a family chat, use a channel, not a '
              'contact option. Give a situation a room and hours when it happens at a particular place or time (lunch at '
              'school). Every person with goals needs a way to act on them, and a goal_id must fit its situation. '
              'Be concise: at most 4 situations '
              'and 4 interventions, one or two sentences per text, compact JSON without indentation.')

    def validate(result):
        try:
            compile_scenario(result, dry_run=False)
        except ValueError:
            raise
        except Exception as exc:  # malformed shapes surface as type errors deep in validation
            raise ValueError(f'{type(exc).__name__}: {exc}') from exc
    # A repair returns the previous draft with the error, so the model fixes that field instead of regenerating
    # everything (which tends to fix one field and break another).
    from . import engine as engine_module
    last = previous = None
    for attempt in range(3):
        supplied = context if attempt == 0 else {**context, 'output_repair': {
            'attempt': attempt, 'validation_error': str(last)[:300], 'previous_output': previous,
            'instruction': 'Return previous_output with only the problem in validation_error fixed.'}}
        prompt_tokens = (len(system) + len(json.dumps(supplied))) // 3
        budget = min(5000, CONTEXT_TOKENS - prompt_tokens - 200)  # prompt and answer share the context window
        if budget < 1500:
            raise ValueError('The draft and its repair no longer fit the model context; shorten the setting') from last
        result = engine_module.request_json(system, supplied, api, model, budget)
        try:
            validate(result)
            return result
        except (ValueError, TypeError, KeyError) as exc:
            last, previous = exc, result
    raise ValueError('Local model output remained invalid after two repair attempts') from last


REVIEW_KINDS = ('contradiction', 'unsupported', 'timing', 'other')


def field(spec, path):
    """The value at a dotted path such as situations.1.options.0.success_text (brackets also accepted)."""
    node = spec
    for part in path.replace('[', '.').replace(']', '').strip('.').split('.'):
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise ValueError(f'{path!r} is not a field of the scenario')
    return node


def review(setting, spec, *, api, model):
    """Advisory model review of a compiling spec against its setting: issues tied to real fields. Changes nothing."""
    compile_scenario(spec, dry_run=False)
    context = {'task': 'review_scenario', 'setting': _text(setting, 'setting', 6000), 'vocabulary': VOCABULARY, 'scenario': spec}
    system = ('Compare this scenario spec with the researcher\'s setting and list problems a careful reviewer should fix before '
              'running it: contradictions with the setting, details the setting does not support, and timing problems, such as '
              'an outcome or situation text that presupposes an event that happens later or may not happen at all. Also check '
              'who starts in whose room, whether written chats are channels rather than in-person contacts, whether situations '
              'happen at the right place and hours, people that situations or groups mention who are not in the scenario, '
              'people whose goals nothing lets them pursue, and goals tied to situations that do not concern them. Give each '
              'issue the dotted path of the exact field (for example situations.1.options.0.success_text or '
              'household.routines.arun.available_hours), a kind (contradiction, unsupported, timing or other) and a one-sentence '
              'problem of at most 400 characters. The vocabulary explains what each field means (rooms are any places, including '
              'places away from home). List only real problems: leave out anything you conclude is fine, and skip style '
              'preferences. Return JSON: issues (list, may be empty).')

    def validate(result):
        issues = result.get('issues')
        if not isinstance(issues, list) or len(issues) > 20:
            raise ValueError('issues must be a list of at most 20')
        for n, issue in enumerate(issues):
            if isinstance(issue, dict) and 'path' not in issue and 'field' in issue:
                issue['path'] = issue.pop('field')  # a common synonym; the path is still checked below
            if not isinstance(issue, dict) or issue.get('kind') not in REVIEW_KINDS:
                raise ValueError(f'issues[{n}].kind must be one of {REVIEW_KINDS}')
            if not isinstance(issue.get('problem'), str) or not issue['problem'].strip() or len(issue['problem']) > 400:
                raise ValueError(f'issues[{n}].problem needs one sentence of at most 400 characters')
            if not isinstance(issue.get('path'), str):
                raise ValueError(f'issues[{n}].path needs a dotted field path')
            field(spec, issue['path'])
    result = validated_json(system, context, validate, api, model, 3000)  # room for reasoning before the JSON
    return [{'path': i['path'], 'kind': i['kind'], 'problem': i['problem'], 'value': field(spec, i['path'])}
            for i in result['issues']]


def main():
    from . import engine as engine_module
    from .run_live import recorder, select_model
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='mode', required=True)
    d = sub.add_parser('draft', help='Local model drafts scenario.json from a setting')
    d.add_argument('setting', nargs='?', help='Setting text (or use --setting-file)')
    d.add_argument('--setting-file', type=Path)
    d.add_argument('--api', default='http://127.0.0.1:18081')
    c = sub.add_parser('compile', help='Validate a reviewed scenario.json into initial.json and policy.json')
    c.add_argument('scenario', type=Path)
    r = sub.add_parser('review', help='Local model checks an edited scenario.json against its setting')
    r.add_argument('scenario', type=Path)
    r.add_argument('--setting-file', type=Path, required=True)
    r.add_argument('--api', default='http://127.0.0.1:18081')
    for p in (d, c, r):
        p.add_argument('--out', type=Path, required=True, help='Fresh output directory')
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a fresh output directory')
    if args.mode == 'draft' and bool(args.setting) == bool(args.setting_file):
        parser.error('Give the setting as text or --setting-file, not both')
    args.out.mkdir(parents=True, exist_ok=True)
    sources = sorted(Path(__file__).parent.glob('*.py'))
    (args.out / 'source-hashes.json').write_text(json.dumps(
        {str(p.resolve()): sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2) + '\n')
    started = time.monotonic()
    if args.mode in ('draft', 'review'):
        setting = args.setting_file.read_text() if args.setting_file else args.setting
        model, models = select_model(args.api)
        (args.out / 'server-model.json').write_text(json.dumps(models, indent=2) + '\n')
        (args.out / 'setting.txt').write_text(setting.strip() + '\n')
        counts, original = {}, engine_module.request_json
        engine_module.request_json = recorder(original, args.out / 'requests.jsonl', counts)
        try:
            spec = draft(setting, api=args.api, model=model) if args.mode == 'draft' else json.loads(args.scenario.read_text())
            issues = review(setting, spec, api=args.api, model=model)
        finally:
            engine_module.request_json = original
        (args.out / 'scenario.json').write_text(json.dumps(spec, indent=2) + '\n')
        (args.out / 'review.json').write_text(json.dumps({'scope': 'advisory model review; check each issue yourself',
                                                          'issues': issues}, indent=2) + '\n')
        summary = {'mode': args.mode, 'model': model, 'requests': counts, 'review_issues': len(issues),
                   'seconds': round(time.monotonic() - started, 3),
                   'next': f'Read review.json, edit {args.out / "scenario.json"}, then: python3 -m devsim.author compile '
                           f'{args.out / "scenario.json"} --out NEW_DIRECTORY'}
    else:
        spec = json.loads(args.scenario.read_text())
        engine, policy, report = compile_scenario(spec)
        engine.save(args.out / 'initial.json')
        (args.out / 'policy.json').write_text(json.dumps(policy, indent=2) + '\n')
        (args.out / 'scenario.json').write_text(json.dumps(spec, indent=2) + '\n')
        (args.out / 'assumptions.json').write_text(json.dumps(report, indent=2) + '\n')
        until = round(report['duration_days'], 3)
        summary = {'mode': 'compile', 'source': str(args.scenario), 'dry_run': report['scripted_dry_run'],
                   'seconds': round(time.monotonic() - started, 3),
                   'run_live': f'python3 -m devsim.run_live --world {args.out / "initial.json"} --policy '
                               f'{args.out / "policy.json"} --until-day {until} --out {args.out / "run"} --api API',
                   'run_scripted': f'python3 -m devsim.lifetime {args.out / "initial.json"} --policy {args.out / "policy.json"} '
                                   f'--until-day {until} --save {args.out / "scripted-world.json"} --scripted'}
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
