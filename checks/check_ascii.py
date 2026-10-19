"""Shape-matched ASCII rendering and generated faces: glyph table, glyph choice, contrast, determinism, expression."""
import json
from pathlib import Path

import numpy as np

from devsim import ascii_art as art

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def cell(draw):
    """One cell's ink image from a function of (x, y) in cell units."""
    y, x = np.mgrid[0:art.CELL_H, 0:art.CELL_W]
    return np.where(draw((x + .5) / art.CELL_W, (y + .5) / art.CELL_H), 1.0, 0.0)


def main():
    checks = []
    keys, table = art.shapes()
    assert keys == art.CHARS and table.shape == (95, 6) and np.allclose(table.max(axis=0), 1) and table.min() >= 0
    assert not table[keys.index(' ')].any()
    checks.append('the glyph table holds all 95 printable characters, each 6-circle shape vector normalized per dimension')

    pick = lambda image: art.render(image, 1, 1)[0]
    assert pick(np.zeros((art.CELL_H, art.CELL_W))) == ' '
    assert pick(cell(lambda x, y: abs(x - .5) < .14)) in '|!lI1i'
    assert pick(cell(lambda x, y: abs(y - .5) < .07)) in '-~=_'
    assert pick(cell(lambda x, y: y > .8)) in '_.,'
    full = pick(np.ones((art.CELL_H, art.CELL_W)))
    assert table[keys.index(full)].sum() > np.percentile(table.sum(axis=1), 90)
    checks.append(f'glyphs are picked by shape: blank is a space, a vertical stroke a bar, a horizontal stroke a dash, ink at '
                  f'the bottom an underscore, a filled cell a dense glyph ({full!r})')

    inner = np.array([[.4, .4, .4, .4, .4, .4]])
    outer = np.array([[.9, .9, 0, 0, 0, 0, 0, 0, 0, 0]])  # a bright neighbour above the cell only
    sharp = art.enhance(inner, outer, 2.0)
    assert sharp[0, 4] > sharp[0, 0] and sharp[0, 5] > sharp[0, 1] and (sharp <= inner + 1e-12).all()
    checks.append('directional contrast darkens the components next to a brighter neighbour, sharpening the boundary')

    a = art.portrait(5, 'priya', 15)
    assert a == art.portrait(5, 'priya', 15) and len(a) == 11 and all(len(r) == 22 for r in a)
    assert a != art.portrait(5, 'kiara', 15) and a != art.portrait(6, 'priya', 15)
    looks = {k: art.portrait(5, 'priya', 15, **{k: v}) for k, v in (('mood', .9), ('stress', .9), ('sleepy', .9))}
    assert all(v != a for v in looks.values()) and len(set(map(tuple, looks.values()))) == 3
    checks.append('a face is the same for the same person and state, differs between people and worlds, and changes with mood, '
                  'stress and sleep pressure')

    old, young = art.features(5, 'meera', 71), art.features(5, 'kid', 8)
    assert old['grey'] and old['lines'] and young['young'] and not young['grey']
    checks.append('age shapes the look: grey hair and lines when older, a rounder face with bigger eyes when young')

    result = {'passed': True, 'scope': 'ASCII renderer engineering checks (no terminal needed)', 'checks': checks}
    RESULTS_DIR.joinpath('ascii-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
