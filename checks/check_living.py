"""Living world checks: needs, sites, activities, whereabouts, free-time choices, happenings, weather and creatures."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devsim import household, living, surroundings
from devsim.engine import Engine, FACET_NAMES
from devsim.lifetime import Lifetime

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
PEOPLE = {'mum': 40, 'kid': 15, 'gran': 70, 'pal': 15}
H = 1 / 24


def world(quiet=True, thoughts=False, creature=False, routines=None):
    e = Engine(seed=7)
    for p, age in PEOPLE.items():
        e.entity(p, p.title(), {'birth_day': -age * 365.25})
        e.materialize(p, dict.fromkeys(FACET_NAMES, 50), birth_day=-age * 365.25)
    e.advance(0)
    rooms = {'kid_room': {'label': "the kid's bedroom", 'kind': 'bedroom', 'site': 'home', 'audible_to': ['hall']},
             'mum_room': {'label': "mum's bedroom", 'kind': 'bedroom', 'site': 'home'},
             'hall': {'label': 'the living room', 'kind': 'living_room', 'site': 'home', 'audible_to': ['kitchen']},
             'kitchen': {'label': 'the kitchen', 'kind': 'kitchen', 'site': 'home', 'audible_to': ['hall']},
             'bath': {'label': 'the bathroom', 'kind': 'bathroom', 'site': 'home'},
             'canteen': {'label': 'the school canteen', 'kind': 'cafeteria', 'site': 'school'},
             'class': {'label': 'the classroom', 'kind': 'classroom', 'site': 'school'},
             'work': {'label': 'the office', 'kind': 'office', 'site': 'work'}}
    policy = {'sampling': 'event_driven', 'opportunities': [], 'planning': {'calendar_mode': 'elapsed', 'hours_per_day': 10},
              'living': {'happenings': {}} if quiet else {},
              'household': {'rooms': rooms, 'locations': {'mum': 'mum_room', 'kid': 'kid_room', 'gran': 'hall', 'pal': 'canteen'},
                            'routines': {p: {'available_hours': (routines or {}).get(p, [[7, 22]]), 'response_minutes': [1, 2],
                                             'in_person_response_minutes': [.05, .2]} for p in PEOPLE},
                            'routes': [{'a': 'kid_room', 'b': 'canteen', 'minutes': 20}]}}
    if thoughts:
        policy['inner_thoughts'] = {'mean_minutes': 20}
    if creature:
        policy['household']['creatures'] = [{'id': 'biscuit', 'name': 'Biscuit', 'kind': 'cat', 'rooms': ['kid_room', 'hall', 'kitchen'], 'room': 'hall'}]
    return e, policy


def events(e, prefix):
    return [ev for ev in e.state['events'] if ev['id'].startswith(prefix)]


def reject(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError('Invalid living setting accepted')


def main():
    checks = []

    # Needs fall lazily, by waking window, and reading them changes nothing.
    e, policy = world()
    c = Lifetime(e, policy, scripted=True)
    before = deepcopy(e.state)
    noon = living.needs(e, 'kid', .5)
    assert e.state == before
    assert abs(noon['hunger'] - (.7 - .02 * 7 - .06 * 5)) < 1e-9 and abs(noon['energy'] - (1 - .05 * 5)) < 1e-9
    assert abs(noon['social'] - (.6 - .04 * 5)) < 1e-9
    checks.append('needs fall per waking or sleeping hour from the last update (energy refills asleep, capped at 1); reading them is pure')

    # Sites: rooms of one site are a walk away, other sites need a route (a route between any of their rooms counts).
    assert living.minutes_between(e, 'hall', 'kitchen') == 0 and living.minutes_between(e, 'kid_room', 'canteen') == 20
    assert living.minutes_between(e, 'hall', 'canteen') == 20 and living.minutes_between(e, 'hall', 'work') is None
    assert household.travel(c, 'gran', 'work', 'no-route') is None and household.location(e, 'gran') == 'hall'
    living.state(e)['weather'] = {'state': 'rain', 'since': 0}
    assert abs(household.route_minutes(e, 'hall', 'canteen') - 24) < 1e-9
    living.state(e)['weather'] = {'state': 'clear', 'since': 0}
    checks.append('rooms in a site are within walking reach; another site needs a route (no teleporting); rain lengthens routes')

    # Privacy: another household's home is off limits; public places are open.
    assert not living.allowed(e, 'pal', 'kitchen') and living.allowed(e, 'kid', 'canteen') and living.allowed(e, 'gran', 'kitchen')
    pal = {o['id'] for o in living.menu(e, 'pal')}
    assert pal and not any('kitchen' in o or 'hall' in o or o.startswith('talk:') for o in pal), pal
    checks.append("a classmate cannot use or walk into another family's home; school and other public places are open")

    # Scripted choice: the most relieving reachable thing, like Sims autonomy.
    c.run(8 * H)
    living.change_needs(e, 'gran', {'hunger': -1})
    assert living.menu(e, 'gran')[0]['id'] == 'do:kitchen/stove/cook'
    checks.append('a hungry person\'s best-ranked option is to cook (need relief minus travel)')

    # An activity takes its time, is seen by people in the room, and raises needs only if completed there.
    household.move(c, 'mum', 'kitchen', 'mum-in')
    hunger = living.needs(e, 'gran')['hunger']
    living.act(c, 'gran', 'do:kitchen/stove/cook', None, 't1')
    c.run(8 * H + 1 / 1440)
    assert living.state(e)['doing']['gran']['phase'] == 'busy' and household.location(e, 'gran') == 'kitchen'
    started = events(e, '@living:gran')[-1]
    assert started['observations']['gran']['text'] == 'I started cooking.' and started['observations']['mum']['text'] == 'Gran started cooking.'
    c.run(8.8 * H)
    assert 'gran' not in living.state(e)['doing'] and events(e, '@living:gran')[-1]['observations']['gran']['text'] == 'I finished cooking.'
    assert abs(living.needs(e, 'gran')['hunger'] - (max(0, hunger - .06 * .75) + .7 - .06 * .05)) < 1e-6  # 45 min cooking, then 3 min
    living.act(c, 'mum', 'do:hall/tv/watch', None, 't2')
    c.run(8.81 * H)
    household.travel(c, 'mum', 'mum_room', 'away')
    c.run(10 * H)
    assert 'mum' not in living.state(e)['doing'] and not any('finished watching' in o['text'] for ev in events(e, '@living:mum') for o in ev['observations'].values())
    checks.append('an activity is seen by people in the room, takes its minutes, and only completes (raising needs) if the person stays')

    # Whereabouts come from perception only.
    assert 'gran' not in living.whereabouts(e, 'kid')
    household.move(c, 'gran', 'kid_room', 'g1')
    assert living.whereabouts(e, 'kid')['gran'][0] == 'kid_room'
    household.move(c, 'gran', 'hall', 'g2')
    assert 'gran' not in living.whereabouts(e, 'kid') and e.agent('kid')['last_seen']['gran'][0] is None
    checks.append('people know where others are only from what they saw or heard; someone leaving makes their whereabouts unknown')

    # Going to talk: walk there and start a conversation, or find them gone or asleep.
    living.saw(e, 'kid', 'gran', 'hall')
    living.act(c, 'kid', 'talk:gran', 'the cat', 'v1')
    c.run(10 * H + 1 / 1440)
    talk = e.state['runtime']['conversations']['visit-v1']
    assert talk['spec']['participants'] == ['kid', 'gran'] and talk['spec']['topic'] == 'the cat' and talk['spec']['room'] == 'hall'
    c.run(12 * H)
    household.move(c, 'kid', 'kid_room', 'k1')  # out of sight: what is seen beats an old belief
    living.saw(e, 'kid', 'gran', 'kitchen')
    living.act(c, 'kid', 'talk:gran', None, 'v2')
    c.run(12 * H + 1 / 1440)
    assert 'visit-v2' not in e.state['runtime']['conversations']
    assert events(e, '@living:kid:visit')[-1]['observations']['kid']['text'] == 'I went to find Gran, but Gran was not there.'
    e2, p2 = world(routines={'gran': [[7, 20]]})
    c2 = Lifetime(e2, p2, scripted=True)
    c2.run(21 * H)
    living.saw(e2, 'kid', 'gran', 'hall')
    living.act(c2, 'kid', 'talk:gran', None, 'v3')
    c2.run(21 * H + 1 / 1440)
    assert events(e2, '@living:kid:visit')[-1]['observations']['kid']['text'] == 'I went to find Gran, but Gran was asleep.'
    checks.append('going to talk walks to the person and opens a conversation there; someone gone or asleep is noticed instead')

    # Bedtime: near the end of the day people at home go back to their own room.
    household.move(c, 'gran', 'kitchen', 'g3')
    c.run(22 * H)
    assert household.location(e, 'gran') == 'hall' and household.location(e, 'mum') == 'mum_room'
    checks.append('near the end of the waking day a person at home walks back to their own room')

    # Happenings reach only people in the room or within earshot.
    e, policy = world(quiet=False)
    c = Lifetime(e, policy, scripted=True)
    c.run(10 * H)
    household.move(c, 'mum', 'kitchen', 'm')
    surroundings.happen(c, 'hall/delivery')
    knock = events(e, '@happening:hall/delivery')[-1]
    assert set(knock['observations']) == {'gran', 'mum'}, knock['observations']
    checks.append('a happening reaches only people in the room and, for sounds, in rooms within earshot')

    # A power cut puts every powered object on the site out of order, then comes back.
    surroundings.happen(c, 'hall/power_cut')
    ids = {o['id'] for o in living.menu(e, 'mum')}
    down = living.state(e)['out_of_order']
    assert not any(i.startswith(('do:kitchen/stove', 'do:hall/tv')) for i in ids)
    assert {'kitchen/stove', 'kitchen/fridge', 'hall/tv', 'kid_room/desk'} <= set(down) and 'hall/sofa' not in down
    assert not any(k.startswith(('canteen', 'class')) for k in down)
    c.run(12.1 * H)
    assert all(until <= e.day for until in down.values()) and living.usable(e, 'kitchen', 'stove', living.objects(e, 'kitchen')['stove'])
    assert any(o['text'] == 'The power came back on.' for ev in events(e, '@happening:hall/power_cut') for o in ev['observations'].values())
    checks.append('a power cut takes out the powered objects of the whole site (not the school) and they work again two hours later')

    # A fire drill interrupts a conversation at school and frees its reserved turn.
    household.travel(c, 'kid', 'canteen', 'to-school')
    c.run(13 * H)
    household.start_conversation(c, 'kid', 'pal', {'topic': 'Lunch.', 'max_turns': 40}, 'chat')
    c.run(13 * H + 2 / 1440)
    surroundings.happen(c, 'class/fire_drill')
    chat = e.state['runtime']['conversations']['chat']
    assert chat['status'] == 'closed' and chat['closed_reason'] == 'interrupted: fire_drill'
    assert not any(b['status'] == 'reserved' and b['activity'].startswith('@conversation:chat') for p in ('kid', 'pal') for b in e.agent(p)['calendar'])
    checks.append('a fire drill interrupts conversations on the school site and releases their reserved turns')

    # The cat has its own routine; people present notice it and can play with it.
    e, policy = world(creature=True)
    c = Lifetime(e, policy, scripted=True)
    c.run(1)
    seen = events(e, '@creature:biscuit')
    assert len(seen) >= 5 and all(e.agent(p)['last_seen'].get('biscuit') for ev in seen for p in ev['observations'])
    assert living.state(e)['creatures']['biscuit']['room'] in ('kid_room', 'hall', 'kitchen')
    e.state['household']['locations']['gran'] = living.state(e)['creatures']['biscuit']['room']
    assert any(o['id'] == 'play:biscuit' for o in living.menu(e, 'gran'))
    checks.append(f'the cat wanders its rooms on its own ({len(seen)} sightings in a day); people there notice it and can play with it')

    # A whole scripted living day: autonomy, surroundings, deterministic, and resumable mid-activity.
    def day(stop=None, checkpoint=None):
        e, policy = world(quiet=False, thoughts=True, creature=True)
        c = Lifetime(e, policy, scripted=True)
        c.run(stop or 1.97, checkpoint)  # past the 21:50 bedtime walk home
        return e, policy
    a, _ = day()
    b, _ = day()
    assert a.state == b.state
    kinds = {ev['id'].split(':')[0] for ev in a.state['events']}
    assert {'@living', '@happening', '@creature', '@weather', '@travel', '@conversation'} <= kinds, kinds
    assert all(household.location(a, p) == living.home_room(a, p) for p in PEOPLE)
    with TemporaryDirectory() as d:
        path = Path(d) / 'world.json'
        mid, policy = day(1.4, path)
        resumed = Engine.load(path)
        Lifetime(resumed, policy, scripted=True).run(1.97)
        assert resumed.state == a.state
    checks.append('a scripted living day (choices, activities, visits, happenings, weather, the cat) is deterministic, '
                  'ends with everyone in their own room, and resumes from a mid-day checkpoint to the same world')

    # Live choice with a stubbed model: the worried grandmother goes to the child's room and starts a talk.
    e, policy = world(thoughts=True)
    def stub(system, context, api, model, max_tokens=600):
        owner = context['identity']['id']
        if context.get('task') == 'inner_thought':
            ids = [o['id'] for o in context['what_you_could_do_now']]
            assert 'how_your_body_feels' in context and 'where_people_are_as_far_as_you_know' in context
            go = owner == 'gran' and 'talk:kid' in ids
            return {'thought': 'She has gone so quiet. I should check on her.' if go else 'Nothing much on my mind.',
                    'valence': -.3 if go else 0, 'arousal': .4, 'importance': .6, 'choice': 'talk:kid' if go else 'stay',
                    'about': 'whether she is all right' if go else None}
        if 'new_observation' in context:
            return {'meaning': 'Noted.', 'valence': 0, 'arousal': .1, 'importance': .3, 'confidence': .8}
        talked = sum(a['owner'] == owner and a['id'].startswith('@conversation:') for a in e.state['actions'])
        return {'action_id': 'speak' if talked < 2 else 'listen', 'action': 'Talk.', 'speech': 'Are you all right?' if talked < 2 else '',
                'goal_id': None, 'plan': [], 'memory_ids': []}
    c = Lifetime(e, policy)
    with patch('devsim.engine.request_json', side_effect=stub):
        c.run(7 * H)
        living.saw(e, 'gran', 'kid', 'kid_room')  # she heard the child go to her room this morning
        c.run(9 * H)
    visits = [s for k, s in e.state['runtime']['conversations'].items() if k.startswith('visit-auto-gran')]
    assert visits and visits[0]['spec']['room'] == 'kid_room' and visits[0]['spec']['topic'] == 'whether she is all right'
    assert visits[0]['turns'][0]['speaker'] == 'gran' and visits[0]['closed_reason'] == 'everyone fell silent'
    worried = next(ev for ev in events(e, '@thought:gran') if 'check on her' in ev['observations']['gran']['text'])
    assert worried['day'] <= visits[0]['spec']['day']
    checks.append('live choice (stubbed model): a worried thought picks "go and talk", the grandmother walks to the child\'s room '
                  'and opens the conversation there, which ends on its own')

    # Someone busy who sets off (in transit, no room) can still be given a context (earth-family-3 crash).
    e, policy = world()
    c = Lifetime(e, policy, scripted=True)
    c.run(8 * H)
    living.act(c, 'gran', 'do:kitchen/stove/cook', None, 't1')
    c.run(8 * H + 1 / 1440)
    assert living.state(e)['doing']['gran']['phase'] == 'busy'
    e.state['household']['locations']['gran'] = None
    assert e.context('gran', 'I set off.')['physical_environment'] is None
    checks.append('a busy person in transit (no room) gets a context with no physical environment instead of crashing')

    # Validation.
    reject(lambda: living.validate({**living.parameters(), 'menu_size': 0}))
    bad = world()[1]
    bad['household']['rooms']['hall']['kind'] = 'castle'
    reject(lambda: Lifetime(world()[0], bad, scripted=True))
    bad = world()[1]
    bad['household']['creatures'] = [{'id': 'c', 'name': 'C', 'kind': 'cat', 'rooms': ['hall'], 'room': 'kitchen'}]
    reject(lambda: Lifetime(world()[0], bad, scripted=True))
    reject(lambda: living.validate_happening({'id': 'x', 'kind': 'incident', 'text': '{name} fell.', 'hours': [1, 2], 'rate_per_day': 1}, 'h'))
    checks.append('unknown room kinds, creatures outside their rooms, bad settings and person-happenings without self_text are rejected')

    result = {'passed': True, 'scope': 'synthetic living-world engineering checks; rates are design defaults, not calibrated', 'checks': checks}
    RESULTS_DIR.joinpath('living-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
