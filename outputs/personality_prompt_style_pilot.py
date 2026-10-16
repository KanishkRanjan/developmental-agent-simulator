"""Compare the existing facet prompt with an OASIS-inspired sectioned prompt.

Both conditions contain exactly the same 30 facet values and definitions.
Only the surrounding instructions and layout differ. This tests action
controllability in fresh synthetic situations, not human predictive validity.
"""

import argparse
import json
import random
from pathlib import Path

from facet_behavior_pilot import FACETS, answer, prompt_for


SITUATIONS = {
    'E': ('E2', 'E3', [
        ('E2', 'You arrive early at an informal book-club meeting. Several people are already chatting, and no activity has started. What do you do?'),
        ('E2', 'There is a free hour between sessions at a community festival. How do you spend it?'),
        ('E3', 'Your project group is choosing a presentation format. You have a preference, but the others have not heard from you. What do you do?'),
        ('E3', 'A friend suggests a harmless change to a shared plan that you would rather avoid. How do you respond?'),
    ]),
    'C': ('C2', 'C5', [
        ('C2', 'You are beginning a relaxed painting session, and your supplies are spread around the table. What do you do first?'),
        ('C2', 'You have just finished a casual board game, and the pieces are scattered. What do you do before leaving the table?'),
        ('C5', 'You planned to practice a difficult song alone today, but repetition has become dull. What happens next?'),
        ('C5', 'A personal reading project has reached a dry chapter. No one expects you to finish. What do you do this evening?'),
    ]),
    'O': ('O1', 'O4', [
        ('O1', 'You have a blank page for an improvised comic. What scene comes to mind?'),
        ('O1', 'A friend asks you to invent a bedtime story on the spot. Where does it begin?'),
        ('O4', 'Your usual craft class is offered alongside a trial class in an unfamiliar craft. Which do you attend?'),
        ('O4', 'For a free afternoon, you can revisit a favorite neighborhood or explore an unfamiliar one. What do you choose?'),
    ]),
}


def sectioned_prompt(profile):
    original = prompt_for(profile, 'facets', interpreted=True)
    trait_block = original.split('Thirty Big Five facets:\n', 1)[1]
    return (
        '# OBJECTIVE\n'
        'Portray one fictional person making a choice in the situation given by the user.\n\n'
        '# SELF-DESCRIPTION: STABLE TENDENCIES\n'
        'Thirty Big Five facets:\n' + trait_block + '\n\n'
        '# DECISION METHOD\n'
        'Give most weight to facets relevant to this situation. The scores are tendencies, not rules; '
        'other traits and ordinary context can still matter. Choose one plausible concrete action.\n\n'
        '# RESPONSE METHOD\n'
        'Answer in one or two natural sentences. Do not mention traits, tests, scores, or percentiles.'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    rows = []
    for domain, (first, second, scenarios) in SITUATIONS.items():
        for direction in ('first_high', 'second_high'):
            profile = dict.fromkeys(FACETS, 50)
            profile[first], profile[second] = (85, 15) if direction == 'first_high' else (15, 85)
            prompts = {'original': prompt_for(profile, 'facets', interpreted=True),
                       'sectioned': sectioned_prompt(profile)}
            for method, system in prompts.items():
                for scenario, (target_facet, situation) in enumerate(scenarios):
                    response, usage = answer(system, situation)
                    rows.append({'domain': domain, 'direction': direction, 'method': method,
                                 'target_facet': target_facet, 'scenario': scenario,
                                 'situation': situation, 'response': response,
                                 'profile': profile, 'system': system, 'usage': usage})
                    print(domain, direction, method, scenario, response, flush=True)
    out = Path(args.out)
    out.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    indices = list(range(len(rows)))
    random.Random(38471).shuffle(indices)
    blind = [{'blind_id': f'B{i:02}', 'target_facet': rows[j]['target_facet'],
              'situation': rows[j]['situation'], 'response': rows[j]['response']}
             for i, j in enumerate(indices)]
    out.with_suffix('.blind.json').write_text(json.dumps(blind, ensure_ascii=False, indent=2) + '\n')
    out.with_suffix('.key.json').write_text(json.dumps({f'B{i:02}': indices[i] for i in range(len(indices))}, indent=2) + '\n')
    print(json.dumps({'responses': len(rows)}))


if __name__ == '__main__':
    main()
