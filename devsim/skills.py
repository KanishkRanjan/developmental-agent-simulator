"""Open-ended skills: acquisition, forgetting, performance and expression. No model calls; lazy and event-driven.

A skill is created the first time a person practises or meets an activity, keyed by its normalized label; there is no
list of skills. State changes only at practice events; level at any time is read in closed form and reading never
changes anything. Every constant is in devsim/policies/skills.json with its evidence tag and ledger ID
(docs/research/skill_acquisition_ledger.md); docs/PARAMETERS.md lists them.

  level      L(t) = L x R(t), R(t) = exp(-(t - t_last) / S)                        within-learner exponential [D, E1]
  practice   L' = C - (C - L(t)) exp(-alpha_eff)                                   exponential approach [D]
             S' = min(S_max, S (1 + k_s (1 - R)^p mode_s q a))                     spacing and testing [D, E8, E9]
  rates      alpha, S0 ~ gamma per (person, skill)                                 power law only on average [V, E2]
  shifts     occasional strategy shifts: a dip, a faster segment, a higher ceiling   [C, E4; parameters U]
  decay      stability scales down with cognitive, open-loop, accuracy-graded      ordering [D, E12]
  doing it   performance = L(t) x state modifier (sleep pressure, stress); stored skill is untouched [D, E19, E20]
  knowing it competence_check decides success outside the model (ground truth); skill_directive tells the model how
             to play the result; perceived skill carries noise calibrated to r = .29 with true skill [D, E22]

One code path for everyone: differences come from Big Five, the four dials, hormone state, one seeded aptitude latent
and event history. Every random draw is seeded by (world seed, person, event or skill, purpose).
"""
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from math import exp, log
from random import Random
import re

from . import POLICY_DIR

CONFIG_PATH = POLICY_DIR / 'skills.json'
PURPOSES = ('skill_aptitude', 'skill_rate', 'skill_stability', 'strategy_shift', 'practice_success', 'perceived_noise',
            'competence_noise')
TIERS = ('none', 'novice', 'competent', 'proficient', 'expert')
MODES = ('retrieval', 'restudy')
FEEDBACK = ('task', 'self', 'none')
FUNCTION_WORDS = {'a', 'an', 'the', 'and', 'or', 'to', 'of', 'on', 'at', 'in', 'for', 'with', 'my', 'your', 'some', 'up'}


@dataclass(frozen=True)
class SkillAttributes:
    cognitive: float = .5          # 0 physical/motor, 1 cognitive/declarative
    open_loop: float = .5          # 0 closed-loop discrete, 1 open-loop continuous
    accuracy_graded: float = .5    # 0 speed-graded, 1 accuracy-graded
    feedback_clarity: float = .5   # 0 noisy outcomes, 1 objective immediate feedback


@dataclass
class SkillState:
    key: str
    attrs: dict
    L: float
    t_last: float
    S: float
    alpha: float
    S0: float
    ceiling: float
    segment: int = 0
    alpha_mult: float = 1.0
    n_practice: int = 0
    n_retrieval: int = 0
    n_success: int = 0
    created_at: float = 0.0
    attrs_defaulted: bool = False
    label: str = ''                             # the words first used for it, for prompts
    origin: dict = field(default_factory=dict)  # the creation values, so the log can be replayed
    log: list = field(default_factory=list)


# Config

def parameters():
    data = json.loads(CONFIG_PATH.read_text())
    return data['parameters'], data['tier_text']


def configure(engine, overrides=None):
    from .engine import number
    spec, text = parameters()
    overrides = overrides or {}
    if not isinstance(overrides, dict) or set(overrides) - set(spec):
        raise ValueError(f'Unknown skills setting: {sorted(set(overrides or {}) - set(spec))}')
    settings = {k: overrides.get(k, item['value']) for k, item in spec.items()}
    for key, item in spec.items():
        if 'choices' in item:
            if settings[key] not in item['choices']:
                raise ValueError(f'{key} must be one of {item["choices"]}')
        else:
            number(settings[key], *item['range'], key)
    if not settings['tier_novice'] < settings['tier_competent'] < settings['tier_proficient'] < settings['tier_expert']:
        raise ValueError('Tier thresholds must rise')
    settings['tier_text'] = text
    settings['sigma_self'] = calibrate_sigma(settings)
    current = engine.state['config'].get('skills')
    if current is not None and current != settings:
        raise ValueError('Cannot silently replace skills policy')
    engine.state['config']['skills'] = settings


