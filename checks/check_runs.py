"""Run control: discovery, liveness, start, stop and resume, without a model server (launch and model check stubbed)."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from devsim import runs
from devsim.engine import Engine, FACET_NAMES

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def tiny_world(path):
    e = Engine(seed=3)
    e.entity('ana', 'Ana', {'birth_day': -20 * 365.25})
    e.materialize('ana', dict.fromkeys(FACET_NAMES, 50), birth_day=-20 * 365.25)
    e.advance(0)
    e.state['runtime'] = {'policy_fingerprint': 'x', 'scripted': False, 'start_day': 0, 'current_day': 0}
    e.save(path)
    return e


def main():
    checks = []
    with TemporaryDirectory() as directory:
        root = Path(directory) / 'live'
        for name, status in (('done', 'completed'), ('halted', 'stopped'), ('broke', 'failed')):
            (root / name / 'run').mkdir(parents=True)
            (root / name / 'run' / 'summary.json').write_text(json.dumps({'status': status, 'final_day': 3.5}))
        (root / 'cut' / 'run').mkdir(parents=True)
        tiny_world(root / 'cut' / 'run' / 'world.json')
        (root / 'cut' / 'run' / 'requests.jsonl').write_text(json.dumps({'simulated_day': 1.25}) + '\n{"simul')
        found = {r['name']: r for r in runs.discover((root,))}
        assert {n: r['status'] for n, r in found.items()} == {'done': 'completed', 'halted': 'stopped', 'broke': 'failed', 'cut': 'interrupted'}
        assert found['cut']['day'] == 1.25 and found['cut']['calls'] == 1 and found['done']['day'] == 3.5
        checks.append('discovery reads status from summary.json (completed, stopped, failed), marks a run with no summary and no '
                      'process as interrupted, and reads the day from the last complete call without loading the world')

        live = root / 'going' / 'run'
        live.mkdir(parents=True)
        child = subprocess.Popen([sys.executable, '-c', 'import time\ntry:\n time.sleep(60)\nexcept KeyboardInterrupt:\n pass',
                                  'devsim.run_live', '--out', str(live)])
        try:
            assert runs.process_for(live) == child.pid and runs.info(live)['status'] == 'running'
            assert runs.stop(live, timeout=10, poll=.1) and child.wait(5) == 0 and runs.process_for(live) is None
        finally:
            child.kill()
        checks.append('a live run_live process is found by its --out directory; stop sends SIGINT and sees it exit')

        world, policy = Path(directory) / 'world.json', Path(directory) / 'policy.json'
        tiny_world(world)
        policy.write_text(json.dumps({'sampling': 'event_driven', 'opportunities': [], 'horizon_days': 5}))
        launched, checked = [], []
        class Fake:
            pid = 4242
        launch = lambda command, **kw: launched.append((command, kw)) or Fake()
        out = Path(directory) / 'runs' / 'fresh' / 'run'
        pid = runs.start(world, policy, out, 2, 60, 'http://x', extra={'sleep': {}}, check=checked.append, launch=launch)
        command, kw = launched[-1]
        assert pid == 4242 and checked == ['http://x'] and kw['start_new_session'] and command[command.index('--pace') + 1] == '60'
        assert json.loads((out.parent / 'policy.json').read_text())['sleep'] == {} and command[command.index('--policy') + 1].endswith('fresh/policy.json')
        assert json.loads((out.parent / 'pid.json').read_text())['pid'] == 4242 and not out.exists()
        (out).mkdir(parents=True)
        (out / 'world.json').write_text('{}')
        try:
            runs.start(world, policy, out, 2, check=checked.append, launch=launch)
            raise AssertionError('started into an existing run')
        except ValueError:
            pass
        checks.append('start checks the model server first, launches run_live in its own session with the chosen pace, adds '
                      'modules to a copied policy, records pid.json beside the run, and refuses a directory that already holds a run')

        old = root / 'done' / 'run'
        tiny_world(old / 'world.json')
        (old / 'policy-used.json').write_text(policy.read_text())
        edits = [{'to': 'ana', 'changes': {'facet:N1': 80, 'mood': .3}, 'name': 'Kanishk'}]
        pid, fresh = runs.resume(old, 4, 1, 'http://x', edits=edits, check=checked.append, launch=launch)
        command, _ = launched[-1]
        staged = Path(command[command.index('--world') + 1])
        assert fresh == root / 'done-r2' / 'run' and staged == root / 'done-r2' / 'start-world.json'
        restored = Engine.load(staged)
        assert restored.agent('ana')['facets']['N1'] == 80 and len(restored.state['runtime']['researcher_edits']) == 2
        assert Engine.load(old / 'world.json').agent('ana')['facets']['N1'] == 50, 'the old checkpoint was edited'
        checks.append('resume starts a fresh sibling (NAME-r2) from the checkpoint and its archived policy; changes made while '
                      'stopped are applied to a staged copy and logged, and the old checkpoint is never edited')

    result = {'passed': True, 'scope': 'run control engineering checks; run_live itself is stubbed', 'checks': checks}
    RESULTS_DIR.joinpath('runs-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
