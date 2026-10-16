"""Environment checks: channels, invitations, group meetings with commutes, scheduled and agent-initiated interviews."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from devsim.engine import Engine, FACET_NAMES
from devsim.lifetime import Lifetime

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
PEOPLE = {'mom': 40, 'kid': 15, 'teacher': 35, 'friend': 15, 'grandpa': 70, 'neighbor': 50}


def fixture():
    e = Engine(seed=11)
    for p, age in PEOPLE.items():
        e.entity(p, p.title(), {'birth_day': -age * 365.25})
        e.materialize(p, dict.fromkeys(FACET_NAMES, 50), birth_day=-age * 365.25)
    e.advance(0)
    ask = {'id': 'ask', 'label': 'Ask Mom some questions.', 'success_probability': 1, 'valence_success': .2, 'valence_failure': 0,
           'success_text': 'I asked Mom.', 'failure_text': 'I could not ask.', 'contact': 'mom', 'contact_text': 'Kid wants to ask me something.',
           'conversation': {'topic': 'Questions about work.', 'questions': ['What is your shift like?']}}
    wait = {'id': 'wait', 'label': 'Wait.', 'success_probability': 1, 'valence_success': 0, 'valence_failure': 0,
            'success_text': 'I waited.', 'failure_text': 'I waited.'}
    policy = {'sampling': 'event_driven', 'planning': {'calendar_mode': 'elapsed', 'hours_per_day': 10},
        'expression': {'age_appropriate_actions': True},
        'opportunities': [{'id': 'curious', 'actor': 'kid', 'situation': 'You wonder about Mom\'s job.', 'rate_per_year': 150,
                           'options': [ask, wait]}],
        'household': {
            'rooms': {'kitchen': {'label': 'the kitchen', 'audible_to': ['hall']}, 'hall': {'label': 'the hallway'},
                      'bedroom': {'label': 'the bedroom'}, 'lab': {'label': 'the school lab'},
                      'friend_home': {'label': 'the friend\'s home'}, 'next_door': {'label': 'next door'}, 'ward': {'label': 'the ward'}},
            'locations': {'mom': 'kitchen', 'kid': 'bedroom', 'teacher': 'lab', 'friend': 'friend_home', 'grandpa': 'hall',
                          'neighbor': 'next_door'},
            'routines': {p: {'available_hours': [[7, 22]], 'response_minutes': [3, 3]} for p in PEOPLE},
            'routes': [{'a': 'bedroom', 'b': 'lab', 'minutes': 20}, {'a': 'friend_home', 'b': 'lab', 'minutes': 15},
                       {'a': 'next_door', 'b': 'ward', 'minutes': 30}],
            'channels': {'family': {'label': 'the family chat', 'members': ['mom', 'kid']}},
            'groups': {'shift': {'label': 'the evening shift', 'place': 'ward', 'members': ['neighbor'],
                                 'meetings': {'first_day': 1, 'start_hour': 15, 'duration_hours': 3, 'every_days': 1, 'topic': 'Work.'}},
                       'robotics': {'label': 'the robotics club', 'place': 'lab', 'members': ['teacher', 'friend'],
                                    'meetings': {'first_day': 3, 'start_hour': 14.4, 'duration_hours': 1.5, 'every_days': 7, 'topic': 'Build the robot arm.',
                                                 'max_turns': 4}}},
            'moves': [{'id': 'downstairs', 'day': 4.79, 'actor': 'kid', 'room': 'kitchen'}],
            'invitations': [{'id': 'join', 'day': 2.5, 'group': 'robotics', 'invitee': 'kid', 'inviter': 'teacher'}],
            'conversations': [
                {'id': 'chat', 'day': 1.5, 'channel': 'family', 'participants': ['mom', 'kid'], 'topic': 'Dinner plans.', 'max_turns': 2},
                {'id': 'checkin', 'day': 4.8, 'room': 'kitchen', 'participants': ['mom', 'kid'], 'topic': 'How school is going.',
                 'interviewer': 'mom', 'questions': ['How was the club?', 'Who did you meet?'], 'max_turns': 4}]}}
    return e, policy


def received(e, owner, prefix):
    return [k for k in e.agent(owner)['memory_meta'] if k.startswith(prefix)]


def reject(change):
    e, policy = fixture()
    change(policy)
    try:
        Lifetime(e, policy, scripted=True)
    except ValueError as exc:
        return str(exc)
    raise AssertionError('Invalid environment accepted')


def main():
    checks = []
    e, policy = fixture()
    Lifetime(e, policy, scripted=True).run(10)
    runtime = e.state['runtime']

    chat = runtime['conversations']['chat']
    assert [t['speaker'] for t in chat['turns']] == ['mom', 'kid'] and chat['status'] == 'closed'
    first = e.state['events'][[ev['id'] for ev in e.state['events']].index(chat['turns'][0]['event'])]
    assert set(first['observations']) == {'mom', 'kid'}
    assert first['observations']['kid']['kind'] == 'direct' and first['observations']['kid']['encountered'] == []
    assert 'wrote:' in first['observations']['kid']['text']
    assert not received(e, 'grandpa', '@conversation:chat') and not received(e, 'teacher', '@conversation:chat')
    checks.append('a channel conversation reaches members in other rooms as read messages, not encounters, and no one else')

    assert 'kid' in e.state['household']['memberships']['robotics'] and e.state['entities']['kid']['facts']['member_robotics'] is True
    assert received(e, 'kid', '@invitation:join') and '@invitation:join:reply' in e.agent('teacher')['memory_meta']
    assert any(a['id'] == '@invitation:join:action' and a['status'] == 'resolved' for a in e.state['actions'])
    checks.append('an invitation is received, decided by the invitee, and acceptance becomes membership and a committed fact')

    meeting = runtime['conversations']['group-robotics-0']
    assert set(meeting['spec']['participants']) == {'teacher', 'friend', 'kid'} and meeting['turns']
    trip = next(b for b in e.agent('kid')['calendar'] if b['activity'] == '@travel:group-robotics-0-kid')
    assert abs((trip['end_day'] - trip['start_day']) * 1440 - 20) < 1e-6 and trip['start_day'] == 3.6
    assert meeting['spec']['day'] > trip['end_day'] and meeting['turns'][0]['day'] >= meeting['spec']['day']
    assert all(set(e.state['events'][[ev['id'] for ev in e.state['events']].index(t['event'])]['observations']) <= {'teacher', 'friend', 'kid'}
               for t in meeting['turns'])
    assert '@travel:group-robotics-0-kid:depart' in e.agent('kid')['memory_meta']
    assert '@travel:group-robotics-0-kid-home:arrive' in e.agent('kid')['memory_meta']
    assert e.state['household']['locations']['kid'] == 'kitchen' and e.state['household']['locations']['friend'] == 'friend_home'
    assert e.state['household']['locations']['teacher'] == 'lab' and not runtime['trips']
    assert runtime['group_meetings']['robotics']['count'] == 1 and runtime['group_meetings']['robotics']['next_day'] == 10.6
    shifts = [k for k in e.agent('neighbor')['memory_meta'] if k.startswith('@travel:group-shift-') and k.endswith(':arrive')]
    assert len(shifts) >= 16 and e.state['household']['locations']['neighbor'] == 'next_door'
    assert not any(k.startswith('group-shift') for k in runtime['conversations'])
    assert any(t.get('status') == 'one attendee; no conversation' for t in runtime['trace'])
    checks.append('a one-person group (a work shift) commutes there and back every day without a conversation')
    checks += ['group meetings bring available members to the meeting place over timed routes, then home again',
               'meeting talk reaches only the people at the meeting place']

    interview = runtime['conversations']['checkin']
    turns = interview['turns']
    assert [t['speaker'] for t in turns] == ['mom', 'kid', 'mom', 'kid'] and interview['closed_reason'] == 'questions finished'
    questions = [e.state['actions'][[a['id'] for a in e.state['actions']].index(t['action'])]['decision']['speech'] for t in turns[::2]]
    assert questions == ['How was the club?', 'Who did you meet?']
    assert all(t2['day'] > t1['day'] for t1, t2 in zip(turns, turns[1:]))
    assert all(any(b['activity'].startswith('@conversation:checkin') for b in e.agent(p)['calendar']) for p in ('mom', 'kid'))
    heard = [h for h in received(e, 'grandpa', '@conversation:checkin') if not h.endswith(':opening')]
    assert len(heard) == 4
    assert heard and all(e.state['events'][[ev['id'] for ev in e.state['events']].index(h)]['observations']['grandpa']['kind'] == 'testimony'
                         for h in heard)
    assert not received(e, 'neighbor', '@conversation:checkin')
    checks += ['a scheduled interview asks the fixed questions in order and takes simulated time on both calendars',
               'interview speech is overheard in an audible adjacent room and not beyond it']

    talks = {k: s for k, s in runtime['conversations'].items() if k.endswith('-talk')}
    assert talks and all(s['spec']['interviewer'] == 'kid' and s['spec']['questions'] == ['What is your shift like?'] and
                         s['spec']['participants'] == ['kid', 'mom'] for s in talks.values())
    assert any(s['spec'].get('channel') == 'family' for s in talks.values()) or any('room' in s['spec'] for s in talks.values())
    checks.append('an agent can start an interview with a contact by choosing an option; it runs over a shared room or channel')

    with TemporaryDirectory() as directory:
        path = Path(directory) / 'world.json'
        a, policy_a = fixture()
        Lifetime(a, policy_a, scripted=True).run(3.7, path)
        resumed = Engine.load(path)
        Lifetime(resumed, deepcopy(policy_a), scripted=True).run(10)
        b, policy_b = fixture()
        Lifetime(b, policy_b, scripted=True).run(10)
        assert resumed.state == b.state
    checks.append('a checkpoint saved mid-commute and mid-meeting resumes to the same state as an uninterrupted run')

    errors = [
        reject(lambda p: p['household']['routes'].append({'a': 'bedroom', 'b': 'moon', 'minutes': 5})),
        reject(lambda p: p['household']['conversations'][0]['participants'].append('teacher')),
        reject(lambda p: p['household']['invitations'][0].update(invitee='friend')),
        reject(lambda p: p['household']['conversations'][1]['participants'].append('grandpa')),
        reject(lambda p: p['household']['conversations'][1].pop('questions')),
        reject(lambda p: p['opportunities'][0]['options'][0].pop('contact')),
        reject(lambda p: p['household']['groups']['robotics']['meetings'].update(duration_hours=30)),
        reject(lambda p: p['household']['groups']['robotics']['meetings'].update(duration_hours=[15, 17])),
        reject(lambda p: p['household']['groups']['robotics']['meetings'].update(first_day=3.6)),
        reject(lambda p: p['household']['channels']['family'].update(members=['mom'])),
    ]
    assert all(errors)
    checks.append('unknown route rooms, non-member channel speakers, existing-member invitations, malformed interviews, '
                  'contactless option conversations, oversized meetings and one-person channels are rejected')

    result = {'passed': True, 'scope': 'engineering only; scripted fixture', 'checks': checks}
    RESULTS_DIR.joinpath('environment-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
