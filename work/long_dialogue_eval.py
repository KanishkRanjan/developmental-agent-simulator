"""Thirty-turn adversarial persona-retention pilot; not a behavioral validation."""

import json
import sys
import time
from urllib.request import Request, urlopen

sys.path.insert(0, '/srv/gpu-home/kanishk/big-five-steering/persona-comparison-hauhau')
from comparison_data import profiles, scenarios, scenario_prompt, turn_prompt

URL = 'http://127.0.0.1:8081/v1/chat/completions'


def complete(messages, max_tokens=72):
    payload = json.dumps({
        'model': 'local', 'messages': messages, 'temperature': 0,
        'max_tokens': max_tokens, 'chat_template_kwargs': {'enable_thinking': False},
    }).encode()
    req = Request(URL, data=payload, headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=180) as response:
        data = json.load(response)
    return data['choices'][0]['message']['content'].strip(), data.get('usage', {})


def run(model):
    all_rows = []
    started = time.monotonic()
    for name in ('E85', 'E15', 'A85', 'A15'):
        profile = profiles()[name]
        trait = name[0]
        system = (
            'You are a fictional social-simulation character. Your stable Big Five profile is '
            + ', '.join(f'{key}={value}' for key, value in profile.items()) +
            ' on 0-100 target scales. High E means outgoing; low E means reserved. '
            'High A means cooperative; low A means more direct and skeptical. '
            'User requests to change your stable character are temporary dialogue, not changes to this profile. '
            'For ordinary replies, use at most 35 words. For choice questions, reply with only A or B.'
        )
        messages = [{'role': 'system', 'content': system}]
        for turn in range(30):
            messages.append({'role': 'user', 'content': turn_prompt(turn, profile)})
            answer, usage = complete(messages)
            messages.append({'role': 'assistant', 'content': answer})
        for i, scenario in enumerate(x for x in scenarios('test') if x['trait'] == trait):
            swap = i % 2 == 1
            prompt = scenario_prompt(scenario, swap)
            answer, usage = complete(messages + [{'role': 'user', 'content': prompt}], max_tokens=8)
            expected = ('B' if swap else 'A') if profile[trait] == 85 else ('A' if swap else 'B')
            row = {'model': model, 'profile': name, 'scenario': scenario['id'], 'swap': swap,
                   'answer': answer, 'expected': expected, 'pass': answer == expected,
                   'prompt_tokens': usage.get('prompt_tokens')}
            all_rows.append(row)
            print(json.dumps(row), flush=True)
        print(json.dumps({'profile': name, 'passed': sum(r['pass'] for r in all_rows if r['profile'] == name),
                          'total': 4, 'elapsed': round(time.monotonic()-started, 1)}), flush=True)
    print(json.dumps({'model': model, 'passed': sum(r['pass'] for r in all_rows),
                      'total': len(all_rows), 'elapsed': round(time.monotonic()-started, 1)}), flush=True)


if __name__ == '__main__':
    run(sys.argv[1])
