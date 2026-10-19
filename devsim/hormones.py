"""Hormone-state module: exactly three per-agent variables, advanced lazily in closed form.

  stress_x        phasic stress (cortisol-like, slow); the readout S = 1 - exp(-(baseline + phasic)) lies in [0, 1).
                  The baseline is not stored: it is a closed-form function of time since waking (awakening rise, then a
                  diurnal decline; the floor while asleep).
  sleep_pressure  Process S in [0, 1]: rises while awake, drains while asleep (two-process model), with a seeded
                  circadian term for sleep_drive. Sleep and wake times come from the sleep module's night schedule.
  dopamine_tonic  leaky integral of reward prediction error (unbounded; read through tanh).

Per-target expectations V(target) are memory, not hormone state: a lazily created dict on the agent, updated by a
Rescorla-Wagner rule. Bonding comes from society-layer closeness in the wanting score; there is no fourth variable.

Lazy and event-driven: the state is (value, anchor time) per field and is advanced only when read or when an event
reaches the agent, at O(1) cost in the number of agents. No model calls. One code path for everyone: differences come
from Big Five traits, the four dials, seeded per-agent parameters and current state. Every random draw is seeded from
(world seed, agent, event or night, purpose). Every constant is tagged in devsim/policies/hormones.json; see
docs/hormone_evidence.md and docs/hormone_design.md.
"""
from dataclasses import asdict, dataclass, fields, replace
import json
from math import cos, exp, floor, pi, tanh
from statistics import NormalDist

from . import POLICY_DIR

CONFIG_PATH = POLICY_DIR / 'hormones.json'
TIER_WEIGHT_FULL = 1.0


@dataclass(frozen=True)
class Level:
    value: float
    anchor: float


@dataclass(frozen=True)
class HormoneState:
    """Exactly three fields (a check fails on any other count)."""
    stress_x: Level
    sleep_pressure: Level
    dopamine_tonic: Level


@dataclass(frozen=True)
class Snapshot:
    t: float
    stress: float           # S in [0, 1)
    stress_x: float         # baseline + phasic
    phasic: float
    baseline: float
    sleep_pressure: float   # P in [0, 1]
    circadian: float        # C in [-1, 1]
    sleep_drive: float      # P + c_amp C
    dopamine_tonic: float   # D (unbounded)
    dopamine: float         # tanh(D - D0)
    asleep: bool
    wake_anchor: float | None


# Config

def parameters():
    data = json.loads(CONFIG_PATH.read_text())
    return data['parameters'], data['style']


def configure(engine, overrides=None):
    """Store the full hormone policy in the world config (checkpointed). Worlds without it are unchanged."""
    from .engine import number
    spec, style = parameters()
    overrides = overrides or {}
    if not isinstance(overrides, dict) or set(overrides) - set(spec):
        raise ValueError('Unsupported hormone setting')
    settings = {key: overrides.get(key, item['value']) for key, item in spec.items()}
    for key, item in spec.items():
        if 'choices' in item:
            if settings[key] not in item['choices'] or type(settings[key]) is not type(item['value']):
                raise ValueError(f'{key} must be one of {item["choices"]}')
        else:
            number(settings[key], *item['range'], key)
    if not settings['style_S_mild'] < settings['style_S_strong']:
        raise ValueError('Need style_S_mild < style_S_strong')
    settings['style'] = style
    current = engine.state['config'].get('hormones')
    if current is not None and current != settings:
        raise ValueError('Cannot silently replace hormone policy')
    engine.state['config']['hormones'] = settings


def enabled(engine):
    return 'hormones' in engine.state['config']


def gauss(*parts):
    """A seeded standard normal from the parts (no shared random state)."""
    from .attention import unit
    return NormalDist().inv_cdf(unit(*parts))


# Per-agent context: everything advance() needs, from traits, dials, seeded parameters and the schedule

