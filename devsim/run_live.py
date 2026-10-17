"""Run the existing lifetime controller with the local model and retain a trace."""
import argparse
from datetime import datetime, timezone
import json
from hashlib import sha256
from pathlib import Path
import time
from urllib.request import urlopen

from . import engine as engine_module
from .engine import Engine
from .lifetime import Lifetime


def select_model(api):
    """The one served HauhauCS 27B model; no smaller or unrelated fallback."""
    with urlopen(api.rstrip('/') + '/v1/models', timeout=10) as response:
        models = json.load(response)
    selected=[entry for entry in models['data'] if 'hauhaucs' in entry['id'].lower() and
              26e9 <= entry.get('meta',{}).get('n_params',0) <= 29e9]
    if len(selected)!=1:
        raise ValueError('Expected exactly one served HauhauCS 27B model; no smaller or unrelated fallback is permitted')
    return selected[0]['id'], models


def recorder(request_json, path, counts):
    """Wrap the model transport so every request/response is appended to path."""
    def recorded(system, context, api, model, max_tokens=600):
        start = time.monotonic()
        purpose = ({'ground_goal_plan':'goal_planning','semantic_recall':'semantic_recall','reflect_received_evidence':'reflection',
                    'expand_constrained_background':'background','generate_biography':'background',
                    'expand_retrieval_query':'retrieval_query','diagnostic_interview':'interview','author_scenario':'authoring',
                    'report_outline':'report','report_section':'report',
                    'review_scenario':'review'}.get(context.get('task')) or
                   ('signatures' if context.get('task') == 'generate_situational_signatures' else
                   'situation' if context.get('task') == 'construe_situation' else
                   'consolidation' if 'episodes_to_consolidate' in context else
                   'appraisal' if 'new_observation' in context else 'action'))
        agent, day = context.get('identity', {}).get('id'), context.get('simulated_day')
        # The watcher shows the call in flight; written atomically and removed when the call ends.
        current, staged = path.with_name('current.json'), path.with_name('current.json.tmp')
        staged.write_text(json.dumps({'purpose': purpose, 'agent': agent, 'simulated_day': day, 'started': time.time(),
                                      'context': context}, allow_nan=False))
        staged.replace(current)
        try:
            result = request_json(system, context, api, model, max_tokens)
        finally:
            current.unlink(missing_ok=True)
        counts[purpose] = counts.get(purpose, 0) + 1
        record = {'purpose': purpose, 'model': model, 'simulated_day': day,
                  'agent': agent, 'seconds': round(time.monotonic() - start, 3), 'finished': time.time(),
                  'usage': dict(engine_module.LAST_USAGE), 'context': context, 'response': result}
        with path.open('a') as output:
            output.write(json.dumps(record, allow_nan=False) + '\n')
        print(json.dumps({'purpose': purpose, 'agent': agent, 'day': day, 'seconds': record['seconds'],
                          'tokens': record['usage'].get('completion_tokens')}), flush=True)
        return result
    return recorded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--until-day', type=float, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--api', default='http://127.0.0.1:18081')
    parser.add_argument('--beyond-horizon', action='store_true', help='Allow running past the policy\'s horizon_days')
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text())
    # The overnight environment run went to day 315 of a 62-day scenario; nothing after day 62 was authored.
    # 1e-3 tolerance: the compiler prints the horizon rounded to three decimals.
    if 'horizon_days' in policy and args.until_day > policy['horizon_days'] + 1e-3 and not args.beyond_horizon:
        raise ValueError(f'--until-day {args.until_day} is past the scenario horizon ({policy["horizon_days"]:.1f} days); '
                         'extend the scenario or pass --beyond-horizon')
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError('Use a fresh output directory; existing run evidence must be preserved')
    args.out.mkdir(parents=True, exist_ok=True)
    sources = list(Path(__file__).parent.glob('*.py'))
    (args.out / 'source-hashes.json').write_text(json.dumps(
        {str(p.resolve()):sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2) + '\n')
    model, models = select_model(args.api)
    (args.out / 'server-model.json').write_text(json.dumps(models, indent=2) + '\n')
    engine = Engine.load(args.world)
    (args.out / 'policy-used.json').write_text(json.dumps(policy, indent=2) + '\n')
    initial_actions = len(engine.state['actions'])
    request_json = engine_module.request_json
    counts = {'action': 0, 'appraisal': 0, 'consolidation': 0, 'signatures': 0, 'situation': 0,
              'semantic_recall':0, 'reflection':0, 'background':0,'retrieval_query':0,'goal_planning':0}
    engine_module.request_json = recorder(request_json, args.out / 'requests.jsonl', counts)
    started = time.monotonic()
    summary = {'model': model, 'started_utc': datetime.now(timezone.utc).isoformat(), 'provider': 'local_model_api',
               'sampling': policy.get('sampling', 'legacy_discrete'), 'personality_expression': 'behavioral_language_v1'}
    try:
        controller = Lifetime(engine, policy, api=args.api, model=model)
        controller.inbox = args.out / 'inbox.jsonl'  # devsim.visit / watcher key t: a researcher joins a conversation
        controller.run(args.until_day, args.out / 'world.json')
        summary['status'] = 'completed'
    except BaseException as exc:  # Ctrl-C (to resume later) is recorded as stopped, not left blank
        summary.update(status='stopped' if isinstance(exc, KeyboardInterrupt) else 'failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        summary.update(seconds=round(time.monotonic() - started, 3), requests=counts,
                       final_day=engine.day, ticks=engine.state.get('runtime', {}).get('tick', 0),
                       new_actions=len(engine.state['actions']) - initial_actions)
        (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        engine_module.request_json = request_json
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
