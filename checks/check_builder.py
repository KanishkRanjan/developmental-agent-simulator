"""The step-by-step builder: design -> compiled world (scripted and with a stubbed model), sliders, relationships,
family warmth, crowd and modules, the two ways to begin, plain-language problems, and builder-only limits."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devsim import author, builder
from devsim.engine import Engine
from devsim.lifetime import Lifetime

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def design():
    d = builder.new_design('Check Street')
    d['places'] = [{'id': 'rao', 'template': 'home', 'label': 'Rao home'}, {'id': 'kim', 'template': 'home', 'label': 'Kim home'},
                   {'id': 'hill', 'template': 'school', 'label': 'Hill School'}, {'id': 'ward', 'template': 'hospital', 'label': 'City Ward'}]
    d['routes'] = {'rao|hill': 15}
    d['people'] = [
        {'id': 'asha', 'name': 'Asha', 'age': 15, 'role': 'main', 'home': 'rao', 'place': 'hill', 'hours': 'student',
         'description': 'a curious, anxious new student', 'sliders': {'N': 80, 'E': 25}, 'goals': [{'description': 'Make one friend.', 'priority': .8}]},
        {'id': 'ravi', 'name': 'Ravi', 'age': 45, 'role': 'main', 'home': 'rao', 'place': 'ward', 'hours': 'evening shift',
         'description': 'a tired nurse who worries about his daughter'},
        {'id': 'jin', 'name': 'Jin', 'age': 15, 'role': 'main', 'home': 'kim', 'place': 'hill', 'hours': 'student',
         'description': 'a cheerful classmate who loves robots'},
        {'id': 'nani', 'name': 'Nani', 'age': 70, 'role': 'side', 'home': 'rao', 'hours': 'at home', 'description': 'warm grandmother'},
        {'id': 'mo', 'name': 'Mo', 'age': 40, 'role': 'side', 'home': 'kim', 'hours': 'at home', 'description': "Jin's dad"}]
    d['relationships'] = [{'a': 'ravi', 'b': 'asha', 'type': 'parent of'}, {'a': 'nani', 'b': 'asha', 'type': 'grandparent of'},
                          {'a': 'asha', 'b': 'jin', 'type': 'new classmate'}, {'a': 'mo', 'b': 'jin', 'type': 'parent of'}]
    d['crowd'] = 'small'
    d['begin'] = {'mode': 'none', 'years': 0}
    return d


def stub(system, context, api, model, max_tokens=600):
    if context.get('task') == 'fill_person':
        out = {'facets': {'O1': 70}, 'background': [f'I am {context["name"]}.']}
        if context['role'] == 'main character':
            out['goals'] = [] if context['given_goals'] else [{'description': 'Get through the week.', 'priority': .5}]
            out['situation'] = {'situation': 'You have a free hour.', 'room_kind': 'bedroom', 'hours': [18, 20],
                                'options': [{'label': 'Read', 'success_probability': .8, 'valence_success': .3, 'valence_failure': -.1,
                                             'success_text': 'I read.', 'failure_text': 'I could not focus.'},
                                            {'label': 'Rest', 'success_probability': 1, 'valence_success': .1, 'valence_failure': 0,
                                             'success_text': 'I rested.', 'failure_text': 'I rested.'}]}
        return out
    if context.get('task') == 'generate_biography':
        fields = context['allowed_fields']
        return {'current_facts': {f: f'{f} so far' for f in fields}, 'overview': 'A short synthetic past.',
                'timeline': [{'field': f, 'value': f'{f} so far', 'start_day': context['birth_day'], 'end_day': context['simulated_day']}
                             for f in fields]}
    raise AssertionError(f'unexpected model call {context.get("task")}')


def main():
    checks = []
    with TemporaryDirectory() as directory:
        out = builder.build(design(), out=Path(directory) / 'scripted')
        world = Engine.load(out / 'initial.json')
        policy = json.loads((out / 'policy.json').read_text())
        spec = json.loads((out / 'scenario.json').read_text())
        rooms = spec['household']['rooms']
        assert {r['site'] for r in rooms.values()} == {'rao', 'kim', 'hill', 'ward'}
        assert {r['kind'] for r in rooms.values()} >= {'bedroom', 'kitchen', 'living_room', 'bathroom', 'classroom', 'cafeteria', 'ward'}
        assert spec['household']['locations']['asha'] == 'rao_asha_room' and 'rao_kitchen' in rooms['rao_asha_room']['audible_to']
        assert any(r['minutes'] == 15 and {rooms[r['a']]['site'], rooms[r['b']]['site']} == {'rao', 'hill'} for r in spec['household']['routes'])
        groups = spec['household']['groups']
        assert sorted(groups['hill_class']['members']) == ['asha', 'jin'] and groups['ward_shift']['members'] == ['ravi']
        assert set(spec['household']['channels']['rao_chat']['members']) == {'asha', 'ravi', 'nani'}
        couple = design(); next(pl for pl in couple['places'] if pl['id'] == 'rao')['shared'] = {'nani': 'ravi'}
        couple_rooms, couple_homes, _ = builder.rooms_for(couple)
        assert couple_homes['nani'] == couple_homes['ravi'] == 'rao_ravi_room' and 'rao_nani_room' not in couple_rooms
        assert couple_rooms['rao_ravi_room']['label'].endswith(' and Nani\'s bedroom'), couple_rooms['rao_ravi_room']
        checks.append('two people at home can share one bedroom, labelled with both names')
        checks.append('templates lay out homes (a bedroom each, shared rooms within earshot), a school and a ward as sites with kinds, '
                      'routes from homes with set or default minutes, groups from daily hours, and a family chat per home')
        a = world.agent('asha')
        assert all(a['facets'][f'N{k}'] == 80 for k in range(1, 7)) and a['facets']['E3'] == 25 and a['initial_facets'] == a['facets']
        assert a['relationships']['jin']['role'] == 'classmate' and world.agent('jin')['relationships']['asha']['closeness'] == .1
        assert a['relationships']['ravi']['closeness'] == .6 and world.agent('ravi')['relationships']['asha']['trust'] == .7
        assert 'ravi' in world.state['entities']['asha']['facts']['caregivers'] and a['goals'] and world.agent('ravi')['goals']
        assert not world.agent('nani')['goals'] and {s['actor'] for s in spec['situations']} == {'asha', 'ravi', 'jin'}
        assert policy['society_layer'] == {'overrides': {'grid': 8}} and all(policy[m] == {} for m in ('hormones', 'attention', 'sleep', 'skills'))
        assert 'living' in policy and policy['horizon_days'] == 30 and 'background_expansion' not in policy
        Lifetime(world, policy, scripted=True).run(.5)
        checks.append('a scripted build turns sliders into facets, applies relationships both ways (family links warm, a new '
                      'classmate barely known), gives main characters goals and a situation of their own, side characters neither, '
                      'switches on the chosen modules and crowd, and the world runs')

        calls = []
        d = design()
        d['begin'] = {'mode': 'fill', 'years': 0}
        with patch('devsim.engine.request_json', side_effect=lambda *a, **k: calls.append(a[1]['task']) or stub(*a, **k)):
            out = builder.build(d, api='http://x', model='m', out=Path(directory) / 'model')
        world = Engine.load(out / 'initial.json')
        assert calls.count('fill_person') == 5 and calls.count('generate_biography') == 3  # Ravi, Nani and Mo are 18 or over
        assert world.agent('jin')['facets']['O1'] == 70 and world.agent('asha')['facets']['N1'] == 80, 'sliders win over the model'
        assert 'personal-history-v1' in world.state['entities']['ravi']['generated_biography']
        assert 'generated_biography' not in world.state['entities']['asha']
        assert any('I am Nani.' in str(m) for m in [o.text for o in world.world.observations.get('nani', [])]) or \
            world.state['entities']['nani']['facts'].get('education')
        policy = json.loads((out / 'policy.json').read_text())
        assert policy['background_expansion']['default']['min_age'] == 18
        checks.append('with the model: one small fill call per person (sliders win over model facets), and "fill the past" writes '
                      'a biography for each adult before day 0')

        d = design()
        d['begin'] = {'mode': 'fast_forward', 'years': 3}
        out = builder.build(d, out=Path(directory) / 'ff')
        world = Engine.load(out / 'initial.json')
        policy = json.loads((out / 'policy.json').read_text())
        age = (world.day - world.agent('asha')['birth_day']) / 365.25
        assert abs(world.day - 3 * 365.25) < 1 and abs(age - 15) < .01 and 'runtime' not in world.state
        assert abs(policy['horizon_days'] - (world.day + 30)) < 1e-6
        assert json.loads((out / 'assumptions.json').read_text())['scripted_history']['years'] == 3
        Lifetime(world, policy, scripted=True).run(world.day + .5)
        checks.append('fast-forward ages everyone by the chosen years with scripted highlights, clears the run state, records the '
                      'scripted history, and the live policy starts there with its horizon counted from that day')

    bad = design()
    bad['people'][0]['home'] = 'hill'
    bad['people'].append(dict(bad['people'][1], id='ravi'))
    bad['begin'] = {'mode': 'fast_forward', 'years': 20}
    problems = builder.check_design(bad)
    assert any('Asha needs a home' in p for p in problems) and any('share a name' in p for p in problems)
    assert any('not be born yet' in p for p in problems)
    checks.append('the builder explains what is missing in plain words (no home, a shared name, not born before a fast-forward)')

    crowded = json.loads(json.dumps(builder.assemble(design(), {p['id']: builder.scripted_fill(p, design()) for p in design()['people']})))
    for n in range(5):
        extra = deepcopy(crowded['people'][3])
        extra.update(id=f'n{n}', name=f'N{n}')
        crowded['people'].append(extra)
        crowded['household']['rooms'][f'rao_n{n}_room'] = {'label': f"N{n}'s bedroom", 'kind': 'bedroom', 'site': 'rao', 'audible_to': []}
        crowded['household']['locations'][f'n{n}'] = f'rao_n{n}_room'
    try:
        author.compile_scenario(deepcopy(crowded), dry_run=False)
        raise AssertionError('ten people accepted under the draft limit')
    except ValueError:
        pass
    author.compile_scenario(deepcopy(crowded), dry_run=False, limits=builder.BUILDER_LIMITS)
    assert author.LIMITS['people'] == 8
    checks.append('builder designs may hold more people and situations than one model draft; the draft limits stay as they were')

    with TemporaryDirectory() as tmp:
        home = Path(tmp)
        assert builder.next_build_folder(home) == home / 'compiled'
        (home / 'compiled').mkdir()
        assert builder.next_build_folder(home) == home / 'compiled'  # an empty folder is reused
        (home / 'compiled' / 'initial.json').write_text('{}')
        (home / 'compiled-2').mkdir()
        (home / 'compiled-2' / 'initial.json').write_text('{}')
        assert builder.next_build_folder(home) == home / 'compiled-3'
    checks.append('a rebuild goes to the next free compiled-N folder; earlier builds that runs may point at are kept')

    result = {'passed': True, 'scope': 'builder engineering checks with scripted fills and a stubbed model', 'checks': checks}
    RESULTS_DIR.joinpath('builder-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
