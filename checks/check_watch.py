"""Terminal watcher checks: read-only loading, labeled feed, filters and layout widths; no terminal needed."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from checks.check_report import world
from devsim.watch import (help_lines, clock, engine_lines, feed_lines, footer, header, load, people_lines, read_calls, stats_lines,
                          status_line, summarize)


def load_world(engine):
    """load() on a saved copy of a world, as the watcher reads a run."""
    with TemporaryDirectory() as directory:
        engine.save(Path(directory) / 'world.json')
        return load(Path(directory))


def main():
    checks = []
    _, engine = world()
    with TemporaryDirectory() as directory:
        run = Path(directory) / 'run'
        run.mkdir()
        assert load(run)['people'] == [] and load(run)['calls'] == 0
        engine.save(run / 'world.json')
        (run / 'requests.jsonl').write_text(json.dumps({'purpose': 'appraisal', 'agent': 'sam', 'simulated_day': 3.5}) + '\n{"purp')
        raw = (run / 'world.json').read_bytes()
        data = load(run)
        assert (run / 'world.json').read_bytes() == raw
        assert data['calls'] == 2 and data['last'] == {'purpose': 'appraisal', 'agent': 'sam', 'day': 3.5}
        assert [p['id'] for p in data['people']] == sorted(engine.state['agents'])
        checks.append('loading is read-only, works before a checkpoint exists and skips a half-written last call')

        lines = feed_lines(data, 60)
        heads = [text for tag, text in lines if tag == 'head']
        spoken = [a for a in engine.state['actions'] if a['decision'].get('speech')]
        assert heads and all(text.startswith('d') for text in heads)
        assert any('kitchen' in text.lower() for text in heads) or any('situation:' in text for text in heads)
        assert len([1 for tag, _ in lines if tag == 'speech']) >= len(spoken) > 0
        assert all(len(text) <= 60 for _, text in lines)
        checks.append('the feed groups decisions under day, time and place headings and wraps to the panel width')

        speech_only = feed_lines(data, 60, everyone=False)
        assert not [1 for tag, _ in speech_only if tag == 'quiet']
        dana = feed_lines(data, 60, only='dana')
        assert all('Sam' not in text.split(':')[0] for tag, text in dana if tag == 'speech')
        checks.append('the speech-only toggle and the one-person filter narrow the feed')

        for width in (40, 80, 200):
            assert len(header(data, run, width)) <= width and len(footer(data, True, 'sam', width)) <= width
            assert all(len(text) <= width for _, text in people_lines(data, width))
        assert clock(14.72) == 'd14 17:17' and clock(0) == 'd0 00:00'
        checks.append('header, footer and people panel fit any width from 40 columns; clock shows day and time')

        # Engine view: each call as what it was asked and what came back, read incrementally.
        rows = [{'purpose': 'semantic_recall', 'agent': 'sam', 'simulated_day': 3.5, 'seconds': 6.5,
                 'context': {'situation': 'Lunch.', 'memory_candidates': [{'event': 'm1', 'text': 'Kiara laughed at me.'}]},
                 'response': {'memory_ids': ['m1']}},
                {'purpose': 'action', 'agent': 'sam', 'simulated_day': 3.6, 'seconds': 8.0,
                 'context': {'situation': 'Lunch.', 'available_actions': [{'id': 'speak'}, {'id': 'listen'}],
                             'repeat_notice': {'your_earlier_words': 'Can I sit here?'}, 'output_repair': {'validation_error': 'bad id'}},
                 'response': {'action_id': 'speak', 'speech': 'Hi, I am Sam.', 'plan': []}}]
        calls = run / 'requests.jsonl'
        calls.write_text(json.dumps(rows[0]) + '\n' + json.dumps(rows[1])[:40])
        cache = read_calls(calls, {})
        assert len(cache['recent']) == 1 and cache['stats'] == {'semantic_recall': [1, 6.5, 0]}
        calls.write_text(json.dumps(rows[0]) + '\n' + json.dumps(rows[1]) + '\n')
        read_calls(calls, cache)
        assert len(cache['recent']) == 2 and cache['stats']['action'] == [1, 8.0, 1]
        view = '\n'.join(text for _, text in engine_lines(cache['recent'], 70))
        assert 'recalls: Kiara laughed at me.' in view and 'says: "Hi, I am Sam."' in view
        assert 'about to repeat "Can I sit here?"' in view and 'repair after: bad id' in view and 'REPAIRED' in view
        assert all(len(text) <= 70 for _, text in engine_lines(cache['recent'], 70))
        assert not engine_lines(cache['recent'], 70, only='dana')
        assert any('action' in text for _, text in stats_lines(data, cache, 26)) and all(len(t) <= 26 for _, t in stats_lines(data, cache, 26))
        assert summarize({**rows[1], 'response': None})['output'] == []  # a call still in flight
        data.update(started=1000.0, horizon=60, day=10.0, current={'purpose': 'appraisal', 'agent': 'sam', 'started': 4590.0},
                    status='running')
        line = status_line(data, 200, now=4600.0)
        assert 'now: sam appraisal for 10s' in line and '10.00 sim days per hour' in line and 'about 5h00m left' in line
        assert len(status_line(data, 40, now=4600.0)) <= 40
        checks.append('the engine view shows each model call\'s input and output (recalled memories, speech, repeat re-asks, repairs), '
                      'reads the call log incrementally without half-written lines, and the status line shows the call in flight, pace and time left')

    # run_live records the call in flight and removes it when the call ends, even on failure.
    from devsim.run_live import recorder
    with TemporaryDirectory() as directory:
        path, seen = Path(directory) / 'requests.jsonl', []
        def transport(system, context, api, model, max_tokens):
            seen.append(json.loads(path.with_name('current.json').read_text())['purpose'])
            if context.get('fail'):
                raise RuntimeError('server down')
            return {'meaning': 'x', 'valence': 0, 'arousal': 0, 'importance': 0, 'confidence': 1}
        wrapped = recorder(transport, path, {})
        wrapped('s', {'new_observation': {'text': 'Hi'}, 'identity': {'id': 'sam'}}, 'api', 'm')
        try:
            wrapped('s', {'new_observation': {'text': 'Hi'}, 'fail': True}, 'api', 'm')
        except RuntimeError:
            pass
        assert seen == ['appraisal', 'appraisal'] and not path.with_name('current.json').exists()
        checks.append('run_live writes the call in flight to current.json and removes it when the call ends, including failed calls')
        # Token usage: the recorder stores the server's counts and a clock time with every call.
        from devsim import engine as engine_module
        def counted(system, context, api, model, max_tokens):
            engine_module.LAST_USAGE.update(prompt_tokens=900, completion_tokens=45, tokens_per_second=30.5)
            return {'meaning': 'x', 'valence': 0, 'arousal': 0, 'importance': 0, 'confidence': 1}
        recorder(counted, path, {})('s', {'new_observation': {'text': 'Hi'}, 'identity': {'id': 'sam'}}, 'api', 'm')
        row = json.loads(path.read_text().splitlines()[-1])
        assert row['usage'] == {'prompt_tokens': 900, 'completion_tokens': 45, 'tokens_per_second': 30.5} and row['finished'] > 0
        checks.append('run_live records each call\'s prompt/output tokens, generation speed and finish time')

    # Graphs: per-minute token sums, per-call speed, how each day felt, now and next.
    from devsim.watch import graph_lines, per_minute, spark, call_lines, latest_call
    assert spark([0, 1, 2, None, 4], 5) == '▁▂▄ █' and spark([], 3) == ''
    now = 10_000.0
    timeline = [{'finished': now - 30, 'output': 50, 'prompt': 1000, 'seconds': 9, 'speed': 30},
                {'finished': now - 40, 'output': 70, 'prompt': 900, 'seconds': 8, 'speed': 28},
                {'finished': now - 200, 'output': 10, 'prompt': 100, 'seconds': 2, 'speed': 25}]
    assert per_minute(timeline, 'output', 5, now) == [None, 10, None, None, 120] and per_minute(timeline, 'calls', 5, now)[-1] == 2
    shown = '\n'.join(text for _, text in graph_lines({'current': None, 'felt': [('Sam', [.5, None, -.5])], 'upcoming': [(3.5, 'meeting club')]},
                                                     {'timeline': timeline}, 120, now))
    assert 'output tok/min' in shown and 'now 120' in shown and 'gen tok/s' in shown and 'd3 12:00  meeting club' in shown and 'Sam' in shown
    assert 'no timed calls yet' in '\n'.join(t for _, t in graph_lines({'current': None}, {'timeline': [{'seconds': 3}]}, 80, now))
    checks.append('graphs show output/prompt tokens and calls per minute, generation speed and seconds per call, '
                  'how each person\'s days felt, and what runs now and next; older runs without token logs say so')
    # The phone-call transcript merges what you said (inbox) with the call log, and knows when a call has not rung yet.
    with TemporaryDirectory() as directory:
        run = Path(directory)
        (run / 'inbox.jsonl').write_text('\n'.join(json.dumps(n) for n in [
            {'kind': 'call', 'to': 'sam', 'name': 'K', 'written': 1}, {'kind': 'call_line', 'text': 'Hi Sam', 'written': 3}]) + '\n')
        (run / 'calls.jsonl').write_text('\n'.join(json.dumps(r) for r in [
            {'call': 0, 'event': 'ringing', 'label': 'Sam', 'written': 2}, {'call': 0, 'event': 'answered', 'label': 'Sam', 'text': 'Hello?', 'written': 2.5},
            {'call': 0, 'event': 'said', 'label': 'Sam', 'text': 'Oh hey.', 'written': 4}]) + '\n')
        call = latest_call(run)
        assert call['state'] == 'talking' and call['active'] and [r['event'] for r in call['events']] == ['ringing', 'answered', 'you', 'said']
        assert 'you: Hi Sam' in '\n'.join(t for _, t in call_lines(call, 60))
        with (run / 'inbox.jsonl').open('a') as inbox:
            inbox.write(json.dumps({'kind': 'call', 'to': 'sam', 'name': 'K', 'written': 9}) + '\n')
        assert latest_call(run)['state'] == 'waiting for the next event to ring'
        with (run / 'inbox.jsonl').open('a') as inbox:
            inbox.write(json.dumps({'kind': 'talk', 'to': 'sam', 'name': 'K', 'text': 'Hi Sam, got a minute?', 'written': 10}) + '\n')
        with (run / 'calls.jsonl').open('a') as log:
            log.write('\n'.join(json.dumps(r) for r in [{'call': 1, 'event': 'approaching', 'label': 'Sam', 'written': 11},
                {'call': 1, 'event': 'joined', 'label': 'Sam', 'written': 11.5}, {'call': 1, 'event': 'quiet', 'label': 'Sam', 'written': 12}]) + '\n')
        talk = latest_call(run)
        assert talk['in_person'] and talk['state'] == 'talking' and [r['event'] for r in talk['events']] == ['you', 'approaching', 'joined', 'quiet']
        shown = '\n'.join(t for _, t in call_lines(talk, 60))
        assert shown.startswith('talking with Sam') and 'you: Hi Sam, got a minute?' in shown and 'Sam stays quiet' in shown and 'walk away' in shown
    checks.append('the phone-call view merges your lines with the person\'s replies in order and shows a new call as waiting to ring; '
                  'a face-to-face talk shows your opening line, their silence and how to walk away')

    people = [{'id': 'priya', 'name': 'Priya'}, {'id': 'rohan', 'name': 'Rohan'}]
    for width in (40, 90):
        guide = help_lines({'people': people}, width)
        assert all(len(text) <= width for _, text in guide)
    text = '\n'.join(t for _, t in help_lines({'people': people}, 200))
    assert '@priya (Priya), @rohan (Rohan)' in text and text.index('People:') < text.index('Talk face to face')
    assert all(example in text for example in ('@priya Hi', '/call priya', '/send Kabir @priya a new classmate, 15', '/auto ', '/bye'))
    assert 'h help' in footer({'last': None}, True, None, 200)
    checks.append('key h opens a talk guide listing this run\'s people first, with examples for talking, calling, sending a '
                  'character, /auto and /bye, wrapped to the panel width; the footer shows h help')

    # Character panel, room map, relationship web and the menus' notes.
    from checks.check_living import world as living_world
    from devsim.lifetime import Lifetime
    from devsim.watch import map_lines, perform, person_card, web_lines
    from devsim import visit
    plain = load_world(engine)
    card = '\n'.join(t for _, t in person_card(plain, plain['people'][0], 40))
    assert 'feeling' in card and 'hormones' not in card and 'needs' not in card
    lived, policy = living_world(quiet=False, thoughts=True, creature=True)
    policy['hormones'] = {}
    policy['skills'] = {}
    Lifetime(lived, policy, scripted=True).run(.6)
    rich = load_world(lived)
    kid = next(p for p in rich['people'] if p['id'] == 'kid')
    shown = person_card(rich, kid, 40)
    text = '\n'.join(t for _, t in shown)
    assert all(part in text for part in ('hormones', 'stress', 'sleep pressure', 'dopamine', 'needs', 'hunger', 'people (closeness'))
    assert 'skills (stored, today)' in text or not lived.agent('kid').get('skills')
    assert 'skills' not in card
    assert all(len(t) <= 40 for _, t in shown) and len([1 for t in text.splitlines()[:11] if t.strip()]) >= 8  # the face on top
    drawn = '\n'.join(t for _, t in map_lines(rich, 'kid', 100))
    for n, person in enumerate(rich['people'], 1):
        assert drawn.count(f'{n} {person["name"]}') == 1
    assert '*' + str([p['id'] for p in rich['people']].index('kid') + 1) + ' Kid' in drawn and 'Biscuit the cat' in drawn
    web = '\n'.join(t for _, t in web_lines(rich, 'kid', 90, 22))
    ties = {lived.label(k) for k in lived.agent('kid')['relationships']}
    others = {p['name'] for p in rich['people']} - ties - {'Kid'}
    assert all(name in web for name in ties) and not any(f' {name} c' in web for name in others) and '[ Kid ]' in web
    checks.append('the character panel shows the face, feelings, and hormone and need bars only when those modules are on; the '
                  'room map lists every person once in their room with the selection marked; the web uses only the picked '
                  "person's own relationship records")
    with TemporaryDirectory() as directory:
        menu, typed = Path(directory) / 'menu', Path(directory) / 'typed'
        menu.mkdir(), typed.mkdir()
        perform(menu, 'Kanishk', 'talk', to='sam', text='Hi Sam')
        perform(menu, 'Kanishk', 'call', to='sam')
        perform(menu, 'Kanishk', 'send', character='Kabir', to='sam', who='a new classmate', age=15)
        perform(menu, 'Kanishk', 'auto', goal='make friends')
        perform(menu, 'Kanishk', 'end')
        for line in ('@sam Hi Sam', '/call sam', '/send Kabir @sam a new classmate, 15', '/auto make friends', '/bye'):
            visit.talk_line(typed, line, 'Kanishk')
        strip = lambda path: [{k: v for k, v in json.loads(l).items() if k != 'written'} for l in (path / 'inbox.jsonl').read_text().splitlines()]
        assert strip(menu) == strip(typed)
        perform(menu, 'Kanishk', 'send', character='Ravi', to='sam', who="Sam's cousin", age=19, relationship='Cousin')
        assert strip(menu)[-1]['relationship'] == 'cousin'
    checks.append('every menu choice writes exactly the inbox note its typed command writes; an introduction carries its relationship')

    result = {'passed': True, 'scope': 'engineering only; scripted fixture, no terminal', 'checks': checks}
    Path(__file__).with_name('results').joinpath('watch-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
