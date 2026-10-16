"""Scenario authoring checks: deterministic compile, strict vocabulary, model draft repair; stubbed model."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devsim.author import COMPILER_DEFAULTS, compile_scenario, draft, review
from devsim.engine import Engine
from devsim.lifetime import Lifetime

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
SPEC = {
    'title': 'New school term', 'summary': 'A teenager starts a new school; a parent works evenings.', 'seed': 7,
    'duration_years': .25,
    'people': [
        {'id': 'sam', 'name': 'Sam', 'age_years': 15, 'facets': {'N1': 70, 'E2': 30}, 'facet_basis': 'Anxious and shy.',
         'caregivers': ['dana'], 'goals': [{'id': 'friends', 'description': 'Make a friend.', 'priority': .8}],
         'private_background': ['I do not know anyone at school yet.']},
        {'id': 'dana', 'name': 'Dana', 'age_years': 42},
        {'id': 'baby', 'name': 'Rio', 'age_years': 1, 'caregivers': ['dana']}],
    'household': {'rooms': {'kitchen': {'label': 'the kitchen'}}, 'locations': {'sam': 'kitchen', 'dana': 'kitchen'},
                  'conversations': [{'id': 'week', 'day': 6.8, 'room': 'kitchen', 'participants': ['sam', 'dana'],
                                     'topic': 'The first week.', 'max_turns': 2}]},
    'situations': [{'id': 'lunch', 'actor': 'sam', 'situation': 'You sit alone at lunch.', 'rate_per_year': 40,
                    'goal_id': 'friends', 'options': [
        {'id': 'hi', 'label': 'Say hello.', 'success_probability': .6, 'valence_success': .4, 'valence_failure': -.3,
         'success_text': 'We talked.', 'failure_text': 'They turned away.', 'progress_gain': .2},
        {'id': 'ask', 'label': 'Ask Dana later.', 'contact': 'dana', 'contact_text': 'Sam asked me about school.',
         'success_probability': .8, 'valence_success': .3, 'valence_failure': -.2, 'success_text': 'Dana helped.',
         'failure_text': 'Dana was tired.'}]}],
    'interventions': [{'id': 'flyer', 'day': 14, 'description': 'A club flyer is handed out.',
                       'observations': {'sam': {'text': 'A teacher gave me a robotics club flyer.'}}}],
    'assumptions': ['Dana is home in the evenings.']}


def reject(spec):
    try:
        compile_scenario(spec, dry_run=False)
    except ValueError as exc:
        return str(exc)
    raise AssertionError('Invalid scenario accepted')


def edit(change):
    spec = deepcopy(SPEC)
    change(spec)
    return spec


def main():
    checks = []
    engine, policy, report = compile_scenario(deepcopy(SPEC))
    sam = engine.agent('sam')
    assert engine.state['entities']['sam']['facts'] == {'birth_day': -15 * 365.25, 'caregivers': ['dana']}
    assert sam['facets']['N1'] == 70 and sam['facets']['E2'] == 30 and sam['facets']['C1'] == 50
    assert sam['goals']['friends']['priority'] == .8 and 'runtime' not in engine.state
    background = sam['memory_meta']['scenario-background-sam-0']
    assert background['kind'] == 'internal' and background['provenance'] == 'scenario_authoring'
    assert 'scenario-background-sam-0' not in engine.agent('dana')['memory_meta']
    assert [e['id'] for e in engine.state['pending']] == ['scenario-flyer']
    checks += ['compile builds committed people, ages, caregivers, goals and listed facet percentiles; others stay neutral',
               'authored background is a labeled private starting experience of its owner only',
               'interventions become pending controller events for their listed recipients']

    paths = {n['path'] for n in report['generated_numbers']}
    assert {'people.0.facets.N1', 'situations.0.rate_per_year', 'situations.0.options.0.success_probability',
            'interventions.0.day', 'duration_years'} <= paths and 'seed' not in paths
    assert report['compiler_defaults'] == COMPILER_DEFAULTS and report['model_stated_assumptions'] == SPEC['assumptions']
    assert 'scenario assumptions' in policy['description']
    assert policy['cognition'] == {'semantic_recall': True, 'indexed_retrieval': True, 'graphiti_retrieval': True}
    checks += ['assumptions report lists every generated number, compiler default and stated assumption']

    dry = report['scripted_dry_run']
    assert dry['resolved_actions'] > 0 and dry['pending_events'] == 0 and dry['conversations'] == {'week': 'closed'}
    again = compile_scenario(deepcopy(SPEC))
    assert again[0].state == engine.state and again[1] == policy and again[2] == report
    checks += ['scripted dry run executes the compiled policy, including scheduled conversations and interventions',
               'compiling the same spec is deterministic']

    with TemporaryDirectory() as directory:
        engine.save(Path(directory) / 'initial.json')
        world = Engine.load(Path(directory) / 'initial.json')
        scripted = deepcopy(policy)
        scripted['cognition']['graphiti_retrieval'] = False  # keep test views out of the real graph outbox
        Lifetime(world, scripted, scripted=True).run(SPEC['duration_years'] * 365.25, Path(directory) / 'world.json')
        assert 'scenario-flyer' in world.agent('sam')['memory_meta'] and 'scenario-flyer' not in world.agent('dana')['memory_meta']
        assert world.state['actions'] and all(a['status'] == 'resolved' for a in world.state['actions'])
    checks += ['saved initial world runs under the compiled policy with a fresh controller']

    chained = edit(lambda s: s['interventions'][0].update(sets_facts={'sam': {'invited': True}}))
    chained['people'][0]['facts'] = {'club_member': False}
    yes = {'id': 'accept', 'label': 'Join.', 'success_probability': 1, 'valence_success': .5, 'valence_failure': 0,
           'success_text': 'I joined.', 'failure_text': 'I could not join.', 'contact': 'dana', 'contact_text': 'Sam joined a club.',
           'effects_success': {'facts': {'sam': {'club_member': True}}, 'relationship_role': 'confidant'}}
    no = {'id': 'decline', 'label': 'Decline.', 'success_probability': 1, 'valence_success': 0, 'valence_failure': 0,
          'success_text': 'I said no.', 'failure_text': 'I said no.'}
    chained['situations'] += [
        {'id': 'join', 'actor': 'sam', 'situation': 'You were invited to the club.', 'rate_per_year': 52,
         'requires_facts': {'sam': {'invited': True}}, 'options': [yes, no]},
        {'id': 'meeting', 'actor': 'sam', 'situation': 'The club meets.', 'rate_per_year': 52,
         'requires_facts': {'sam': {'club_member': True}}, 'options': [dict(no, id='attend', label='Attend.'), no]}]
    world, compiled, _ = compile_scenario(deepcopy(chained), dry_run=False)
    assert compiled['opportunities'][1]['options'][0]['requires'] == {'facts': {'sam': {'invited': True}}}
    assert 'requires_facts' not in compiled['opportunities'][1]
    assert compiled['opportunities'][1]['options'][0]['effects_success'] == {
        'facts': {'sam': {'club_member': True}}, 'relationships': [{'a': 'sam', 'b': 'dana', 'role': 'confidant'}]}
    assert world.state['entities']['sam']['facts']['club_member'] is False
    scripted = deepcopy(compiled)
    scripted['cognition']['graphiti_retrieval'] = False
    Lifetime(world, scripted, scripted=True).run(chained['duration_years'] * 365.25)
    days = {kind: [a['day'] for a in world.state['actions'] if f'-{kind}-' in a['id']] for kind in ('join', 'meeting')}
    joined = [a['day'] for a in world.state['actions'] if '-join-' in a['id'] and a['decision']['action_id'] == 'accept']
    assert days['join'] and min(days['join']) >= 14 and joined, days
    assert days['meeting'] and min(days['meeting']) > min(joined), (days, joined)
    assert world.state['entities']['sam']['facts']['club_member'] is True
    assert world.agent('sam')['relationships']['dana']['role'] == 'confidant'
    checks += ['a situation gated by requires_facts never occurs before an intervention sets the fact, and occurs after it',
               'option effects set facts that open later situations and give actor and contact a shared role']

    places = deepcopy(SPEC)
    places['people'].append({'id': 'coach', 'name': 'Coach Lee', 'age_years': 35})
    places['household'] = {
        'rooms': {'kitchen': {'label': 'the kitchen'}, 'lab': {'label': 'the school lab'}},
        'locations': {'sam': 'kitchen', 'dana': 'kitchen', 'coach': 'lab'},
        'routes': [{'a': 'kitchen', 'b': 'lab', 'minutes': 20}],
        'channels': {'family': {'label': 'the family chat', 'members': ['sam', 'dana']}},
        'groups': {'robotics': {'label': 'the robotics club', 'place': 'lab', 'members': ['coach'],
                                'meetings': {'first_day': 21, 'start_hour': 14.4, 'duration_hours': 1, 'every_days': 7, 'topic': 'The robot arm.'}}},
        'invitations': [{'id': 'club', 'day': 14.5, 'group': 'robotics', 'invitee': 'sam', 'inviter': 'coach'}],
        'conversations': [{'id': 'checkin', 'day': 30.8, 'channel': 'family', 'participants': ['dana', 'sam'], 'topic': 'School.',
                           'interviewer': 'dana', 'questions': ['How is the club?'], 'max_turns': 2}]}
    places['situations'].append({'id': 'build', 'actor': 'sam', 'situation': 'The club asks for ideas.', 'rate_per_year': 52,
        'requires_facts': {'sam': {'member_robotics': True}}, 'options': [
            {'id': 'share', 'label': 'Share an idea.', 'success_probability': .5, 'valence_success': .5, 'valence_failure': -.3,
             'success_text': 'They liked my idea.', 'failure_text': 'Nobody picked it up.', 'contact': 'coach',
             'contact_text': 'Sam shared an idea.', 'conversation': {'topic': 'The idea.', 'questions': ['Can you explain it?']}},
            {'id': 'quiet', 'label': 'Stay quiet.', 'success_probability': 1, 'valence_success': 0, 'valence_failure': 0,
             'success_text': 'I listened.', 'failure_text': 'I listened.'}]})
    world, compiled, report = compile_scenario(deepcopy(places))
    assert world.state['entities']['coach']['facts']['member_robotics'] is True
    assert 'member_robotics' not in world.state['entities']['sam']['facts']
    dry = report['scripted_dry_run']
    assert dry['conversations']['checkin'] == 'closed' and dry['conversations']['group-robotics-0'] == 'closed'
    probe, _, _ = compile_scenario(deepcopy(places), dry_run=False)
    scripted = deepcopy(compiled)
    scripted['cognition']['graphiti_retrieval'] = False
    Lifetime(probe, scripted, scripted=True).run(places['duration_years'] * 365.25)
    builds = [a['day'] for a in probe.state['actions'] if '-build-action' in a['id']]
    assert probe.state['entities']['sam']['facts']['member_robotics'] is True and builds and min(builds) > 14.5
    checks += ['authored places, routes, groups, channels, invitations and interviews compile and run; membership facts gate situations']

    def returns(*answers):
        calls = iter(answers)
        return lambda system, context, api, model, max_tokens=600: next(calls)
    good = {'issues': [{'path': 'situations.0.options.1.contact_text', 'kind': 'timing', 'problem': 'Presupposes a later event.'}]}
    wrong = {'issues': [{'path': 'situations.9.label', 'kind': 'timing', 'problem': 'x'}]}
    before = deepcopy(SPEC)
    with patch('devsim.engine.request_json', side_effect=returns(wrong, good)):
        issues = review('A teenager starts a new school.', SPEC, api='stub', model='stub')
    assert issues == [{**good['issues'][0], 'value': SPEC['situations'][0]['options'][1]['contact_text']}] and SPEC == before
    with patch('devsim.engine.request_json', side_effect=returns(wrong, wrong, wrong)):
        try:
            review('A teenager starts a new school.', SPEC, api='stub', model='stub')
            raise AssertionError('review citing a missing field accepted')
        except ValueError:
            pass
    checks.append('a setting review must cite real spec fields; it returns their values, is repaired or fails, and edits nothing')

    errors = [
        reject(edit(lambda s: s.update(extra=1))),
        reject(edit(lambda s: s['people'][0]['facets'].update(Z9=50))),
        reject(edit(lambda s: s['people'][0]['facets'].update(N1=140))),
        reject(edit(lambda s: s['people'][0].pop('facet_basis'))),
        reject(edit(lambda s: s['people'].append(deepcopy(s['people'][1])))),
        reject(edit(lambda s: s['people'][1].update(id='Dana:1'))),
        reject(edit(lambda s: s['people'][1].update(caregivers=['sam']))),
        reject(edit(lambda s: s['situations'][0].update(actor='nobody'))),
        reject(edit(lambda s: s['situations'][0].update(rate_per_year=500))),
        reject(edit(lambda s: s['situations'][0]['options'][1].pop('contact_text'))),
        reject(edit(lambda s: s['situations'][0]['options'][0].update(success_probability=1.5))),
        reject(edit(lambda s: s['situations'][0]['options'][0].update(effects_success={}))),
        reject(edit(lambda s: s['situations'][0]['options'][0].update(effects_success={'births': []}))),
        reject(edit(lambda s: s['situations'][0].update(requires_facts={'sam': {'never_set': True}}))),
        reject(edit(lambda s: s['situations'][0]['options'][0].update(effects_success={'relationship_role': 'friend'}))),
        reject(edit(lambda s: s['people'][0].update(facts={'caregivers': []}))),
        reject(edit(lambda s: s['interventions'][0].update(sets_facts={'ghost': {'x': True}}))),
        reject(edit(lambda s: s.update(household={'rooms': {'k': {'label': 'K'}}, 'groups': {'Bad Id': {'label': 'x', 'place': 'k'}}}))),
        reject(edit(lambda s: s['situations'][0]['options'][0].update(conversation={'topic': 'x'}))),
        reject(edit(lambda s: s['situations'][0].update(options=s['situations'][0]['options'][:1]))),
        reject(edit(lambda s: s['interventions'][0].update(day=400))),
        reject(edit(lambda s: s['interventions'][0]['observations'].update(ghost={'text': 'Boo.'}))),
        reject(edit(lambda s: s['interventions'][0]['observations']['sam'].update(kind='testimony'))),
        reject(edit(lambda s: s['interventions'][0]['observations']['sam'].update(kind='testimony', source='sam'))),
        reject(edit(lambda s: s['household']['conversations'][0]['participants'].append('nobody'))),
        reject(edit(lambda s: s.update(people=[deepcopy(s['people'][1])] * 9))),
    ]
    assert all(errors) and any('facets' in e for e in errors) and any('unsupported' in e for e in errors)
    assert any('Facts that can be set for sam: none' in e for e in errors)
    checks += ['out-of-vocabulary keys, facet codes and ranges, ids, caregivers, actors, contacts, rates, probabilities, '
               'intervention days/recipients, testimony sources, fact keys/values/reachability, effects, conversation participants and size limits are rejected with field names']

    calls = []
    def stub(system, context, api, model, max_tokens=600):
        calls.append(context)
        assert context['task'] == 'author_scenario' and 'robotics' in context['setting']
        return {**SPEC, 'people': 'everyone'} if len(calls) == 1 else deepcopy(SPEC)
    with patch('devsim.engine.request_json', side_effect=stub):
        spec = draft('A teenager joins a robotics club at a new school.', api='stub', model='stub')
    assert spec == SPEC and len(calls) == 2 and 'people' in calls[1]['output_repair']['validation_error']
    assert calls[1]['output_repair']['previous_output'] == {**SPEC, 'people': 'everyone'}
    with patch('devsim.engine.request_json', return_value={'title': 'x'}):
        try:
            draft('A teenager joins a robotics club.', api='stub', model='stub')
            raise AssertionError('Invalid draft accepted')
        except ValueError:
            pass
    checks += ['model drafts must compile; repairs return the previous draft with the field-named error, and fail after two']

    result = {'passed': True, 'scope': 'engineering only; stubbed transport', 'checks': checks}
    RESULTS_DIR.joinpath('author-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