def cfg(engine):
    return engine.state['config']['skills']


def rng(engine, owner, key, purpose):
    """A Random seeded by (world seed, person, event or skill, purpose); purposes are fixed (section 8 of the spec)."""
    assert purpose in PURPOSES, purpose
    digest = sha256(json.dumps([engine.state.get('seed'), owner, key, purpose]).encode()).digest()
    return Random(int.from_bytes(digest[:8], 'big'))


# Identity and similarity

def normalize_label(text):
    """Lowercase, no punctuation, no function words, light suffix stripping. shortcut: no lemmatiser exists in the repo."""
    words = re.findall(r"[a-z0-9]+", str(text).lower())
    out = []
    for w in words:
        if w in FUNCTION_WORDS:
            continue
        if len(w) > 5 and w.endswith('ies'):
            w = w[:-3] + 'y'
        elif len(w) > 5 and w.endswith('ing'):
            w = w[:-3]
        elif len(w) > 4 and w.endswith('ed'):
            w = w[:-2]
        elif len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
            w = w[:-1]
        if len(w) > 3 and w.endswith('e'):
            w = w[:-1]
        if len(w) > 2 and w[-1] == w[-2] and w[-1] not in 'aeiou':  # running -> runn -> run
            w = w[:-1]
        out.append(w)
    return ' '.join(out)


def similarity(a, b):
    """Token-set Jaccard on normalized labels (the default SkillSimilarity; no model dependency)."""
    x, y = set(normalize_label(a).split()), set(normalize_label(b).split())
    return len(x & y) / len(x | y) if x | y else 0.0


def attributes(given=None):
    """(SkillAttributes, defaulted?) from a catalog or event; neutral 0.5 when nothing is given [U]."""
    if not given:
        return SkillAttributes(), True
    from .engine import number
    values = {k: number(given.get(k, .5), 0, 1, k) for k in ('cognitive', 'open_loop', 'accuracy_graded', 'feedback_clarity')}
    return SkillAttributes(**values), False


def stability_scale(c, attrs):
    """Smaller stability for cognitive, open-loop and accuracy-graded skills: the E12 ordering, magnitudes [U]."""
    return exp(-(c['decay_cognitive'] * attrs['cognitive'] + c['decay_open_loop'] * attrs['open_loop']
                 + c['decay_accuracy'] * attrs['accuracy_graded']))


# Store

def store(engine, owner):
    return engine.agent(owner).setdefault('skills', {})


def state_of(engine, owner, key):
    record = store(engine, owner).get(normalize_label(key))
    return None if record is None else SkillState(**record)


def aptitude(engine, owner):
    """exp(beta_apt z + openness link), z a seeded N(0, 1) drawn once per person. The module's one agent-level variable."""
    c = cfg(engine)
    if c['aptitude_mode'] == 'off':
        return 1.0
    agent = engine.agent(owner)
    if 'skill_aptitude' not in agent:
        agent['skill_aptitude'] = rng(engine, owner, 'aptitude', 'skill_aptitude').gauss(0, 1)
    from .attention import traits
    return exp(c['rho_skill'] * c['log_rate_sigma'] * agent['skill_aptitude'] + c['openness_link'] * (traits(agent)['O'] - .5))


def create(engine, owner, key, t, attrs=None):
    """A new skill at level 0 (lazy). A savings record from a pruned skill keeps its stability and practice count."""
    c = cfg(engine)
    label, key = key, normalize_label(key)
    a, defaulted = attributes(attrs)
    a = asdict(a)
    scale = stability_scale(c, a)
    alpha = rng(engine, owner, key, 'skill_rate').gammavariate(c['alpha_shape'], c['alpha_mean'] / c['alpha_shape'])
    s0 = rng(engine, owner, key, 'skill_stability').gammavariate(c['s0_shape'], c['s0_mean_days'] / c['s0_shape']) * scale
    saved = engine.agent(owner).get('skill_savings', {}).pop(key, None)
    origin = {'alpha': alpha, 'S0': s0, 'S': max(s0, saved['S']) if saved else s0, 'n_practice': saved['n_practice'] if saved else 0,
              't': t, 'ceiling': c['ceiling0']}
    state = SkillState(key, a, 0.0, t, origin['S'], alpha, s0, c['ceiling0'], n_practice=origin['n_practice'], created_at=t,
                       attrs_defaulted=defaulted, label=' '.join(str(label or key).split())[:60], origin=origin)
    store(engine, owner)[key] = asdict(state)
    return state