def context(engine, owner):
    from .attention import traits
    from .sleep import dials, night
    p = engine.state['config']['hormones']
    agent = engine.agent(owner)
    trait, dial = traits(agent), dials(agent)
    seed = engine.state.get('seed')
    shift = dial['mood_baseline_shift']
    return {
        'p': p, 'seed': seed, 'owner': owner, 'traits': trait, 'dials': dial,
        'night': night(engine, owner) if 'household' in engine.state['config'] else None,
        'wake_fallback': agent.get('sleep', {}).get('wake_day', agent['birth_day']),
        'b_floor': p['b_floor'] + p['b_mood_shift'] * max(0.0, -shift),
        'tau_s': p['tau_s_h'] * (1 + p['dys_tau'] * dial['dysregulation']) / 24,
        'g_s': p['g_s'] * (1 + p['dys_gain'] * dial['dysregulation'])
               * exp(p['reactivity_sigma'] * gauss(seed, owner, 'trait', 'stress_reactivity')),
        'D0': p['d0'] + p['d_mood_shift'] * shift,
        'chronotype_h': p['chronotype_sd_h'] * gauss(seed, owner, 'trait', 'chronotype'),
    }


def initial(ctx, t):
    return HormoneState(Level(0.0, t), Level(ctx['p']['P_start'], t), Level(ctx['D0'], t))


# Schedule: sleep periods from the routine's night, with a seeded, stress-dependent onset latency

def nights(ctx, start, end):
    """(night start, night end) for every night overlapping [start, end], oldest first."""
    if ctx['night'] is None:
        return []
    hour, length = ctx['night']
    first = floor(start) - 1
    found = []
    for day in range(first, floor(end) + 1):
        a = day + hour / 24
        b = a + length / 24
        if b > start and a < end:
            found.append((a, b))
    return found


def last_wake(ctx, t):
    """End of the latest night that ended by t, or the fallback (the sleep module's wake time) without a routine."""
    if ctx['night'] is None:
        return ctx['wake_fallback']
    hour, length = ctx['night']
    end = floor(t - (hour + length) / 24) + (hour + length) / 24
    return end if end <= t else end - 1


def baseline(ctx, t, asleep):
    """Wake-anchored stress baseline: floor + diurnal decline + an awakening rise peaking tau_car after waking."""
    p = ctx['p']
    if asleep:
        return ctx['b_floor']
    gap = max(0.0, (t - last_wake(ctx, t)) * 24)
    return (ctx['b_floor'] + p['A_day'] * exp(-gap / p['tau_day_h'])
            + p['A_car'] * (gap / p['tau_car_h']) * exp(1 - gap / p['tau_car_h']))


def phasic_at(state, ctx, t):
    """Phasic stress at t from the stored anchor (also backwards, for a night that began before the anchor)."""
    return state.stress_x.value * exp(-(t - state.stress_x.anchor) / ctx['tau_s'])


def onset(state, ctx, night_start, night_end):
    """(sleep onset, efficiency) for one night: stress at bedtime slows onset and lowers efficiency (wired flag)."""
    p = ctx['p']
    s = 1 - exp(-(baseline(ctx, night_start, False) + phasic_at(state, ctx, night_start)))
    mean = p['L0_min']
    if p['wired_override']:
        mean += p['L_k_min'] * max(0.0, s - p['S_wired']) ** p['wired_power']
    from .attention import unit
    u = unit(ctx['seed'], ctx['owner'], f'night:{night_start!r}', 'onset_latency')
    latency = mean * (1 - p['latency_spread'] + 2 * p['latency_spread'] * u) / 1440
    efficiency = 1 - p['k_eff'] * s if p['wired_override'] else 1.0
    return min(night_start + latency, night_start + .8 * (night_end - night_start)), efficiency


def sleep_periods(state, ctx, start, end):
    """(asleep from, asleep until, efficiency) overlapping [start, end]."""
    periods = []
    for a, b in nights(ctx, start, end):
        begin, efficiency = onset(state, ctx, a, b)
        if b > start and begin < end:
            periods.append((begin, b, efficiency))
    return periods


def asleep_at(state, ctx, t):
    return any(a <= t < b for a, b, _ in sleep_periods(state, ctx, t, t + 1e-9))


