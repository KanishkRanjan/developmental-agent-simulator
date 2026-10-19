"""Shape-matched ASCII rendering and generated character faces (for the watcher).

Method after Alex Harri, "ASCII rendering" (https://alexharri.com/blog/ascii-rendering): a character is picked by its
shape, not only its brightness. Each cell is sampled with 6 circles (2 columns x 3 rows, left column lowered, right
raised, slightly overlapping) to give a 6-number sampling vector, sharpened by directional contrast (10 circles just
outside the cell, reaching into the neighbours) and global contrast, then matched to the nearest precomputed glyph
shape vector (each dimension normalized by its maximum over all glyphs). Lookups are cached by a 30-bit key.

    python3 -m devsim.ascii_art --build-shapes   (once; needs PIL and DejaVu Sans Mono; writes devsim/data/ascii_shapes.json)
    python3 -m devsim.ascii_art --demo           (prints a few faces)

Faces are drawn as an "ink" image (1 = drawn) from a person's seeded features and age; the expression follows their
current state (mood, stress, sleep pressure, tonic dopamine). Reading only: nothing here changes a world.
"""
import argparse
from functools import lru_cache
import json
from math import cos, pi, sin
from pathlib import Path

import numpy as np

SHAPES_PATH = Path(__file__).resolve().parent / 'data' / 'ascii_shapes.json'
CHARS = [chr(c) for c in range(32, 127)]
CELL_W, CELL_H = 8, 16  # sampling image pixels per terminal cell (cells are about twice as tall as wide)
# Circle centres in cell units (x across, y down) and radius in cell widths.
INTERNAL = [(.27, .22), (.73, .16), (.27, .55), (.73, .49), (.27, .88), (.73, .82)]
EXTERNAL = [(.27, -.12), (.73, -.18), (-.2, .22), (1.2, .16), (-.2, .55), (1.2, .49), (-.2, .88), (1.2, .82), (.27, 1.2), (.73, 1.14)]
RADIUS = .28
# Which external circles can sharpen each internal one (from the article).
AFFECTING_EXTERNAL = [[0, 1, 2, 4], [0, 1, 3, 5], [2, 4, 6], [3, 5, 7], [4, 6, 8, 9], [5, 7, 8, 9]]


def circle_points(cx, cy, r, w, h, rings=(0, .45, .9), per_ring=8):
    """Sample offsets (pixels) inside one circle: the centre plus points on rings."""
    points = []
    for ring in rings:
        n = 1 if ring == 0 else per_ring
        for i in range(n):
            a = 2 * pi * i / n + ring
            points.append((cx * w + ring * r * w * cos(a), cy * h + ring * r * w * sin(a)))
    return points


