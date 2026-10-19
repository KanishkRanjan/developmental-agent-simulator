"""Terminal widget helpers that need no terminal: tab bar, sliders, search filter, mascot frames."""
import json
from pathlib import Path

from devsim import tui

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def main():
    checks = []
    names = ['Runs', 'Watch', 'Characters', 'New']
    for width in (20, 60, 200):
        line = tui.tabs_line(names, 2, width)
        assert len(line) <= width
    assert '[3 Characters]' in tui.tabs_line(names, 2, 200) and '[1 Runs]' not in tui.tabs_line(names, 2, 200)
    checks.append('the tab bar marks the active tab and fits any width')

    assert tui.slider_text('openness', 50, 0, 100, 10).endswith('█████░░░░░ 50')
    assert tui.slider_text('mood', -1, -1, 1, 10).endswith('░' * 10 + ' -1.00') and tui.slider_text('x', 1, 0, 1, 4).endswith('████ 1.00')
    checks.append('a slider shows a bar filled in proportion and the value in the right form for its range')

    items = [{'key': 'priya', 'search': 'Priya priya @priya5468'}, {'key': 'rohan', 'search': 'Rohan rohan @rohan0946'},
             {'key': 'ms_okafor', 'search': 'Ms. Okafor ms_okafor'}]
    assert [i['key'] for i in tui.filter_items(items, 'pri')] == ['priya']
    assert [i['key'] for i in tui.filter_items(items, '@ROHAN')] == ['rohan']
    assert [i['key'] for i in tui.filter_items(items, 'ms oka')] == ['ms_okafor'] and len(tui.filter_items(items, '')) == 3
    checks.append('character search matches name, id or handle, case-insensitively, every word')

    frames = [tuple(tui.mascot(n)) for n in range(8)]
    assert len(set(frames)) >= 3 and all(len(f) == 5 for f in frames) and max(len(l) for l in tui.LOGO) <= 80
    checks.append('Pip the mascot animates through at least three frames, and the logo fits 80 columns')

    result = {'passed': True, 'scope': 'widget helpers; the interactive screens were driven in a pseudo-terminal', 'checks': checks}
    RESULTS_DIR.joinpath('tui-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