def pressure(state, ctx, t):
    """Process S from the anchor to t: saturating rise awake, exponential drain asleep (scaled by efficiency)."""
    p = ctx['p']
    level, u = state.sleep_pressure.value, state.sleep_pressure.anchor
    for a, b, efficiency in sleep_periods(state, ctx, u, t):
        a, b = max(a, u), min(b, t)
        if a > u:
            level = 1 - (1 - level) * exp(-(a - u) * 24 / p['tau_rise_h'])
        level *= exp(-efficiency * (b - a) * 24 / p['tau_decay_h'])
        u = b
    if t > u:
        level = 1 - (1 - level) * exp(-(t - u) * 24 / p['tau_rise_h'])
    return min(1.0, max(0.0, level))


# The two required pure functions

def advance(state, t, ctx):
    """State at t >= every anchor, with no events in between; advance(advance(s, t1), t2) == advance(s, t2)."""
    p = ctx['p']
    phasic = phasic_at(state, ctx, t)
    d = ctx['D0'] + (state.dopamine_tonic.value - ctx['D0']) * exp(-(t - state.dopamine_tonic.anchor) * 24 / p['tau_d_h'])
    return HormoneState(Level(phasic, t), Level(pressure(state, ctx, t), t), Level(d, t))


def snapshot(state, ctx, t):
    p = ctx['p']
    now = advance(state, t, ctx)
    sleeping = asleep_at(state, ctx, t)
    base = baseline(ctx, t, sleeping)
    x = base + now.stress_x.value
    hour = (t - floor(t)) * 24
    circadian = cos(2 * pi * (hour - p['circadian_peak_hour'] - ctx['chronotype_h']) / 24)
    return Snapshot(t, 1 - exp(-x), x, now.stress_x.value, base, now.sleep_pressure.value, circadian,
                    now.sleep_pressure.value + p['c_amp'] * circadian, now.dopamine_tonic.value,
                    tanh(now.dopamine_tonic.value - ctx['D0']), sleeping, None if sleeping else last_wake(ctx, t))


# Storage on the agent

def load(engine, owner):
    record = engine.agent(owner).get('hormones')
    ctx = context(engine, owner)
    if record is None:
        return initial(ctx, engine.state['runtime']['start_day'] if 'runtime' in engine.state else engine.day), ctx
    return HormoneState(*(Level(*record[f.name]) for f in fields(HormoneState))), ctx


def store(engine, owner, state):
    engine.agent(owner)['hormones'] = {f.name: [getattr(state, f.name).value, getattr(state, f.name).anchor]
                                       for f in fields(HormoneState)}


def read(engine, owner, t=None):
    """Snapshot at t (default now). Read-only."""
    state, ctx = load(engine, owner)
    t = engine.day if t is None else t
    return snapshot(state, ctx, max(t, max(getattr(state, f.name).anchor for f in fields(HormoneState))))


# Events

def appraisal(obs):
    """Default appraisal provider from the event's own appraisal: valence, threat, controllability."""
    valence = obs.get('valence', 0.0)
    return {'valence': valence, 'threat': max(0.0, -valence) * obs.get('arousal', 0.0),
            'controllability': obs.get('controllability', 0.5)}


def stress_increment(ctx, snap, appraised, arousal, surprise, exposures):
    """Delta x for one event, computed once at the event."""
    p, dial = ctx['p'], ctx['dials']
    threat = appraised['threat'] * (1 + p['k_controllability'] * (0.5 - appraised['controllability']))
    threat += p['rt_bias'] * (1 - dial['reality_testing']) * max(0.0, 1 - threat) * arousal
    gain = ctx['g_s'] * (1 + p['lambda_p'] * snap.sleep_pressure if p['sleep_dep_reactivity'] else 1)
    return (gain * max(0.0, threat) * (1 + p['theta_ts'] * dial['threat_sensitivity']) * (1 + p['theta_n'] * ctx['traits']['N'])
            * (1 + p['g_novelty'] * surprise) / (1 + exposures) ** p['habituation_power'] * (1 - snap.stress))


def tier_weight(p, result):
    """How much an outcome teaches: FULL 1, GIST gist_weight, NONE 0; 1 without the attention module."""
    if result is None:
        return TIER_WEIGHT_FULL
    return {'FULL': TIER_WEIGHT_FULL, 'GIST': p['gist_weight'], 'NONE': 0.0}[result.tier]