# Reading (pure)

def level(engine, owner, key, t=None):
    """Stored skill at t, in [0, 1). Unknown skill: 0. Never changes anything."""
    s = state_of(engine, owner, key)
    if s is None:
        return 0.0
    t = engine.day if t is None else t
    return s.L * exp(-max(0.0, t - s.t_last) / s.S)


def body_state(engine, owner, t):
    """(stress, sleep pressure) from the hormone module when it is on, else calm and rested."""
    if 'hormones' not in engine.state['config']:
        return 0.0, 0.0
    from . import hormones
    snap = hormones.read(engine, owner, t)
    return snap.stress, snap.sleep_pressure


def state_modifier(c, attrs, stress, sleep_pressure):
    """Sleep pressure and stress above their references lower performance, more for cognitive skills. No inverted U."""
    weight = .5 + .5 * attrs['cognitive']
    sleep = max(0.0, sleep_pressure - c['sleep_ref']) / max(1e-9, 1 - c['sleep_ref'])
    strain = max(0.0, stress - c['stress_ref']) / max(1e-9, 1 - c['stress_ref'])
    return min(1.0, max(1e-6, 1 - c['w_sleep'] * sleep * weight - c['w_stress'] * strain * weight))


def performance(engine, owner, key, t=None, ctx=None):
    """What the person can do right now: stored skill times the state modifier (stored skill is not changed)."""
    s = state_of(engine, owner, key)
    if s is None:
        return 0.0
    t = engine.day if t is None else t
    stress, sleep_pressure = ctx if ctx is not None else body_state(engine, owner, t)
    return level(engine, owner, key, t) * state_modifier(cfg(engine), s.attrs, stress, sleep_pressure)


def tier_of(c, value):
    for name, threshold in (('expert', c['tier_expert']), ('proficient', c['tier_proficient']), ('competent', c['tier_competent']),
                            ('novice', c['tier_novice'])):
        if value >= threshold:
            return name
    return 'none'


# Practice (the one place skill state changes)

def apply(state, entry, c):
    """One practice step on a state dict: pure, shared by live practice and log replay."""
    s = deepcopy(state)
    gap = max(0.0, entry['t'] - s['t_last'])
    R = exp(-gap / s['S'])
    L_now = s['L'] * R
    q, a = entry['q'], entry['a']
    savings = 1 + c['savings_gain'] * (1 - exp(-s['n_practice'] / c['savings_n'])) * (1 - R)
    mode_mult = c['mode_mult_' + entry['mode']]
    fb = {'task': c['feedback_task'], 'self': c['feedback_self'], 'none': 1.0}[entry['feedback']]
    alpha_eff = s['alpha'] * s['alpha_mult'] * entry['apt'] * q * a * mode_mult * fb * entry['boost'] * savings
    L_new = s['ceiling'] - (s['ceiling'] - L_now) * exp(-alpha_eff)
    scale = stability_scale(c, s['attrs'])
    S_new = min(c['s_max_days'] * scale, s['S'] * (1 + c['k_s'] * (1 - R) ** c['p_gap'] * c['mode_s_' + entry['mode']] * q * a))
    shifted = False
    if c['strategy_shift'] and q * a > 0:
        p_shift = 1 - exp(-c['h_shift'] * q * a * (1 - L_new))
        if entry['shift_u'] < p_shift:
            shifted = True
            s['segment'] += 1
            L_new *= 1 - c['dip']
            s['alpha_mult'] *= c['shift_boost']
            s['ceiling'] += (1 - s['ceiling']) * c['shift_ceiling_gain']
    effective = q * a > 0
    s.update(L=L_new, S=S_new, t_last=entry['t'], n_practice=s['n_practice'] + effective,
             n_retrieval=s['n_retrieval'] + (effective and entry['mode'] == 'retrieval'), n_success=s['n_success'] + bool(entry['success']))
    return s, {'level_before': L_now, 'level': L_new, 'shifted': shifted, 'alpha_eff': alpha_eff, 'stability': S_new}