def build_shapes(font_path='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', size=48):
    """Render each printable glyph and measure ink coverage in the 6 internal circles; normalize per dimension."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(font_path, size)
    ascent, descent = font.getmetrics()
    w, h = round(font.getlength('M')), ascent + descent
    raw = {}
    for ch in CHARS:
        glyph = Image.new('L', (w, h), 0)
        ImageDraw.Draw(glyph).text((0, 0), ch, fill=255, font=font)
        ink = np.asarray(glyph, dtype=float) / 255
        vector = []
        for cx, cy in INTERNAL:
            pts = circle_points(cx, cy, RADIUS, w, h, rings=(0, .25, .5, .75, 1.0), per_ring=24)
            vector.append(float(np.mean([ink[min(h - 1, max(0, int(y))), min(w - 1, max(0, int(x)))] for x, y in pts])))
        raw[ch] = vector
    tops = [max(v[i] for v in raw.values()) or 1.0 for i in range(6)]
    shapes = {ch: [round(x / t, 5) for x, t in zip(v, tops)] for ch, v in raw.items()}
    SHAPES_PATH.write_text(json.dumps({'font': Path(font_path).name, 'size': size, 'cell': [w, h],
                                       'circles': INTERNAL, 'radius': RADIUS, 'shapes': shapes}, indent=1) + '\n')
    return shapes


@lru_cache(maxsize=1)
def shapes():
    data = json.loads(SHAPES_PATH.read_text())['shapes']
    keys = list(data)
    return keys, np.array([data[k] for k in keys])


@lru_cache(maxsize=1)
def offsets():
    """(internal, external) sample offsets, pixel arrays of shape [circles, points, 2]."""
    make = lambda centres: np.array([circle_points(cx, cy, RADIUS, CELL_W, CELL_H) for cx, cy in centres])
    return make(INTERNAL), make(EXTERNAL)


def sample(ink, origins, offs):
    """Mean ink in each circle for every cell: [cells, circles]. Outside the image counts as empty."""
    h, w = ink.shape
    ys = (origins[:, None, None, 0] + offs[None, :, :, 1]).astype(int)
    xs = (origins[:, None, None, 1] + offs[None, :, :, 0]).astype(int)
    inside = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
    values = np.where(inside, ink[np.clip(ys, 0, h - 1), np.clip(xs, 0, w - 1)], 0.0)
    return values.mean(axis=2)


def enhance(internal, external, exponent):
    """Directional contrast (against the neighbouring external circles), then global contrast, per cell."""
    out = internal.copy()
    for i, affecting in enumerate(AFFECTING_EXTERNAL):
        m = np.maximum(internal[:, i], external[:, affecting].max(axis=1))
        safe = np.where(m > 0, m, 1)
        out[:, i] = np.where(m > 0, (internal[:, i] / safe) ** exponent * m, 0)
    m = out.max(axis=1, keepdims=True)
    safe = np.where(m > 0, m, 1)
    return np.where(m > 0, (out / safe) ** exponent * m, 0)


def render(ink, cols, rows, exponent=1.6):
    """Lines of text for an ink image of shape [rows * CELL_H, cols * CELL_W] with values in [0, 1]."""
    assert ink.shape == (rows * CELL_H, cols * CELL_W), ink.shape
    keys, table = shapes()
    origins = np.array([(r * CELL_H, c * CELL_W) for r in range(rows) for c in range(cols)])
    inner, outer = offsets()
    vectors = enhance(sample(ink, origins, inner), sample(ink, origins, outer), exponent)
    cache, out = {}, []
    for v in vectors:
        key = sum(min(31, int(x * 32)) << (5 * i) for i, x in enumerate(v))  # the article's 30-bit key
        if key not in cache:
            cache[key] = keys[int(np.argmin(((table - v) ** 2).sum(axis=1)))]
        out.append(cache[key])
    return [''.join(out[r * cols:(r + 1) * cols]) for r in range(rows)]


# Faces

def features(seed, owner, age):
    """Fixed look of one person, seeded by (world seed, person, 'portrait') and shaped by age."""
    from .attention import unit
    u = lambda purpose: unit(seed, owner, 'portrait', purpose)
    styles = ['short', 'long', 'bun', 'curly', 'side'] if age >= 12 else ['short', 'long', 'curly']
    return {'face_w': .5 + .1 * u('face_w'), 'face_h': .66 + .08 * u('face_h'),
            'hair': 'bald' if age > 55 and u('bald') < .3 else styles[int(u('hair') * len(styles))],
            'grey': age > 55, 'glasses': u('glasses') < .25, 'freckles': age < 30 and u('freckles') < .3,
            'lines': age > 50, 'young': age < 12, 'eye_gap': .2 + .05 * u('eye_gap')}


def expression(mood=0.0, stress=0.0, sleepy=0.0, drive=0.0):
    """Mouth curve from mood, brows from stress, eyelids from sleep pressure, eye size from tonic dopamine."""
    clip = lambda x, a=-1.0, b=1.0: max(a, min(b, x))
    return {'smile': clip(mood), 'worry': clip(stress, 0), 'droop': clip(sleepy, 0), 'bright': clip(drive)}


def face(look, mood, cols=22, rows=11):
    """An ink image of a face, ready for render(): bright strokes on an empty background."""
    h, w = rows * CELL_H, cols * CELL_W
    y, x = np.mgrid[0:h, 0:w]
    x = (x - w / 2) / (w / 2)  # -1..1 across
    y = (y - h / 2) / (h / 2)  # -1..1 down
    ink = np.zeros((h, w))
    fw, fh = look['face_w'], look['face_h']
    def stroke(mask, level=1.0):
        np.maximum(ink, np.where(mask, level, 0), out=ink)
    head = (x / fw) ** 2 + ((y - .08) / fh) ** 2
    stroke(np.abs(head - 1) < .09, .9)  # outline
    grey = .5 if look['grey'] else .85
    top = (y < -.32 + .1 * np.cos(x * 4)) & (head < 1.25)
    hair = {'short': top, 'curly': top | ((head < 1.35) & (head > .95) & (y < .1)),
            'long': top | ((np.abs(x) > fw * .82) & (np.abs(x) < fw * 1.25) & (y < .75) & (y > -.6)),
            'bun': top | ((x ** 2 + (y + fh + .05) ** 2) < .06),
            'side': (y < -.32 + .25 * x) & (head < 1.25), 'bald': np.zeros_like(top)}[look['hair']]
    texture = .75 + .25 * np.sin(x * 40 + y * 13) if look['hair'] == 'curly' else 1.0
    stroke(hair, grey * texture)
    gap, size = look['eye_gap'], (1.25 if look['young'] else 1.0) * (1 + .15 * mood['bright'])
    for side in (-1, 1):
        ex, ey = side * gap * fw / .55, -.02
        opening = max(.25, 1 - .7 * mood['droop'])
        eye = ((x - ex) / (.1 * size)) ** 2 + ((y - ey) / (.07 * size * opening)) ** 2
        stroke(np.abs(eye - 1) < .35, .9)
        stroke(((x - ex) ** 2 + (y - ey) ** 2) < (.035 * size) ** 2, 1.0)  # pupil
        if mood['droop'] > .3:  # heavy eyelid
            stroke((np.abs(y - (ey - .07 * size * opening)) < .02) & (np.abs(x - ex) < .12 * size), 1.0)
        tilt = .1 * mood['worry'] * side  # worry lifts the inner ends of the brows
        brow_y = ey - .17 - tilt * (ex - x) / .12 * side
        stroke((np.abs(y - brow_y) < .025) & (np.abs(x - ex) < .12), .95)
        if look['glasses']:
            stroke(np.abs(((x - ex) / .17) ** 2 + ((y - ey) / .13) ** 2 - 1) < .18, .8)
    if look['glasses']:
        stroke((np.abs(y + .02) < .015) & (np.abs(x) < gap * fw / .55 - .17), .8)
    stroke((np.abs(x) < .025) & (y > .05) & (y < .25), .6)  # nose
    curve = .12 * mood['smile']
    mouth = .42 - curve + curve * (x / .22) ** 2
    stroke((np.abs(y - mouth) < .025) & (np.abs(x) < .22), 1.0)
    if look['lines']:
        stroke((np.abs(y + .38) < .012) & (np.abs(x) < .25) & (head < .9), .5)
    if look['freckles']:
        for fx, fy in ((-.3, .18), (-.22, .22), (.3, .18), (.22, .22)):
            stroke(((x - fx) ** 2 + (y - fy) ** 2) < .0008, .7)
    return ink


def portrait(seed, owner, age, mood=0.0, stress=0.0, sleepy=0.0, drive=0.0, cols=22, rows=11):
    return render(face(features(seed, owner, age), expression(mood, stress, sleepy, drive), cols, rows), cols, rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--build-shapes', action='store_true')
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    if args.build_shapes:
        build_shapes()
        print(f'wrote {SHAPES_PATH}')
    if args.demo:
        for owner, age, state in (('priya', 15, {}), ('meera', 71, {'mood': .6}), ('rohan', 16, {'mood': -.7, 'stress': .9, 'sleepy': .8})):
            print(owner, age, state)
            print('\n'.join(portrait(5, owner, age, **state)))


if __name__ == '__main__':
    main()