def targets(engine, owner, event, obs):
    """What this outcome is about: the person it came from, the group of a group talk, or a named activity."""
    found = []
    if obs['source'] in engine.state['entities'] and obs['source'] != owner:
        found.append(obs['source'])
    if event['id'].startswith('@conversation:'):
        talk = engine.state.get('runtime', {}).get('conversations', {}).get(event['id'].split(':')[1], {})
        if talk.get('spec', {}).get('group'):
            found.append('group:' + talk['spec']['group'])
    if obs.get('outcome_target'):
        found.append(obs['outcome_target'])
    return found


def expectation(engine, owner, target, ctx):
    """V(target) and exposures; a new target starts at an openness-raised prior."""
    record = engine.agent(owner).get('expectations', {}).get(target)
    if record is None:
        return ctx['p']['v0'] + ctx['p']['n_open'] * ctx['traits']['O'], 0
    return record['V'], record['n']


def learn(engine, owner, target, reward, weight, ctx):
    """One Rescorla-Wagner step; returns the prediction error. weight 0 (not attended) learns nothing."""
    v, n = expectation(engine, owner, target, ctx)
    delta = reward - v
    engine.agent(owner).setdefault('expectations', {})[target] = {'V': v + ctx['p']['alpha'] * weight * delta,
                                                                   'n': n + (weight > 0)}
    return delta


def on_event(engine, owner, event, obs, result=None):
    """Called once per (agent, delivered event) from Engine.advance. O(1) in the number of agents."""
    from .attention import provider
    state, ctx = load(engine, owner)
    p = ctx['p']
    t = max(event['day'], *(getattr(state, f.name).anchor for f in fields(HormoneState)))
    snap = snapshot(state, ctx, t)
    now = advance(state, t, ctx)
    surprise = provider(engine, 'surprise')(engine, owner, None) if 'attention' in engine.state['config'] else 0.0
    dx = stress_increment(ctx, snap, appraisal(obs), obs.get('arousal', 0.0), surprise, obs.get('exposures', 0))
    weight = tier_weight(p, result)
    reward = max(-1.0, min(1.0, obs.get('valence', 0.0))) * (1 + p['rho_k'] * snap.dopamine)
    errors = [learn(engine, owner, target, reward, weight, ctx)
              for target in targets(engine, owner, event, obs)]
    d = now.dopamine_tonic.value + p['eta'] * weight * (sum(errors) / len(errors) if errors else 0.0)
    store(engine, owner, replace(now, stress_x=Level(now.stress_x.value + dx, t), dopamine_tonic=Level(d, t)))
    return {'S': snap.stress, 'dx': dx, 'rpe': errors, 'weight': weight}


# Readouts (no new state)

def capacity_factor(engine, owner, t):
    """Attention capacity multiplier from arousal (S and event load); 1 unless arousal_form is set (default off)."""
    p = engine.state['config']['hormones']
    if p['arousal_form'] == 'off':
        return 1.0
    a = arousal(engine, owner, t)
    if p['arousal_form'] == 'monotone':
        return 1 - p['k_mono'] * a
    return max(0.0, 1 - p['kappa_u'] * (a - .5) ** 2)


def arousal(engine, owner, t):
    p = engine.state['config']['hormones']
    load = len(engine.agent(owner).get('attention_state', {}).get('streams', {}))
    return min(1.0, p['arousal_s'] * read(engine, owner, t).stress + p['arousal_load'] * min(1.0, load / p['load_ref']))


def fatigue(engine, owner, t):
    return read(engine, owner, t).sleep_pressure


def mood_scale(engine, meta, valence):
    """Negative mood impulses grow with stress at the event: (1 + lambda_s S)."""
    record = meta.get('hormones')
    if record is None or valence >= 0:
        return 1.0
    return 1 + engine.state['config']['hormones']['lambda_s'] * record['S']


def mood_offset(engine, owner, t):
    """Mood baseline offset: beta_d (D - D0) - beta_s (S - S0)."""
    p = engine.state['config']['hormones']
    _, ctx = load(engine, owner)
    snap = read(engine, owner, t)
    return p['beta_d'] * (snap.dopamine_tonic - ctx['D0']) - p['beta_s'] * (snap.stress - p['S0'])