def attention_for(engine, owner, t):
    """How much attention practice gets: the attention module's capacity (fatigue, dysregulation), lowered a little by
    anxiety; 1 without that module. shortcut: capacity of a lone, fully relevant stream, not a full allocation."""
    c = cfg(engine)
    from .attention import traits
    from .sleep import dials
    agent = engine.agent(owner)
    anxiety = (traits(agent)['N'] + dials(agent)['threat_sensitivity']) / 2  # [U] mapping of anxiety
    a = 1.0
    if 'attention' in engine.state['config']:
        from . import attention
        acfg = engine.state['config']['attention']
        a = attention.capacity(acfg, engine.mood(owner, t)['arousal'], attention.provider(engine, 'fatigue')(engine, owner, t), 0,
                               dials(agent)['dysregulation']) * attention.provider(engine, 'capacity_factor')(engine, owner, t)
    return max(0.0, min(1.0, a * (1 - c['anxiety_attention'] * anxiety)))


def transfer_boost(engine, owner, key, t):
    """Near transfer only: related skills (similarity at or above the cutoff) speed learning; below it, exactly none."""
    c = cfg(engine)
    best = 0.0
    for other in store(engine, owner):
        if other == key:
            continue
        sim = similarity(key, other)
        if sim >= c['transfer_similarity_cutoff']:
            best = max(best, sim * level(engine, owner, other, t))
    return 1 + c['transfer_gain'] * best


def practice(engine, owner, key, event_id, t=None, quality=1.0, attention=None, mode='retrieval', feedback='none', attrs=None):
    """A practice or exposure event: creates the skill if new, updates it, logs the inputs. Returns the step record."""
    from .engine import number
    c = cfg(engine)
    if mode not in MODES or feedback not in FEEDBACK:
        raise ValueError(f'mode is one of {MODES}; feedback one of {FEEDBACK}')
    key = normalize_label(key)
    if not key:
        raise ValueError('A skill needs a label')
    t = engine.day if t is None else t
    state = state_of(engine, owner, key) or create(engine, owner, key, t, attrs)
    a = attention_for(engine, owner, t) if attention is None else number(attention, 0, 1, 'attention')
    stress, sleep_pressure = body_state(engine, owner, t)
    record = asdict(state)
    L_now = record['L'] * exp(-max(0.0, t - record['t_last']) / record['S'])
    p_perform = L_now * state_modifier(c, record['attrs'], stress, sleep_pressure)
    entry = {'event': event_id, 't': t, 'q': number(quality, 0, 1, 'quality'), 'a': a, 'mode': mode, 'feedback': feedback,
             'apt': aptitude(engine, owner), 'boost': transfer_boost(engine, owner, key, t), 'p_perform': p_perform,
             'success': rng(engine, owner, event_id, 'practice_success').random() < p_perform,
             'shift_u': rng(engine, owner, event_id, 'strategy_shift').random()}
    new, step = apply(record, entry, c)
    if c['event_log_cap']:
        new['log'] = (new['log'] + [entry])[-int(c['event_log_cap']):]
    store(engine, owner)[key] = new
    prune(engine, owner, t, keep=key)
    return {**step, 'key': key, 'success': entry['success'], 'attention': a}


def set_level(engine, owner, key, value, t=None):
    """A researcher sets the stored level now (an intervention, logged by visit.apply_edit). Stability and history stay;
    the replay record restarts from here so the log still reproduces the state."""
    t = engine.day if t is None else t
    state = state_of(engine, owner, key) or create(engine, owner, key, t)
    record = asdict(state)
    record.update(L=float(value), t_last=t, log=[])
    record['origin'] = {k: record[k] for k in ('alpha', 'S0', 'S', 'n_practice', 'ceiling', 'L', 'segment', 'alpha_mult',
                                                'n_retrieval', 'n_success')} | {'t': t}
    store(engine, owner)[state.key] = record


