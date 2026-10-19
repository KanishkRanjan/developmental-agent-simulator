"""Run control for the control panel: find simulations, start, stop and resume them. No terminal needed.

A run started here is `python3 -m devsim.run_live` in its own session (it keeps going when the panel closes), with
`run.log` and `pid.json` beside its run directory, as the earlier live runs were laid out (`runs/live/NAME/run`).
Stopping sends SIGINT: run_live records `status: stopped` and the last checkpoint stays valid. Resuming never edits
the old directory: it starts a fresh sibling from the checkpoint and its archived policy (docs/RESUME.md).
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ROOTS = (ROOT / 'runs' / 'live', ROOT / 'runs' / 'scripted', ROOT / 'work' / 'runs')
DEFAULT_API = 'http://127.0.0.1:8081'


def run_dir(path):
    """The directory holding world.json for a run given as NAME, NAME/run or a path."""
    path = Path(path)
    return path / 'run' if (path / 'run').is_dir() else path


def _tail(path, size=65536):
    try:
        with path.open('rb') as stream:
            stream.seek(max(0, path.stat().st_size - size))
            return stream.read().decode('utf8', 'replace').splitlines()
    except OSError:
        return []


def _lines(path):
    try:
        with path.open('rb') as stream:
            return sum(chunk.count(b'\n') for chunk in iter(lambda: stream.read(1 << 20), b''))
    except OSError:
        return 0


def _cmdline(pid):
    try:
        return Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    except OSError:
        return []


def process_for(run):
    """The pid of a live run_live writing to this run directory, or None."""
    run = run_dir(run).resolve()
    record = run.parent / 'pid.json'
    candidates = []
    if record.exists():
        try:
            candidates.append(json.loads(record.read_text())['pid'])
        except (ValueError, KeyError):
            pass
    candidates += [int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit()]
    for pid in candidates:
        args = [a.decode('utf8', 'replace') for a in _cmdline(pid)]
        if 'devsim.run_live' in args and '--out' in args:
            out = Path(args[args.index('--out') + 1])
            out = (Path(_cwd(pid)) / out if not out.is_absolute() else out).resolve()
            if out == run:
                return pid
    return None


def _cwd(pid):
    try:
        return os.readlink(f'/proc/{pid}/cwd')
    except OSError:
        return str(ROOT)


def info(path):
    """What the panel shows about one run, read without loading its world."""
    run = run_dir(path)
    summary = {}
    if (run / 'summary.json').exists():
        try:
            summary = json.loads((run / 'summary.json').read_text())
        except ValueError:
            pass
    pid = process_for(run)
    day = summary.get('final_day')
    for line in reversed(_tail(run / 'requests.jsonl')):
        try:
            day = json.loads(line).get('simulated_day', day)
            break
        except ValueError:
            continue
    policy = {}
    for name in ('policy-used.json',):
        try:
            policy = json.loads((run / name).read_text())
        except (OSError, ValueError):
            pass
    status = 'running' if pid else summary.get('status') or ('not started' if not (run / 'world.json').exists() else 'interrupted')
    name = run.parent.name if run.name == 'run' else run.name
    return {'name': name, 'path': str(run), 'status': status, 'pid': pid, 'day': day, 'calls': _lines(run / 'requests.jsonl'),
            'horizon': policy.get('horizon_days'), 'pace': summary.get('pace'), 'error': summary.get('error'),
            'modified': max((p.stat().st_mtime for p in (run / 'world.json', run / 'requests.jsonl', run / 'summary.json') if p.exists()), default=0)}


def discover(roots=ROOTS):
    """Every run under the roots, newest first."""
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            run = run_dir(child)
            if (run / 'world.json').exists() or (run / 'summary.json').exists() or (child / 'pid.json').exists():
                found.append(info(child))
    return sorted(found, key=lambda r: -r['modified'])


def designs(root=ROOT / 'work'):
    """Compiled worlds ready to run: directories holding initial.json and policy.json."""
    found = []
    for path in sorted(root.rglob('initial.json')):
        if (path.parent / 'policy.json').exists() and 'staging' not in path.parts:
            try:
                horizon = json.loads((path.parent / 'policy.json').read_text()).get('horizon_days')
            except ValueError:
                horizon = None
            found.append({'name': str(path.parent.relative_to(root)), 'path': str(path.parent), 'horizon': horizon,
                          'modified': path.stat().st_mtime})
    return sorted(found, key=lambda d: -d['modified'])


def check_model(api=DEFAULT_API):
    """The served model id, or raise: a run is never started against a missing or wrong server."""
    from .run_live import select_model
    return select_model(api)[0]


def start(world, policy, out, until, pace=1.0, api=DEFAULT_API, extra=None, check=check_model, launch=subprocess.Popen):
    """Launch run_live detached. extra adds policy modules (e.g. {'sleep': {}}) into a copy beside the run.
    Returns the pid. The output directory must not exist yet (earlier evidence is never overwritten)."""
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError(f'{out} already holds a run; choose a new name')
    check(api)
    home = out.parent
    home.mkdir(parents=True, exist_ok=True)
    policy_path = Path(policy)
    if extra:
        merged = {**json.loads(policy_path.read_text()), **extra}
        policy_path = home / 'policy.json'
        policy_path.write_text(json.dumps(merged, indent=2) + '\n')
    command = [sys.executable, '-m', 'devsim.run_live', '--world', str(Path(world).resolve()), '--policy', str(policy_path.resolve()),
               '--until-day', f'{float(until):g}', '--out', str(out.resolve()), '--api', api, '--pace', f'{float(pace):g}']
    log = (home / 'run.log').open('a')
    process = launch(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    (home / 'pid.json').write_text(json.dumps({'pid': process.pid, 'out': str(out.resolve()), 'command': command,
                                               'started': time.time()}, indent=2) + '\n')
    return process.pid


def stop(run, timeout=60.0, poll=0.5):
    """SIGINT the run's process and wait for it to exit. True when it stopped (or was not running)."""
    pid = process_for(run)
    if pid is None:
        return True
    os.kill(pid, signal.SIGINT)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not Path(f'/proc/{pid}').exists() or _zombie(pid):
            return True
        time.sleep(poll)
    return False


def _zombie(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().split()[2] == 'Z'
    except (OSError, IndexError):
        return True


def next_name(run):
    """A fresh sibling name for a resumed run: NAME-r2, NAME-r3, …"""
    run = run_dir(run)
    home = run.parent if run.name == 'run' else run
    base = home.name.split('-r')[0] if '-r' in home.name and home.name.rsplit('-r', 1)[1].isdigit() else home.name
    n = 2
    while (home.parent / f'{base}-r{n}').exists():
        n += 1
    return home.parent / f'{base}-r{n}' / 'run'


def resume(run, until, pace=1.0, api=DEFAULT_API, edits=None, out=None, **kw):
    """Continue a stopped or finished run in a fresh directory from its checkpoint and archived policy.
    edits (visit.apply_edit notes) are applied to a staged copy of the checkpoint first, and logged there."""
    run = run_dir(run)
    if process_for(run):
        raise ValueError('That run is still going; stop it first')
    out = Path(out) if out else next_name(run)
    world = run / 'world.json'
    if edits:
        from .engine import Engine
        from .visit import apply_edit
        staged = out.parent / 'start-world.json'  # beside the new run: what it started from, with the changes logged
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(world, staged)
        engine = Engine.load(staged)
        for note in edits:
            apply_edit(engine, note)
        engine.save(staged)
        world = staged
    return start(world, run / 'policy-used.json', out, until, pace, api, **kw), out
