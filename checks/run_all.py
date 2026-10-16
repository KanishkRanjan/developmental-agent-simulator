"""Run every engineering check suite and the core demo; print one line per suite.

Usage from the repository root:  python -m checks.run_all [--skip graphiti ...]
check_graphiti needs the local Graphiti config (services/graphiti-local/README.md).
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--skip', nargs='*', default=[], help='Suite names to skip, such as graphiti')
    args = parser.parse_args()
    suites = sorted(p.stem.removeprefix('check_') for p in Path(__file__).parent.glob('check_*.py'))
    failed, named = [], 0
    for suite in suites:
        if suite in args.skip:
            print(f'{suite:<14} skipped')
            continue
        start = time.monotonic()
        result = subprocess.run([sys.executable, '-m', f'checks.check_{suite}'], cwd=ROOT, capture_output=True, text=True)
        seconds = time.monotonic() - start
        if result.returncode:
            failed.append(suite)
            print(f'{suite:<14} FAILED ({seconds:.1f}s): {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "no stderr"}')
            continue
        record = json.loads(RESULTS_DIR.joinpath(f'{suite.replace("_", "-")}-engineering-checks.json').read_text())
        named += len(record['checks'])
        print(f'{suite:<14} passed {len(record["checks"]):>3} named checks ({seconds:.1f}s)')
    with TemporaryDirectory() as directory:
        demo = subprocess.run([sys.executable, '-m', 'devsim.demo', '--out', directory], cwd=ROOT, capture_output=True, text=True)
        core = json.loads(Path(directory, 'engineering-checks.json').read_text()) if not demo.returncode else None
    if core and core['passed']:
        print(f'{"core demo":<14} passed {len(core["checks"]):>3} core checks')
    else:
        failed.append('core demo')
        print(f'{"core demo":<14} FAILED')
    print(f'\n{named} named checks passed; failed: {", ".join(failed) or "none"}')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
