"""Guards at the language-model boundary (design v2, build step 10; all design defaults).

Opinions, tie scalars, dials and goals live in simulation state. A model may voice them and may propose a change;
the change applied is never larger than the bounded-confidence rule allows for that pair. Each person's speech
style, directness and stubbornness are sampled once and fixed. A tie with enmity sets a floor on non-cooperation.
The variance monitor flags a population collapsing toward one opinion, the homogenization failure signal.
"""
from statistics import pvariance

from .core import clip, uniform

STYLES = ('plain and brief', 'warm and talkative', 'dry and ironic', 'formal and careful', 'blunt', 'hesitant', 'animated')


def rule_change(pop, mine, other, listener, source, t):
    """The bounded-confidence (Deffuant) update for `listener` hearing `source` on one topic."""
    cfg = pop.cfg
    if abs(mine - other) >= cfg['opinion_epsilon']:
        return mine
    weight = (.3 + .7 * uniform(pop.seed, 'credibility', source)) ** (cfg['credibility_gamma'] * pop.dials(listener, t)['reality_testing'])
    return clip(mine + cfg['opinion_mu'] * weight * (other - mine), -1, 1)


def clamp(pop, mine, other, proposed, listener, source, t):
    """Apply a model-proposed opinion only as far as the rule allows: same direction, no larger move.
    Returns (applied value, whether it was clamped)."""
    allowed = rule_change(pop, mine, other, listener, source, t)
    move, limit = proposed - mine, allowed - mine
    if move * limit < 0 or abs(move) > abs(limit) or (limit == 0 and move != 0):
        return allowed, True
    return proposed, False


def post_check(before, after, allowed_after):
    """True when a rendered exchange moved an opinion further than the rule allowed: resample the turn."""
    return abs(after - before) > abs(allowed_after - before) + 1e-9


def persona(pop, pid):
    return {'speech_style': STYLES[int(uniform(pop.seed, 'style', pid) * len(STYLES))],
            'directness': round(uniform(pop.seed, 'directness', pid), 2), 'stubbornness': round(uniform(pop.seed, 'stubborn', pid), 2)}


def conflict_floor(tie_record):
    """Minimum non-cooperation implied by enmity or an active dispute (0 when the tie is friendly)."""
    if tie_record['ruptured'] is not None:
        return 1.0
    return round(clip(-tie_record['valence'], 0, 1) + .1 * min(5, tie_record['hostile']) * (tie_record['valence'] < 0), 2)


def record_variance(pop, topic, t, values):
    rows = pop.state.setdefault('variance', {}).setdefault(topic, [])
    values = list(values)
    if len(values) >= 2:
        rows.append([t, pvariance(values)])
    return rows


def collapsed(pop, topic, *, fraction=.2, sustained=3):
    """The failure signal: variance stayed below `fraction` of its first recorded value for `sustained` records."""
    rows = pop.state.get('variance', {}).get(topic, [])
    if len(rows) < sustained + 1 or rows[0][1] <= 0:
        return False
    return all(v < fraction * rows[0][1] for _, v in rows[-sustained:])