def expose(engine, owner, key, t=None, attrs=None):
    """Meeting a skill (seeing it, being taught): it exists at level 0, with no stability bonus [U]."""
    key = normalize_label(key)
    return state_of(engine, owner, key) or create(engine, owner, key, engine.day if t is None else t, attrs)


def replay(state, c):
    """Recompute a skill from its creation values and its event log (audit). Equals the stored state while the log
    holds every event (event_log_cap not reached)."""
    o = state['origin']
    s = asdict(SkillState(state['key'], state['attrs'], o.get('L', 0.0), o['t'], o['S'], o['alpha'], o['S0'], o['ceiling'],
                          segment=o.get('segment', 0), alpha_mult=o.get('alpha_mult', 1.0), n_practice=o['n_practice'],
                          n_retrieval=o.get('n_retrieval', 0), n_success=o.get('n_success', 0), created_at=state['created_at'],
                          attrs_defaulted=state['attrs_defaulted'], label=state.get('label', ''), origin=o))
    for entry in state['log']:
        s, _ = apply(s, entry, c)
    s['log'] = list(state['log'])
    return s


def prune(engine, owner, t, keep=None):
    """Long-unused, faded skills become savings records; over the cap, the least important ones do too."""
    c = cfg(engine)
    skills = store(engine, owner)
    savings = engine.agent(owner).setdefault('skill_savings', {})
    def to_savings(k):
        s = skills.pop(k)
        savings[k] = {'key': k, 'S': s['S'], 't_last': s['t_last'], 'n_practice': s['n_practice']}
    for k in [k for k, s in skills.items() if k != keep and level(engine, owner, k, t) < c['eps_level']
              and t - s['t_last'] > c['eps_recency_days']]:
        to_savings(k)
    while len(skills) > c['max_skills_per_agent']:
        k = min((k for k in skills if k != keep), key=lambda k: (level(engine, owner, k, t) + .01 * skills[k]['n_practice'], k))
        to_savings(k)


# Expression

def competence_check(engine, owner, key, difficulty, event_id, t=None, ctx=None):
    """Ground truth for an attempt: tier and pass/fail decided here, never by the model. Logged."""
    from .engine import number
    c = cfg(engine)
    key = normalize_label(key)
    t = engine.day if t is None else t
    perf = performance(engine, owner, key, t, ctx)
    noisy = min(1.0, max(0.0, perf + rng(engine, owner, event_id, 'competence_noise').gauss(0, c['competence_noise']))) if perf else 0.0
    result = {'skill': key, 'tier': tier_of(c, noisy), 'performance': noisy, 'passed': noisy >= number(difficulty, 0, 1, 'difficulty')}
    engine.state.setdefault('skill_checks', []).append({'day': t, 'owner': owner, 'event': event_id, 'difficulty': difficulty,
                                                       'stored_level': level(engine, owner, key, t), **result})
    return result


def skill_directive(c, tier, passed=None):
    """Short text for an existing prompt. Below the threshold it describes not knowing; it never asks for wrong content [U]."""
    text = c['tier_text'][tier]
    if passed is False and tier != 'none':
        text += ' This attempt does not go well.'
    return text


def calibrate_sigma(c, n=4000):
    """Self-assessment noise such that perceived (clipped) and true skill correlate at r_self in a reference population
    of uniform true levels, for a new skill with neutral feedback clarity [D, E22]."""
    rng_ = Random(29)
    true = [rng_.random() for _ in range(n)]
    z = [rng_.gauss(0, 1) for _ in range(n)]
    neutral = 1 - c['clarity_noise_cut'] * .5
    def corr(sigma):
        seen = [min(1.0, max(0.0, x + sigma * neutral * e)) for x, e in zip(true, z)]
        mx, my = sum(true) / n, sum(seen) / n
        cov = sum((a - mx) * (b - my) for a, b in zip(true, seen))
        vx, vy = sum((a - mx) ** 2 for a in true), sum((b - my) ** 2 for b in seen)
        return cov / (vx * vy) ** .5 if vy else 0.0
    low, high = 0.0, 50.0
    for _ in range(60):
        mid = (low + high) / 2
        low, high = (mid, high) if corr(mid) > c['r_self'] else (low, mid)
    return (low + high) / 2


