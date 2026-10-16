"""Researcher interviews: frozen diagnostic copies and explicit in-world questions.

A diagnostic interview questions a deep copy of the world. The run itself gains
no memory, recall, mood, relationship or checkpoint change, and the person does
not remember being asked. An in-world interview is an explicit researcher
intervention at the current simulated instant: each question is a received
event, each reply a committed action, and both stay in the person's history.

In either mode an answer is a generated account. It is not access to the true
cause of the person's behavior, and spoken claims never become world facts.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import time

from . import household
from .engine import Engine, number, validated_json

ACCOUNT_POLICY = 'generated_account_not_causal_access'


def _interviewable(engine, owner):
    agent = engine.agent(owner)
    if not agent['alive']:
        raise ValueError('A dead agent cannot be interviewed')
    if (engine.day - agent['birth_day']) / 365.25 < 2:
        raise ValueError('An infant cannot give a verbal interview')


def _questions(questions):
    if not questions or not all(isinstance(q, str) and q.strip() for q in questions):
        raise ValueError('An interview needs at least one nonempty question')
    return [q.strip() for q in questions]


def state_digest(engine):
    return sha256(json.dumps(engine.state, sort_keys=True, allow_nan=False).encode()).hexdigest()


def diagnostic(engine, owners, questions, *, api, model):
    """Ask every question of every agent on one frozen copy; return transcript records."""
    questions = _questions(questions)
    if not owners or len(set(owners)) != len(owners):
        raise ValueError('Name each interviewed agent once')
    for owner in owners:
        _interviewable(engine, owner)
    before = state_digest(engine)
    frozen = deepcopy(engine)
    system = ('A researcher outside the simulated world asks this fictional agent a diagnostic question. '
              'The agent will not remember this exchange and it changes nothing in their life. '
              'Answer in the first person as the agent, expressing the supplied behavioral tendencies, mood, '
              'memories, beliefs and relationships. Use only the agent context for personal knowledge; if the agent '
              'would not know or remember something, say so. An explanation of your own behavior is your own account '
              'and may be incomplete or mistaken. Return JSON with answer (string), confidence (0 to 1, how sure the '
              'agent feels about the answer), and memory_ids (supplied memory event ids the answer draws on; may be empty).')
    if engine.state['config'].get('expression', {}).get('age_appropriate_actions', False):
        system += ' Use age-appropriate language and only lived or received knowledge.'
    records = []
    for owner in owners:
        for question in questions:
            context = frozen.context(owner, question)
            context.update(task='diagnostic_interview', researcher_question=question)
            allowed = {m['event'] for m in context['memories']}

            def validate(result):
                if not isinstance(result.get('answer'), str) or not result['answer'].strip():
                    raise ValueError('An interview answer needs text')
                number(result.get('confidence'), 0, 1, 'answer confidence')
                ids = result.get('memory_ids')
                if not isinstance(ids, list) or any(m not in allowed for m in ids):
                    raise ValueError('Answer cites a memory unavailable to this agent')
            result = validated_json(system, context, validate, api, model, 500)
            records.append({'mode': 'diagnostic', 'owner': owner, 'day': engine.day, 'question': question,
                            'answer': result['answer'], 'confidence': result['confidence'],
                            'memory_ids': result['memory_ids'], 'model': model, 'policy': ACCOUNT_POLICY,
                            'world_state_sha256': before, 'context': context})
    if state_digest(frozen) != before or state_digest(engine) != before:
        raise RuntimeError('A diagnostic interview changed world state')
    return records


def in_world(controller, owner, interviewer, questions, interview_id):
    """Explicit intervention at the current instant, atomic across all questions.

    shortcut: the exchange takes no simulated time and is private (no calendar
    reservation, no household overhearing); add both if interviews join policies.
    """
    engine = controller.engine
    questions = _questions(questions)
    _interviewable(engine, owner)
    if interviewer == owner or interviewer not in engine.state['entities']:
        raise ValueError('The interviewer must be a distinct committed identity')
    if not isinstance(interview_id, str) or not interview_id.strip() or ':' in interview_id:
        raise ValueError('Interview id must be a nonempty string without colons')
    prefix = '@interview:' + interview_id
    if any(e['id'].startswith(prefix + ':') for e in engine.state['events'] + engine.state['pending']):
        raise ValueError('Duplicate interview id')
    if 'household' in engine.state['config'] and not household.available(engine, owner):
        raise ValueError('This person is not available for an interview now')
    hearer = interviewer if interviewer in engine.state['agents'] and engine.agent(interviewer)['alive'] else None
    asker, name = engine.state['entities'][interviewer]['name'], engine.state['entities'][owner]['name']
    menu = [{'id': 'answer', 'label': 'Answer the question in your own words.'},
            {'id': 'decline', 'label': 'Decline to answer.'}]
    backup, turns = deepcopy(engine.state), []
    try:
        for i, question in enumerate(questions):
            asked, action, replied = (f'{prefix}:{i}:{part}' for part in ('question', 'answer', 'reply'))
            observations = {owner: {'text': f'{asker} asked me: {question}', 'source': interviewer,
                                    'kind': 'direct', 'encountered': [interviewer]}}
            if hearer:
                observations[hearer] = {'text': f'I asked {name}: {question}', 'source': 'self',
                                        'kind': 'direct', 'encountered': [owner]}
            household.deliver(controller, asked, 'An interview question is asked in person.', observations)
            situation = (f'{asker} is interviewing you in person and just asked: "{question}" '
                         'Answer in your own words or decline. Use only what you personally know and remember. '
                         'An explanation of your own behavior is your own account and may be incomplete.')
            controller._before_decision(owner, situation)
            if not controller.scripted and 'situational_personality' in controller.policy:
                engine.generate_signatures(owner, api=controller.api, model=controller.model)
                engine.prepare_situation(owner, situation, f'{prefix}:{i}:situation', cues=['social'],
                    half_life_days=controller.policy['situational_personality'].get('recovery_half_life_days', 1),
                    api=controller.api, model=controller.model)
            if controller.scripted:
                proposal = {'owner': owner, 'day': engine.day, 'context': engine.context(owner, situation, ['social'], menu),
                            'decision': {'action_id': 'answer', 'action': 'Answer the question.',
                                         'speech': 'I would like to think about that before I say more.',
                                         'goal_id': None, 'plan': [], 'memory_ids': []}}
            else:
                proposal = engine.propose(owner, situation, cues=['social'], options=menu,
                                          api=controller.api, model=controller.model)
            engine.commit_action(action, proposal)
            decision = proposal['decision']
            said = ('said: ' + decision['speech'] if decision['speech'].strip() else
                    'declined to answer.' if decision['action_id'] == 'decline' else 'did not say anything.')
            observations = {owner: {'text': 'I ' + said, 'source': 'self', 'kind': 'direct', 'encountered': [interviewer]}}
            if hearer:
                observations[hearer] = {'text': f'{name} {said}', 'source': owner, 'kind': 'direct',
                                        'encountered': [owner], 'provenance': replied}
            household.deliver(controller, replied, 'An interview reply is observed; spoken claims are not world facts.',
                              observations, action)
            if not controller.scripted and controller.policy.get('consolidation_batch_size'):
                for person in observations:
                    engine.consolidate(person, api=controller.api, model=controller.model,
                                       batch_size=controller.policy['consolidation_batch_size'])
            turns.append({'question': question, 'question_event': asked, 'action': action, 'reply_event': replied,
                          'choice': decision['action_id'], 'speech': decision['speech'],
                          'memory_ids': decision['memory_ids']})
    except Exception:
        engine.state = backup
        engine.world = controller._world_from_state(backup)
        raise
    return {'mode': 'in_world', 'id': interview_id, 'owner': owner, 'interviewer': interviewer, 'day': engine.day,
            'policy': ACCOUNT_POLICY, 'provider': 'scripted_engineering_fixture' if controller.scripted else 'local_model_api',
            'turns': turns}


def main():
    from . import engine as engine_module
    from .lifetime import Lifetime
    from .run_live import recorder, select_model
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=('diagnostic', 'in-world'))
    parser.add_argument('world', type=Path, help='Checkpoint to interview; it is never modified')
    parser.add_argument('--agent', action='append', required=True, help='Repeat for a batch diagnostic interview')
    parser.add_argument('--question', action='append', required=True, help='Repeat for several questions')
    parser.add_argument('--out', type=Path, required=True, help='Fresh output directory')
    parser.add_argument('--policy', type=Path, help='in-world: the checkpoint\'s own archived policy')
    parser.add_argument('--interviewer', help='in-world: committed identity id asking the questions')
    parser.add_argument('--id', dest='interview_id', help='in-world: unique interview id')
    parser.add_argument('--scripted', action='store_true', help='in-world: deterministic engineering provider')
    parser.add_argument('--api', default='http://127.0.0.1:18081')
    args = parser.parse_args()
    in_world_mode = args.mode == 'in-world'
    if in_world_mode and not (args.policy and args.interviewer and args.interview_id and len(args.agent) == 1):
        parser.error('in-world needs --policy, --interviewer, --id and exactly one --agent')
    if args.scripted and not in_world_mode:
        parser.error('Diagnostic interviews always use the local model')
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a fresh output directory')
    args.out.mkdir(parents=True, exist_ok=True)
    sources = sorted(Path(__file__).parent.glob('*.py'))
    (args.out / 'source-hashes.json').write_text(json.dumps(
        {str(p.resolve()): sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2) + '\n')
    model = 'scripted'
    if not args.scripted:
        model, models = select_model(args.api)
        (args.out / 'server-model.json').write_text(json.dumps(models, indent=2) + '\n')
    engine = Engine.load(args.world)
    counts, started = {}, time.monotonic()
    original = engine_module.request_json
    engine_module.request_json = recorder(original, args.out / 'requests.jsonl', counts)
    try:
        if in_world_mode:
            policy = json.loads(args.policy.read_text())
            controller = Lifetime(engine, policy, scripted=args.scripted, api=args.api, model=model)
            result = in_world(controller, args.agent[0], args.interviewer, args.question, args.interview_id)
            engine.save(args.out / 'world.json')
            engine.save(args.out / 'world.sqlite')
        else:
            result = diagnostic(engine, args.agent, args.question, api=args.api, model=model)
    finally:
        engine_module.request_json = original
    (args.out / 'transcript.json').write_text(json.dumps(result, indent=2) + '\n')
    summary = {'mode': args.mode, 'source_checkpoint': str(args.world), 'model': model, 'requests': counts,
               'seconds': round(time.monotonic() - started, 3), 'policy': ACCOUNT_POLICY}
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
