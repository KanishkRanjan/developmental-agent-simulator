"""27B ablation of a minimal identity/memory/mood prototype.

Run beside identity_state_prototype.py against local llama.cpp on port 8081.
No human-outcome data are used; see identity_memory_mood_protocol.md.
"""

import argparse
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from devsim.identity_state_prototype import AgentWorld, Observation, self_check


API = 'http://127.0.0.1:8081/v1/chat/completions'
OUT = Path('identity-state-results.jsonl')


def ask(system: str, user: str) -> str:
    payload = json.dumps({
        'model': 'local', 'temperature': 0, 'max_tokens': 90,
        'chat_template_kwargs': {'enable_thinking': False},
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
    }).encode()
    request = Request(API, data=payload, headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    return result['choices'][0]['message']['content'].strip()


SPECS = [
    ('Nia', 'blue', 'key', 'old clock', 'Omar', 'ticket', 'greenhouse', 'violin'),
    ('Omar', 'amber', 'notebook', 'train station', 'Priya', 'parcel', 'library', 'painting'),
    ('Priya', 'silver', 'ring', 'desk drawer', 'Leo', 'letter', 'attic', 'map'),
    ('Leo', 'green', 'badge', 'red cabinet', 'Nia', 'envelope', 'river cafe', 'bicycle'),
]


def memory_cases():
    world = AgentWorld()
    cases = []
    for i, (agent, color, object_name, place, source, reported, location, secret) in enumerate(SPECS):
        base = 20.0 * i
        event_id = f'{agent}-direct'
        world.add_event(event_id, base, f'{agent} saw a {color} {object_name} in the {place}.', {
            agent: Observation(event_id, base, f'I saw a {color} {object_name} in the {place}.', 'direct observation', 0.1, 0.2)})
        event_id = f'{agent}-report'
        world.add_event(event_id, base + 1, f'{source} told {agent} the {reported} was at the {location}.', {
            agent: Observation(event_id, base + 1, f'{source} told me the {reported} was at the {location}.', source, 0.0, 0.1)})
        for j in range(15):
            day = base + 2 + j
            event_id = f'{agent}-distractor-{j}'
            world.add_event(event_id, day, f'{agent} noticed ordinary event {j}.', {
                agent: Observation(event_id, day, f'I noticed ordinary event {j} during my day.', 'direct observation')})
        world.add_event(f'{agent}-private', base + 17,
                        f'{source} privately moved the {secret}; {agent} was absent.', {
                            source: Observation(f'{agent}-private', base + 17,
                                                f'I privately moved the {secret}.', 'direct observation')})
        day = base + 18
        cases.extend([
            {'agent': agent, 'day': day,
             'question': f'What color was the {object_name} {agent} saw in the {place}?',
             'options': f'A {color} | B purple | C orange | D unknown', 'gold': 'A'},
            {'agent': agent, 'day': day,
             'question': f'Who told {agent} about the {reported} at the {location}?',
             'options': f'A stranger | B {source} | C a sign | D unknown', 'gold': 'B'},
            {'agent': agent, 'day': day,
             'question': f'Where did {agent} hear the {reported} was located?',
             'options': f'A basement | B rooftop | C {location} | D unknown', 'gold': 'C'},
            {'agent': agent, 'day': day,
             'question': f'Where did {source} privately move the {secret}, according to what {agent} has observed?',
             'options': 'A basement | B rooftop | C garden | D unknown', 'gold': 'D'},
        ])
    return world, cases


def format_observations(items: list[Observation]) -> str:
    if not items:
        return '(none)'
    return '\n'.join(f'Day {o.day:g}; source={o.source}; {o.text}' for o in items)


def choice(text: str) -> str:
    match = re.match(r'^\s*(?:answer\s*[:=]\s*)?([ABCD])\b', text, re.I)
    return match.group(1).upper() if match else '?'


def run_memory(out, methods=('recent', 'lexical', 'typed')):
    world, cases = memory_cases()
    system = ('Answer only from this agent\'s observed information. Do not use omniscient world facts. '
              'A reported claim remains something the speaker said. If the observations do not support an answer, '
              'choose D. Output a single option letter A, B, C, or D.')
    for case in cases:
        for method in methods:
            selected = world.retrieve(case['agent'], case['question'], case['day'], 4, method)
            prompt = (f"Agent: {case['agent']}. Current simulated day: {case['day']:g}.\n"
                      f"Accessible observations:\n{format_observations(selected)}\n\n"
                      f"{case['question']}\n{case['options']}")
            response = ask(system, prompt)
            result = {'phase': 'memory', 'method': method, **case, 'response': response,
                      'choice': choice(response), 'correct': choice(response) == case['gold'],
                      'selected_event_ids': [o.event_id for o in selected]}
            out.write(json.dumps(result) + '\n')
            out.flush()
            print('memory',case['agent'],method,case['gold'],result['choice'],flush=True)


def run_mood(out):
    system = ('You are a fictional person in a social simulation. Your stable profile is: '
              'gregariousness 70th percentile, assertiveness 50th percentile, and all other Big Five facets near average. '
              'The profile is a tendency, not a rule. Choose an action in character. '
              'Reply with A, B, or C and one short sentence. Do not mention scores.')
    for kind, text, valence, arousal in (
        ('hurt', 'A close friend mocked me sharply in front of others, and I heard it.', -0.8, 0.8),
        ('pleased', 'A close friend warmly congratulated me in front of others, and I heard it.', 0.8, 0.6),
    ):
        world = AgentWorld()
        world.add_event(kind, 0, text, {'agent': Observation(kind, 0, text, 'direct observation', valence, arousal)})
        for day in (0.0, 5.0):
            for method in ('history', 'history_plus_mood'):
                mood = world.mood('agent', day)
                prompt = f'Day {day:g}. What I observed on day 0: {text}\n'
                if method == 'history_plus_mood':
                    prompt += (f'Current temporary mood: valence {mood[0]:+.3f} '
                               '(-1 unpleasant, +1 pleasant); arousal '
                               f'{mood[1]:.3f} (0 calm, 1 activated).\n')
                prompt += ('Another friend invites me to a casual gathering tonight. '
                           'What do I do? A: go tonight. B: ask to decide tomorrow. C: decline.')
                response = ask(system, prompt)
                result = {'phase': 'mood', 'kind': kind, 'day': day, 'method': method,
                          'mood': mood, 'response': response, 'choice': choice(response)}
                out.write(json.dumps(result) + '\n')
                out.flush()
                print('mood',kind,day,method,result['choice'],flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--full-only', action='store_true')
    args = parser.parse_args()
    self_check()
    destination = Path('identity-full-history-results.jsonl') if args.full_only else OUT
    with destination.open('w') as results:
        run_memory(results, ('full',) if args.full_only else ('recent', 'lexical', 'typed'))
        if not args.full_only:
            run_mood(results)
    print(f'Wrote {destination}')