def style_level(p, stress):
    """0, 1 or 2; never decreases as stress rises."""
    return 2 if stress >= p['style_S_strong'] else 1 if stress >= p['style_S_mild'] else 0


def style_directive(p, snap, mood_valence=0.0):
    """Text for the existing prompt. Stress: simpler, more fragmented phrasing with pauses and fillers; length is
    left neutral by default. High sleep pressure: flatter feeling, slower to respond."""
    style = p['style']
    lines = []
    level = style_level(p, snap.stress)
    if level:
        lines += [style['stress_strong' if level == 2 else 'stress_mild'], style['length_' + p['length_bias']]]
    if snap.sleep_pressure >= p['style_P'] and not snap.asleep:
        lines.append(style['tired'])
    if p['first_person_low_mood'] and mood_valence <= p['low_mood']:
        lines.append(style['first_person'])
    return ' '.join(lines)


# Decisions (the caller passes the candidates; nothing here iterates over agents)

def closeness(engine, owner, target):
    if target not in engine.state['agents']:
        return 0.0
    from .attention import provider
    if 'attention' not in engine.state['config']:
        return max(0.0, engine.agent(owner)['relationships'].get(target, {}).get('closeness', 0.0))
    return provider(engine, 'closeness')(engine, owner, target)


def wanting_scores(engine, owner, candidates, t=None):
    """W(target) = V + kappa_c closeness + novelty bonus N0 exp(-exposures / tau_n)."""
    state, ctx = load(engine, owner)
    p = ctx['p']
    scores = {}
    for target in candidates:
        v, n = expectation(engine, owner, target, ctx)
        scores[target] = v + p['kappa_c'] * closeness(engine, owner, target) + p['N0'] * exp(-n / p['tau_n'])
    return scores


def initiative(engine, owner, t=None):
    """Multiplier on the rate or score of starting interactions: 1 + initiative_k tanh(D - D0)."""
    p = engine.state['config']['hormones']
    return 1 + p['initiative_k'] * read(engine, owner, t).dopamine


def temperature(engine, owner, t=None):
    p = engine.state['config']['hormones']
    if not p['stress_exploration_link']:
        return p['T0']
    return p['T0'] * (1 + p['lambda_T'] * read(engine, owner, t).stress)


def choose(engine, owner, candidates, event_id, t=None):
    """Softmax choice over wanting scores, seeded by (agent, event, purpose)."""
    from .attention import unit
    scores = wanting_scores(engine, owner, candidates, t)
    T = temperature(engine, owner, t)
    top = max(scores.values())
    weights = {k: exp((v - top) / T) for k, v in sorted(scores.items())}
    pick = unit(engine.state.get('seed'), owner, event_id, 'target_choice') * sum(weights.values())
    for key, w in weights.items():
        pick -= w
        if pick <= 0:
            return key
    return key


def leave_chance(engine, owner, current, alternatives, t=None):
    """Chance of leaving `current` at a decision event: rises once the best alternative beats it by the margin."""
    p = engine.state['config']['hormones']
    scores = wanting_scores(engine, owner, [current, *alternatives], t)
    gap = max((scores[a] for a in alternatives), default=scores[current]) - scores[current] - p['leave_margin']
    return min(1.0, p['leave_h0'] * max(0.0, gap))


# Sleep-module interface

def sleep_onset_latency(engine, owner, night_start):
    """Minutes from going to bed to sleep for the night starting at night_start."""
    state, ctx = load(engine, owner)
    hour, length = ctx['night'] or (0, 8)
    begin, _ = onset(state, ctx, night_start, night_start + length / 24)
    return (begin - night_start) * 1440


def sleep_efficiency(engine, owner, wake):
    """Efficiency of the night ending at `wake` (1 without a routine)."""
    state, ctx = load(engine, owner)
    if ctx['night'] is None:
        return 1.0
    hour, length = ctx['night']
    return onset(state, ctx, wake - length / 24, wake)[1]


def describe(engine, owner, t=None):
    """A plain dict for watchers and reports."""
    return asdict(read(engine, owner, t))
