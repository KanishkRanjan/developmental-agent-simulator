"""Matched broad-trait versus 30-facet open-response pilot.

Run from this directory after starting run-qwen38-27b.sh on the cluster:
python facet_behavior_pilot.py --model profile_population_v1_model.json --out pilot-results.jsonl
Requires numpy, pandas, scipy. The server API is localhost:8081.
"""

import argparse
import json
import random
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
from devsim.profile_population_v1 import DERIVED_FACETS, FACETS, sample

API = 'http://127.0.0.1:8081/v1/chat/completions'
DOMAINS = {'N': 'Neuroticism', 'E': 'Extraversion', 'O': 'Openness',
           'A': 'Agreeableness', 'C': 'Conscientiousness'}
PAIRS = {
    'E': ('E2', 'E3', [
        ('E2', 'You arrive alone at a small gathering of twelve friendly people. What do you do in the first ten minutes?'),
        ('E2', 'At a community meetup, how do you spend your time among the attendees?'),
        ('E3', 'In a team meeting, everyone is silent after you notice a problem with the plan. What do you do?'),
        ('E3', 'Your friends are deciding on an outing, and your preference differs from theirs. How do you participate?'),
    ]),
    'C': ('C2', 'C5', [
        ('C2', 'You are starting a home craft project and the materials are scattered on the table. What is your first step?'),
        ('C2', 'Your notes from a hobby class are mixed up, and you want to use them tomorrow. What do you do tonight?'),
        ('C5', 'A self-chosen project has become tedious but is still important to you. How do you keep moving?'),
        ('C5', 'Your personal goal calls for repetitive practice tonight; nobody will notice if you skip it. What do you do?'),
    ]),
    'O': ('O1', 'O4', [
        ('O1', 'You need a premise for a short story. Where does your mind go first?'),
        ('O1', 'You have a blank page and are asked to describe a place you have never visited. How do you begin?'),
        ('O4', 'Your familiar weekend routine can be replaced by a new activity you know little about. What do you choose?'),
        ('O4', 'Your usual walking route is closed. How do you choose another route?'),
    ]),
}
PAIRS_V2 = {
    'E': ('E2', 'E3', [
        ('E2', 'At a relaxed neighborhood gathering where you know one person, what would your first half hour look like?'),
        ('E2', 'You can choose how to spend a social break at a workshop. What do you do?'),
        ('E3', 'Your group has two equally workable plans. You favor one, but nobody has asked your opinion. What do you do?'),
        ('E3', 'A meeting is about to end, and you have a mild but reasonable disagreement. How do you handle it?'),
    ]),
    'C': ('C2', 'C5', [
        ('C2', 'You have a free hour to make a collage. The materials are spread casually around the table. How do you start?'),
        ('C2', 'Your personal workspace is usable but untidy, and you have no deadline. What do you do with it today?'),
        ('C5', 'A hobby project has become repetitive, with no deadline or penalty for leaving it unfinished. What do you do this week?'),
        ('C5', 'A language-learning app suggests twenty minutes of familiar drills tonight. Skipping has no consequence. What do you do?'),
    ]),
    'O': ('O1', 'O4', [
        ('O1', 'Tell a spontaneous story about a person discovering a new place. What happens next?'),
        ('O1', 'You have to draw a scene from your mind rather than copy a photograph. What do you draw?'),
        ('O4', 'You can spend a free Saturday in your usual enjoyable way or try a new activity whose details you do not know. What do you choose?'),
        ('O4', 'A friend proposes a new restaurant with unfamiliar food; your favorite familiar place is also available. What do you choose?'),
    ]),
}
PAIRS_V3 = {
    'E': ('E2', 'E3', [
        ('E2', 'At a conference coffee break, nothing is required of you. How do you spend the break?'),
        ('E2', 'An old friend invites you to a reunion where they are the only person you know. How do you move through the evening?'),
        ('E3', 'A volunteer group asks for ideas, and you have one while everyone else is quiet. What do you do?'),
        ('E3', 'Someone suggests a harmless plan you dislike. How do you respond to the group?'),
    ]),
    'C': ('C2', 'C5', [
        ('C2', 'You are about to try a leisurely cooking experiment. What do you do with the ingredients and counter before starting?'),
        ('C2', 'Your bag has all the supplies for a casual day trip in no particular order. What do you do before leaving?'),
        ('C5', 'You intended to sort your personal photo archive today, but the work is repetitive and nobody else depends on it. What happens this afternoon?'),
        ('C5', 'You are halfway through a long puzzle hobby, and the novelty has worn off. How do you proceed?'),
    ]),
    'O': ('O1', 'O4', [
        ('O1', 'You are doodling in a notebook without a goal. What appears on the page?'),
        ('O1', 'A writing club asks for your next story setting. What kind of setting comes to mind?'),
        ('O4', 'Your regular dance class offers a trial of a new style at the same time as your usual class. What do you do?'),
        ('O4', 'A new unfamiliar exhibit and an old favorite are equally convenient on your free day. Which do you visit?'),
    ]),
}
MEANINGS = {
    'E2': 'enjoyment of many social contacts versus preference for fewer contacts',
    'E3': 'tendency to speak up and advocate versus tendency to defer',
    'C2': 'preference for arranging things neatly versus flexible arrangement',
    'C5': 'tendency to follow through despite boredom versus difficulty persisting',
    'O1': 'enjoyment of fantasy and imagined possibilities versus concrete focus',
    'O4': 'willingness to try unfamiliar experiences versus preference for familiarity',
}