def perceived(engine, owner, key, event_id, t=None):
    """How good the person thinks they are: true level plus seeded noise, smaller for familiar skills and clear feedback.
    No built-in overconfidence (E23 contested)."""
    c = cfg(engine)
    s = state_of(engine, owner, key)
    true = level(engine, owner, key, t)
    familiar = 1 - exp(-(s.n_practice if s else 0) / c['savings_n'])
    clarity = s.attrs['feedback_clarity'] if s else .5
    sigma = c['sigma_self'] * (1 - c['familiar_noise_cut'] * familiar) * (1 - c['clarity_noise_cut'] * clarity)
    return min(1.0, max(0.0, true + sigma * rng(engine, owner, event_id, 'perceived_noise').gauss(0, 1)))


def context(engine, owner, limit=6):
    """For the existing prompt: what the person can do, by tier, with the not-knowing rule for everything else [U]."""
    c = cfg(engine)
    skills = store(engine, owner)
    rows = sorted(((performance(engine, owner, k), k) for k in skills), reverse=True)[:limit]
    known = {skills[k].get('label') or k: skill_directive(c, tier_of(c, p)) for p, k in rows if tier_of(c, p) != 'none'}
    return {'what_you_can_do': known, 'anything_else': skill_directive(c, 'none')}


def validate_option_skill(skill):
    """A situation option's skill: {key, difficulty, optional attrs, mode, feedback}."""
    from .engine import number
    if not isinstance(skill, dict) or set(skill) - {'key', 'difficulty', 'attrs', 'mode', 'feedback'} or not normalize_label(skill.get('key', '')):
        raise ValueError('An option skill needs a key (a short label) and may give difficulty, attrs, mode and feedback')
    number(skill.get('difficulty', .5), 0, 1, 'skill difficulty')
    attributes(skill.get('attrs'))
    if skill.get('mode', 'retrieval') not in MODES or skill.get('feedback', 'none') not in FEEDBACK:
        raise ValueError(f'skill mode is one of {MODES}; feedback one of {FEEDBACK}')


def attempt(engine, owner, skill, event_id):
    """An option that exercises a skill: the competence check decides success (ground truth) and the attempt is practice."""
    check = competence_check(engine, owner, skill['key'], skill.get('difficulty', .5), event_id)
    step = practice(engine, owner, skill['key'], event_id, mode=skill.get('mode', 'retrieval'), feedback=skill.get('feedback', 'none'),
                    attrs=skill.get('attrs'))
    return check, step


# Choosing to practise (the hormone module's wanting; no initiation or abandonment hazards)

def practice_wanting(engine, owner, keys):
    """W for practice targets: learned value of 'skill:<key>' (when hormones are on) plus conscientiousness (motivation,
    never rate) minus anxiety (motivation). Abandonment emerges when repeated failure lowers the learned value."""
    from .attention import traits
    from .sleep import dials
    c = cfg(engine)
    agent = engine.agent(owner)
    trait, dial = traits(agent), dials(agent)
    nudge = c['conscientiousness_motivation'] * (trait['C'] - .5) - c['anxiety_motivation'] * ((trait['N'] + dial['threat_sensitivity']) / 2 - .25)
    targets = {k: 'skill:' + normalize_label(k) for k in keys}
    if 'hormones' in engine.state['config']:
        from . import hormones
        values = hormones.wanting_scores(engine, owner, list(targets.values()))
        return {k: values[target] + nudge for k, target in targets.items()}
    return {k: nudge for k in keys}


# Sensitivity

def sensitivity_sweep(scenario, grid, base=None):
    """Rerun scenario(overrides) -> {outcome: number} across a grid of [U] parameters (one at a time) and report each
    outcome's range, so placeholders are visibly not driving conclusions."""
    base = base or {}
    report = {}
    for name, values in grid.items():
        results = [scenario({**base, name: v}) for v in values]
        report[name] = {outcome: [min(r[outcome] for r in results), max(r[outcome] for r in results)] for outcome in results[0]}
    return report
