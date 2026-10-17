"""Researcher cockpit checks: perspective boundaries, accessibility, read-only loading, live files, safe page, loopback server."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

from checks.check_report import world
from devsim import cockpit
from devsim.engine import Engine


def main():
    checks = []
    _, engine = world()
    with TemporaryDirectory() as directory:
        run = Path(directory)
        engine.save(run / 'world.json')
        rows = [{'purpose': 'action', 'agent': 'sam', 'simulated_day': 3.0, 'seconds': 1.0, 'context': {},
                 'response': {'action_id': 'hi', 'speech': 'Hello </script><script>alert(1)</script>'}}]
        (run / 'requests.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows) + '{"purpose": "act')
        raw = (run / 'world.json').read_bytes()
        data = cockpit.snapshot(run)
        assert (run / 'world.json').read_bytes() == raw and len(data['requests']) == 1
        checks += ['loading a run is read-only and skips a half-written last model-call line']

        dana, sam = data['people']['dana'], data['people']['sam']
        own = {o.event_id for o in engine.world.observations['dana']}
        assert {m['event'] for m in dana['memories']} <= own
        assert all(a['id'] in {x['id'] for x in engine.state['actions'] if x['owner'] == 'dana'} for a in dana['actions'])
        private = [o.text for o in engine.world.observations['sam'] if o.event_id not in own]
        assert private and not any(text in json.dumps(dana) for text in private)
        assert dana['scope'] == cockpit.AGENT_SCOPE and data['researcher']['scope'] == cockpit.RESEARCHER_SCOPE
        assert len(data['researcher']['events']) == len(engine.state['events']) and data['researcher']['actions'] == engine.state['actions']
        assert sam['actions'] and all(a['outcome'] for a in sam['actions'])
        checks += ['an agent perspective holds only that person\'s received memories and own actions; another person\'s private text never appears',
                   'the researcher view holds every raw event and action, and both views carry their scope label']

        faded = deepcopy(engine)
        events = [o.event_id for o in faded.world.observations['sam']]
        gist, lost = events[0], events[1]
        for event_id in (gist, lost):
            meta = faded.agent('sam')['memory_meta'][event_id]
            meta.update(stability_days=1e-6, last_recall_day=0.0)
            meta.pop('summary', None)
        faded.agent('sam')['memory_meta'][gist]['summary'] = 'Only the gist remains.'
        faded.agent('sam')['beliefs'] = {}
        faded.save(run / 'world.json')
        memories = {m['event']: m for m in cockpit.snapshot(run)['people']['sam']['memories']}
        assert memories[gist]['text'] == 'Only the gist remains.' and memories[gist]['representation'] == 'subjective_gist'
        assert lost not in memories
        checks.append('faded memories show only their encoded gist, and memories with no accessible representation are omitted')

        page = cockpit.render(data)
        assert page.count('</script>') == 1 and '<\\/script><script>alert(1)' in page
        checks.append('embedded run text cannot close the page script')

        (run / 'world.json').unlink()
        waiting = cockpit.snapshot(run)
        assert not waiting['world_available'] and 'people' not in waiting and waiting['requests']
        checks.append('before a live run writes its checkpoint, the cockpit shows the streaming model-call timeline')

        engine.save(run / 'world.json')
        live = cockpit.make_server(run, 0)
        threading.Thread(target=live.serve_forever, daemon=True).start()
        host, port = live.server_address
        assert host == '127.0.0.1'
        assert 'const LIVE = true' in urlopen(f'http://127.0.0.1:{port}/').read().decode()
        assert json.loads(urlopen(f'http://127.0.0.1:{port}/data.json').read())['day'] == engine.day
        try:
            urlopen(f'http://127.0.0.1:{port}/../world.json')
            raise AssertionError('server exposed another path')
        except HTTPError as exc:
            assert exc.code == 404
        # The live page can talk to people through the run's inbox; nothing else may post to it.
        from urllib.request import Request
        base = f'http://127.0.0.1:{port}'
        def post(body, kind='application/json', origin=None):
            headers = {'Content-Type': kind, **({'Origin': origin} if origin else {})}
            try:
                with urlopen(Request(base + '/talk', data=json.dumps(body).encode(), headers=headers)) as response:
                    return response.status, json.loads(response.read())
            except HTTPError as exc:
                return exc.code, json.loads(exc.read() or b'{}')
        assert 'TALK = true' in urlopen(base + '/').read().decode() and json.loads(urlopen(base + '/talk.json').read()) is None
        # Typed lines, read like the watcher's t key.
        assert post({'text': '@sam Hi Sam.', 'name': 'Kanishk'}, origin=base) == (200, {'ok': True, 'done': 'walking over to sam'})
        assert post({'text': 'How are you?'})[1]['done'] == 'said' and post({'text': '/auto cheer Sam up'})[0] == 200
        assert post({'text': '/send Kabir @sam a new classmate, 15', 'name': 'Kanishk'})[0] == 200
        assert post({'text': '/call sam'})[0] == 200 and post({'text': '/bye'})[0] == 200
        notes = [json.loads(line) for line in (run / 'inbox.jsonl').read_text().splitlines()]
        assert [n['kind'] for n in notes] == ['talk', 'call_line', 'auto', 'talk', 'call', 'hangup']
        assert notes[0]['to'] == 'sam' and notes[0]['text'] == 'Hi Sam.' and notes[2]['goal'] == 'cheer Sam up'
        assert (notes[3]['as'], notes[3]['to'], notes[3]['who'], notes[3]['age']) == ('Kabir', 'sam', 'a new classmate', 15)
        assert json.loads(urlopen(base + '/talk.json').read())['label'] == 'sam'
        assert post({'text': '@sam x'}, kind='text/plain')[0] == 403
        assert post({'text': '@sam x'}, origin='http://evil.example')[0] == 403
        for bad in ('', '/delete', '/send Kabir', '/auto', 'x' * 700):
            code, reply = post({'text': bad})
            assert code == 400 and reply['error'], bad
        assert len((run / 'inbox.jsonl').read_text().splitlines()) == 6, 'refused requests must write nothing'
        (run / 'calls.jsonl').write_text(json.dumps({'call': 0, 'event': 'ended', 'written': 9e9}) + '\n')
        assert post({'text': 'Anyone?'})[1]['done'].startswith('said into the most recent group conversation')
        live.shutdown()
        checkpoint_only = cockpit.make_server(run / 'world.json', 0)
        threading.Thread(target=checkpoint_only.serve_forever, daemon=True).start()
        other = f'http://127.0.0.1:{checkpoint_only.server_address[1]}'
        assert 'TALK = false' in urlopen(other + '/').read().decode()
        try:
            urlopen(Request(other + '/talk', data=b'{}', headers={'Content-Type': 'application/json'}))
            raise AssertionError('a checkpoint-file cockpit accepted a talk request')
        except HTTPError as exc:
            assert exc.code == 404
        checkpoint_only.shutdown()
        assert 'TALK = false' in cockpit.render(data)
        checks.append('the live server binds to loopback and serves only the page and its data')
        checks.append('the live page has one talk box read like the watcher\'s t key (@name starts a talk, plain text continues, '
                      '/call, /send with who and age, /auto, /bye) writing to the run inbox; requests that are not JSON from the '
                      'page\'s own origin, or are invalid, are refused and write nothing; static exports and checkpoint files cannot talk')

    result = {'passed': True, 'scope': 'engineering only; scripted fixture, no browser', 'checks': checks}
    Path(__file__).with_name('results').joinpath('cockpit-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
