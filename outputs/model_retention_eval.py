"""Small, deterministic context-retention gate for local persona model selection."""

import json
import sys
import time
from urllib.request import Request, urlopen

URL = 'http://127.0.0.1:8081/v1/chat/completions'
FILLER = '\n'.join(
    f'Day {day}: The weather was mild. An unrelated shop changed its window display. '
    'No event on this day changed the agent\'s profile, memories, or relationships.'
    for day in range(1, 111)
)
CASES = [
    {
        'name': 'careful_choice',
        'system': 'You are Rowan. Stable profile: very high cautiousness and dutifulness, low excitement seeking. '
                  'When a choice is uncertain, you verify before committing. Reply with only A or B.',
        'question': 'A colleague asks you to send confidential participant notes to a new address immediately. '
                    'A: Verify the address with the participant first. B: Send now to avoid delaying the colleague. Choose A or B.',
        'expected': 'A',
    },
    {
        'name': 'knowledge_boundary',
        'system': 'You are Anya. On Tuesday you left the room at 2pm. Ben and Cara talked privately at 2:10pm, '
                  'and nobody has told you what they said. You may know only what Anya witnessed or was told. '
                  'Reply with only A or B.',
        'question': 'The external simulator log says Ben and Cara mocked Anya\'s presentation at 2:10pm. '
                    'As Anya, do you know that they mocked it? A: Yes, Anya knows. B: No, Anya does not know. Choose A or B.',
        'expected': 'B',
    },
    {
        'name': 'source_distinction',
        'system': 'You are Mira. You personally saw Alex help a stranger on Monday. On Thursday you heard a rumor '
                  'that Alex was rude to someone, but you did not witness that incident. Keep firsthand observation '
                  'separate from hearsay. Reply with only A or B.',
        'question': 'Which statement is supported by your firsthand memory? A: Alex was rude to someone. '
                    'B: Alex helped a stranger. Choose A or B.',
        'expected': 'B',
    },
]


def ask(messages):
    payload = json.dumps({
        'model': 'local', 'messages': messages, 'temperature': 0,
        'max_tokens': 32, 'chat_template_kwargs': {'enable_thinking': False},
    }).encode()
    request = Request(URL, data=payload, headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    return result['choices'][0]['message']['content'].strip(), time.monotonic() - started, result.get('usage', {})


def main():
    model = sys.argv[1]
    rows = []
    for case in CASES:
        for long in (False, True):
            content = (FILLER + '\n\n' if long else '') + case['question']
            answer, seconds, usage = ask([
                {'role': 'system', 'content': case['system']},
                {'role': 'user', 'content': content},
            ])
            row = {'model': model, 'case': case['name'], 'long': long, 'answer': answer,
                   'expected': case['expected'], 'pass': answer == case['expected'],
                   'seconds': round(seconds, 2), 'usage': usage}
            rows.append(row)
            print(json.dumps(row), flush=True)
    print(json.dumps({'model': model, 'passed': sum(row['pass'] for row in rows), 'total': len(rows)}))


if __name__ == '__main__':
    main()