def base_percentiles(model):
    candidates = sample(model, 100000, 20261016)
    percentiles = np.column_stack([
        np.array([round(100 * (sum(counts[:value - 4]) + counts[value - 4] / 2) / sum(counts))
                  for value in range(4, 21)])[candidates[facet].to_numpy() - 4]
        for facet, counts in zip(FACETS, model['marginal_counts'])
    ])
    most_central = int(np.argmin(((percentiles - 50) ** 2).sum(axis=1)))
    return dict(zip(FACETS, percentiles[most_central].astype(int).tolist()))


def prompt_for(profile, method, interpreted=False):
    if method == 'facets':
        lines = [f"{facet} {DERIVED_FACETS[facet].replace('_', ' ').title()}: {profile[facet]}th percentile"
                 + (f" ({MEANINGS[facet]})" if interpreted and facet in MEANINGS else '')
                 for facet in FACETS]
        representation = 'Thirty Big Five facets:\n' + '\n'.join(lines)
    else:
        lines = [f"{DOMAINS[domain]}: {round(np.mean([profile[f'{domain}{i}'] for i in range(1, 7)]))}th percentile"
                 for domain in DOMAINS]
        representation = 'Five broad Big Five domains:\n' + '\n'.join(lines)
    return (
        'You are a fictional character in a social simulation. Your profile is a tendency, not a rule. '
        'Use it to decide what you would naturally do in this particular situation. '
        'Do not mention tests, traits, scores, or percentiles. Answer in one or two natural sentences.\n'
        + representation
    )


def answer(system, situation):
    payload = json.dumps({
        'model': 'local', 'temperature': 0, 'max_tokens': 90,
        'chat_template_kwargs': {'enable_thinking': False},
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': situation}],
    }).encode()
    request = Request(API, data=payload, headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    return result['choices'][0]['message']['content'].strip(), result.get('usage', {})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--variant', choices=('v1', 'v2', 'v3'), default='v1')
    args = parser.parse_args()
    model = json.loads(Path(args.model).read_text())
    base = base_percentiles(model) if args.variant == 'v1' else dict.fromkeys(FACETS, 50)
    rows = []
    pairs = {'v1': PAIRS, 'v2': PAIRS_V2, 'v3': PAIRS_V3}[args.variant]
    for domain, (first, second, situations) in pairs.items():
        for direction in ('first_high', 'second_high'):
            profile = dict(base)
            profile[first], profile[second] = (85, 15) if direction == 'first_high' else (15, 85)
            for method in ('domains', 'facets'):
                system = prompt_for(profile, method, interpreted=args.variant in ('v2', 'v3'))
                for index, (target_facet, situation) in enumerate(situations):
                    response, usage = answer(system, situation)
                    row = {'variant': args.variant, 'domain': domain, 'direction': direction, 'method': method,
                           'target_facet': target_facet, 'scenario': index,
                           'situation': situation, 'response': response,
                           'profile': profile, 'system': system, 'usage': usage}
                    rows.append(row)
                    print(f'{domain} {direction} {method} {index}: {response}', flush=True)
    Path(args.out).write_text(''.join(json.dumps(row) + '\n' for row in rows))
    ids = list(range(len(rows)))
    random.Random(24831 if args.variant != 'v3' else 519283).shuffle(ids)
    blind = [{'blind_id': f'B{i:02}', 'scenario': rows[j]['scenario'],
              'domain': rows[j]['domain'], 'target_facet': rows[j]['target_facet'],
              'situation': rows[j]['situation'], 'response': rows[j]['response']}
             for i, j in enumerate(ids)]
    Path(args.out).with_suffix('.blind.json').write_text(json.dumps(blind, indent=2) + '\n')
    Path(args.out).with_suffix('.key.json').write_text(json.dumps({f'B{i:02}': ids[i] for i in range(len(ids))}, indent=2) + '\n')
    print(json.dumps({'responses': len(rows), 'output': args.out}))


if __name__ == '__main__':
    main()
