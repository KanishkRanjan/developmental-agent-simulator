"""Attention allocation: how much of a delivered event each listener actually takes in.

This is psychological attention, not the transformer kind. Capacity theory (Kahneman 1973): attention is a
limited, shared resource, allocated by momentary intentions and enduring dispositions. An event's weight a
(0-1) and tier (FULL, GIST, NONE) decide how it is encoded, how much it moves mood, and how it appears in the
agent's model context. Every number is a tunable design default; see devsim/policies/attention.json and
docs/attention_evidence.md for the evidence tag on each.

Lazy and event-driven: allocate() runs once per (listener, event), from Engine.advance only. Nothing runs per
tick; stale streams are dropped when the agent's state is next read. No model calls, and no branch on agent type:
differences come from Big Five traits, the four dials, mood and arousal. Noise is seeded per
(world seed, agent, event, purpose), so results do not depend on evaluation order.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from math import exp, log
import re

from . import POLICY_DIR

CONFIG_PATH = POLICY_DIR / 'attention.json'
TAGS = ('social', 'novelty_ideas', 'threat', 'conflict', 'distress', 'task_duty', 'gossip', 'romance', 'money', 'family')
TRAITS = tuple('OCEAN')
FULL, GIST, NONE = 'FULL', 'GIST', 'NONE'
UNATTENDED = 'unattended'  # memory tier of a NONE event: a hidden receipt, like sleep's 'dropped'
WEIGHTS = ('w_topic', 'w_rel', 'w_ment', 'w_goal')
MINUTES_PER_DAY = 1440
PHRASES = {'social': 'everyday things', 'novelty_ideas': 'an idea', 'threat': 'something alarming',
           'conflict': 'a disagreement', 'distress': 'someone being upset', 'task_duty': 'work or duties',
           'gossip': 'other people', 'romance': 'romance', 'money': 'money', 'family': 'family'}


def parameters():
    return json.loads(CONFIG_PATH.read_text())['parameters']


def configure(engine, overrides=None):
    """Store the full attention policy in the world config (checkpointed). Worlds without it are unchanged."""
    spec = parameters()
    overrides = overrides or {}
    if not isinstance(overrides, dict) or set(overrides) - set(spec):
        raise ValueError('Unsupported attention setting')
    settings = {key: deepcopy(overrides.get(key, item['value'])) for key, item in spec.items()}
    validate(settings, spec)
    current = engine.state['config'].get('attention')
    if current is not None and current != settings:
        raise ValueError('Cannot silently replace attention policy')
    engine.state['config']['attention'] = settings


def validate(settings, spec=None):
    """Fail fast: ranges and choices, weights summing to 1, a_gist < a_full, and well-formed tag tables."""
    from .engine import number
    spec = spec or parameters()
    for key, item in spec.items():
        value = settings[key]
        if 'choices' in item:
            if value not in item['choices'] or type(value) is not type(item['value']):
                raise ValueError(f'{key} must be one of {item["choices"]}')
        elif 'range' in item:
            number(value, *item['range'], key)
    if abs(sum(settings[w] for w in WEIGHTS) - 1) > 1e-9:
        raise ValueError('Top-down weights w_topic, w_rel, w_ment and w_goal must sum to 1')
    if not settings['a_gist'] < settings['a_full']:
        raise ValueError('Need a_gist < a_full')
    def tag_numbers(table, low, high, label, keys=TAGS):
        if not isinstance(table, dict) or set(table) - set(keys):
            raise ValueError(f'{label} must map known names to numbers')
        for value in table.values():
            number(value, low, high, label)
    tag_numbers(settings['affinity_base'], 0, 1, 'affinity_base')
    if set(settings['affinity_base']) != set(TAGS):
        raise ValueError('affinity_base needs every tag')
    if not isinstance(settings['loadings'], dict) or set(settings['loadings']) - set(TAGS):
        raise ValueError('loadings must map tags to trait loadings')
    for row in settings['loadings'].values():
        tag_numbers(row, -2, 2, 'loadings', TRAITS)
    rules = settings['topic_rules']
    if not isinstance(rules, dict) or set(rules) - set(TAGS) or not all(
            isinstance(words, list) and all(isinstance(w, str) and w == w.lower() and w for w in words) for words in rules.values()):
        raise ValueError('topic_rules must map tags to lists of lowercase words')
    if not isinstance(settings['event_tags'], dict):
        raise ValueError('event_tags must map event id prefixes to tag weights')
    for row in settings['event_tags'].values():
        tag_numbers(row, 0, 1, 'event_tags')


# Inputs

@dataclass
class EventView:
    """What the allocator needs from one delivered observation (built by event_view)."""
    event_id: str
    actor_id: str | None
    stream_id: str
    mentioned_ids: list
    topic_tags: dict
    threat_salience: float
    addressed_ids: list
    timestamp: float


@dataclass
class AttentionResult:
    weight: float
    tier: str
    top_down: float = 1.0
    bottom_up: float = 0.0
    capacity: float = 1.0
    share: float = 1.0
    captured: bool = False
    drifted: bool = False
    addressed: bool = False
    may_skip_response: bool = False  # 5.4 hook for a later response gate: NONE or GIST and not addressed
    reasons: dict = field(default_factory=dict)


def stream_of(event_id):
    """Conversation or call the event belongs to; a one-off event is its own stream."""
    for prefix in ('@conversation:', '@call:'):
        if event_id.startswith(prefix):
            return prefix[1:] + event_id[len(prefix):].split(':')[0]
    return event_id


def topic_tags(engine, event_id, obs):
    """(tag weights, neutral?) from authored topic_tags, else the event-type and keyword rule tables."""
    if 'topic_tags' in obs:
        tags = obs['topic_tags']
        if not isinstance(tags, dict) or set(tags) - set(TAGS) or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1 for v in tags.values()):
            raise ValueError('topic_tags must map known tags to weights in [0, 1]')
        return {t: float(tags.get(t, 0)) for t in TAGS}, False
    cfg = engine.state['config']['attention']
    tags = dict.fromkeys(TAGS, 0.0)
    for prefix, weights in cfg['event_tags'].items():
        if event_id.startswith(prefix):
            for tag, weight in weights.items():
                tags[tag] = max(tags[tag], weight)
    words = set(re.findall(r"[a-z']+", obs['text'].lower()))
    for tag, keywords in cfg['topic_rules'].items():
        if words.intersection(keywords):
            tags[tag] = max(tags[tag], cfg['keyword_tag_weight'])
    if not any(tags.values()):
        return dict.fromkeys(TAGS, cfg['neutral_tag_weight']), True
    return tags, False


def event_view(engine, owner, event, obs):
    entities = engine.state['entities']
    actor = obs['source'] if obs['source'] in entities and obs['source'] != owner else None
    mentioned = [*obs.get('references', []), *(m['resolved_id'] for m in obs.get('mentions', []) if m.get('resolved_id'))]
    tags, neutral = topic_tags(engine, event['id'], obs)
    stats = engine.state.setdefault('attention_stats', {'allocations': 0, 'neutral_tags': 0})
    stats['neutral_tags'] += neutral
    # Threat comes from metadata, else the listener's own appraisal (so it is post hoc, not pre-attentive).
    threat = obs.get('threat_salience', max(0.0, -obs.get('valence', 0)) * obs.get('arousal', 0))
    return EventView(event['id'], actor, stream_of(event['id']), list(dict.fromkeys(mentioned)), tags, threat,
                     list(obs.get('addressed', [])), event['day'])


# Providers: callables (engine, ...) that return 0-1. Override any of them with engine.attention_providers[name];
# the defaults are safe until the relationship, surprise, fatigue and goal modules supply real signals.

def default_closeness(engine, i, j):
    cfg = engine.state['config']['attention']
    agent = engine.agent(i)
    record = agent['relationships'].get(j)
    if record is not None:
        if 'society' in engine.state['config']:
            from . import society
            record = society.relationship(engine, record)
        # shortcut: encounters create relationships at closeness 0, so 0 reads as "known, unrated", not distant.
        return record['closeness'] if record.get('closeness', 0) > 0 else cfg['closeness_known']
    return cfg['closeness_known'] if j in agent['references'] else cfg['closeness_stranger']


PROVIDERS = {'closeness': default_closeness,
             'surprise': lambda engine, i, view: 0.0,
             'fatigue': lambda engine, i, now: 0.0,
             'asleep': lambda engine, i, now: False,
             'goal_match': lambda engine, i, view: 0.0}


def provider(engine, name):
    return getattr(engine, 'attention_providers', {}).get(name, PROVIDERS[name])


# The model

def clip(x, low=0.0, high=1.0):
    return min(high, max(low, x))


def traits(agent):
    """Big Five domains in [0, 1] from the six 0-100 facets of each."""
    return {d: sum(agent['facets'][d + str(k)] for k in range(1, 7)) / 600 for d in TRAITS}


def affinity(cfg, trait):
    """4.1: enduring topic dispositions, clip(base + sum of loading x (trait - 0.5))."""
    return {tag: clip(cfg['affinity_base'][tag] + sum(w * (trait[t] - .5) for t, w in cfg['loadings'].get(tag, {}).items()))
            for tag in TAGS}


def cached_affinity(engine, owner, cfg):
    """Per-agent affinity, recomputed only when the agent's traits change."""
    trait = traits(engine.agent(owner))
    cache = engine.__dict__.setdefault('_attention_affinity', {})
    key = tuple(trait[t] for t in TRAITS)
    if cache.get(owner, (None,))[0] != key:
        cache[owner] = (key, affinity(cfg, trait))
    return cache[owner][1]


def topic_fit(affinities, tags):
    return clip(sum(affinities[t] * w for t, w in tags.items()) / max(sum(tags.values()), 1e-9))


def top_down(cfg, fit, closeness_actor, closeness_mentioned, goal_match):
    """4.2: T = w_topic fit + w_rel closeness(actor) + w_ment max closeness(mentioned) + w_goal goal match."""
    return (cfg['w_topic'] * fit + cfg['w_rel'] * closeness_actor + cfg['w_ment'] * closeness_mentioned
            + cfg['w_goal'] * goal_match)


def bottom_up(cfg, surprise, threat_salience, threat_sensitivity, addressed):
    """4.3: B = max(surprise g_sur, threat_salience g_threat, 1 if addressed); g_threat rises with threat sensitivity."""
    g_threat = clip(cfg['threat_base'] + cfg['threat_dial_gain'] * threat_sensitivity)
    return max(surprise * cfg['g_sur'], threat_salience * g_threat, 1.0 if addressed else 0.0)


def combined(T, B):
    """4.4: soft OR, so bottom-up capture can override boredom."""
    return 1 - (1 - T) * (1 - B)


def capacity(cfg, arousal, fatigue, load, dysregulation, asleep=False):
    """4.5: K = K_max f(arousal) (1 - lam_fat fatigue) (1 - lam_load min(1, load / n_load_ref)) (1 - lam_dys dys)."""
    if asleep:
        return cfg['K_sleep']
    shape = 1 - cfg['kappa'] * (arousal - .5) ** 2 if cfg['arousal_shape'] == 'inverted_u' else 1.0
    return (cfg['K_max'] * shape * (1 - cfg['lam_fat'] * fatigue) * (1 - cfg['lam_load'] * min(1, load / cfg['n_load_ref']))
            * (1 - cfg['lam_dys'] * dysregulation))


def share(cfg, u, others, dysregulation):
    """4.6: this stream's share against the agent's other open streams and the mind-wandering competitor u0."""
    theta = cfg['theta']
    u0 = cfg['u0_base'] + cfg['u0_dys'] * dysregulation
    mine = u ** theta
    return mine / (mine + sum(x ** theta for x in others) + u0 ** theta) if mine else 0.0


def unit(*parts):
    """Deterministic uniform in (0, 1) from the parts; consumes no shared random state."""
    return (int(sha256(json.dumps(parts).encode()).hexdigest()[:13], 16) + .5) / 16 ** 13


def noisy(a_raw, z, scale):
    """4.7: a = sigmoid(logit(clip(a_raw, .01, .99)) + scale z), z standard logistic."""
    x = clip(a_raw, .01, .99)
    return 1 / (1 + exp(-(log(x / (1 - x)) + scale * z)))


def drift(cfg, prev, now, K, dysregulation, captured, seed, owner, stream):
    """4.9: (drift_until, newly drifted?) for an event arriving in a stream the agent was already in.

    Hazard lam = lam0 (1 - T_stream) (1 + lam_dys dys) / max(K, 0.1) per minute over the gap since the last event
    in the stream (or since the last drift ended). One draw r, seeded by the stream's last event, decides both
    whether a drift began (r < 1 - exp(-lam dt)) and when: onset = -ln(1 - r) / lam. Capture ends a drift.
    """
    until = prev.get('drift_until')
    if captured:
        return None, False
    if until is not None and until > now:
        return until, False
    since = max(prev['last_day'], until or prev['last_day'])
    lam = cfg['lam0_per_minute'] * (1 - prev['T']) * (1 + cfg['lam_dys'] * dysregulation) / max(K, .1)
    gap = (now - since) * MINUTES_PER_DAY
    r = unit(seed, owner, stream, prev['last_event'], 'drift')
    if lam <= 0 or r >= 1 - exp(-lam * gap):
        return None, False
    length = -cfg['drift_mean_minutes'] * log(unit(seed, owner, stream, prev['last_event'], 'drift_length'))
    end = since + (-log(1 - r) / lam + length) / MINUTES_PER_DAY
    return (end if end > now else None), True


def tier_of(cfg, a, addressed=False, captured=False):
    """4.8: FULL / GIST / NONE by thresholds; captured is at least FULL, addressed never NONE."""
    tier = FULL if a >= cfg['a_full'] else GIST if a >= cfg['a_gist'] else NONE
    if captured:
        return FULL
    return GIST if addressed and tier == NONE else tier


def allocate(engine, owner, event, obs):
    """One (listener, event) allocation. Updates only this agent's small stream state."""
    cfg = engine.state['config']['attention']
    if not cfg['enabled']:
        return AttentionResult(1.0, FULL)
    if obs['source'] == 'self' or obs.get('kind') == 'internal':
        return AttentionResult(1.0, FULL, addressed=True, reasons={'own_action_or_thought': True})
    from .sleep import dials
    agent = engine.agent(owner)
    dial = dials(agent)
    dys = dial['dysregulation']
    view = event_view(engine, owner, event, obs)
    now = view.timestamp
    close = lambda j: provider(engine, 'closeness')(engine, owner, j) ** cfg['gamma_rel']
    # Own name in the talk counts as being addressed (cocktail-party effect, Cherry 1953).
    addressed = owner in view.addressed_ids or owner in view.mentioned_ids
    fit = topic_fit(cached_affinity(engine, owner, cfg), view.topic_tags)
    c_actor = close(view.actor_id) if view.actor_id else 0.0
    c_ment = max((close(m) for m in view.mentioned_ids if m != owner and m in engine.state['entities']), default=0.0)
    goal = provider(engine, 'goal_match')(engine, owner, view)
    T = top_down(cfg, fit, c_actor, c_ment, goal)
    surprise = provider(engine, 'surprise')(engine, owner, view)
    B = bottom_up(cfg, surprise, view.threat_salience, dial['threat_sensitivity'], addressed)
    captured = B >= cfg['B_capture']
    u = combined(T, B)
    # Stream state: drop streams unseen for longer than the expiry, then compete with the rest.
    state = agent.setdefault('attention_state', {'streams': {}})
    expiry = cfg['stream_expiry_minutes'] / MINUTES_PER_DAY
    streams = {k: s for k, s in state['streams'].items() if now - s['last_day'] <= expiry}
    others = [s['u'] for k, s in streams.items() if k != view.stream_id]
    arousal = engine.mood(owner, now)['arousal']
    fatigue = provider(engine, 'fatigue')(engine, owner, now)
    asleep = provider(engine, 'asleep')(engine, owner, now)
    K = capacity(cfg, arousal, fatigue, len(others), dys, asleep and B < cfg['B_wake'])
    s = share(cfg, u, others, dys)
    a_raw = K * s
    q = unit(engine.state.get('seed'), owner, view.event_id, 'attention_noise')
    z = log(q / (1 - q))
    a = noisy(a_raw, z, cfg['s_0'] + cfg['s_dys'] * dys)
    prev = streams.get(view.stream_id)
    drift_until, began = drift(cfg, prev, now, K, dys, captured, engine.state.get('seed'), owner, view.stream_id) \
        if prev else (None, False)
    state['drift_periods'] = state.get('drift_periods', 0) + began
    drifted = drift_until is not None
    if drifted:
        a *= cfg['d_drift']
    if captured:
        a = max(a, cfg['a_capture_floor'])
    tier = tier_of(cfg, a, addressed, captured)
    streams[view.stream_id] = {'u': u, 'T': T, 'last_day': now, 'last_event': view.event_id, 'drift_until': drift_until}
    state['streams'] = streams
    engine.state['attention_stats']['allocations'] += 1
    return AttentionResult(a, tier, T, B, K, s, captured, drifted, addressed, tier != FULL and not addressed, {
        'topic_fit': fit, 'closeness_actor': c_actor, 'closeness_mentioned': c_ment, 'goal_match': goal,
        'surprise': surprise, 'threat_salience': view.threat_salience, 'asleep': bool(asleep),
        'arousal': arousal, 'fatigue': fatigue, 'other_streams': len(others), 'dysregulation': dys,
        'a_raw': a_raw, 'noise_z': z, 'stream': view.stream_id, 'topic_tags': view.topic_tags})


# Effects

def trace_factor(cfg, result):
    """5.1: a^gamma_enc, the multiplier on the existing trace weight."""
    return result.weight ** cfg['gamma_enc']


def encoding_factor(cfg, result, buffered=False):
    """Stability multiplier. With the hippocampal buffer, a scales its trace weight instead (sleep.trace_weight),
    so it is not applied twice; a GIST trace also starts less stable."""
    return (1.0 if buffered else trace_factor(cfg, result)) * (cfg['gist_stability_factor'] if result.tier == GIST else 1.0)


def coarse_text(engine, owner, obs, result):
    """A GIST trace keeps only who, the main topic and rough valence; a NONE receipt keeps nothing readable."""
    if result.tier == NONE:
        return '(not attended)'
    tags = result.reasons.get('topic_tags', {})
    topic = PHRASES[max(TAGS, key=lambda t: (tags.get(t, 0), TAGS.index(t)))]  # ties go past generic 'social'
    source = obs['source']
    who = engine.label(source) if source in engine.state['entities'] and source != owner else 'Something'
    valence = obs.get('valence', 0)
    feel = '; it seemed unpleasant' if valence < -.2 else '; it seemed pleasant' if valence > .2 else ''
    return f'Half-noticed: {who}, something about {topic}{feel}.'


def encoded(engine, owner, obs, result):
    """The observation as encoded: unchanged when FULL, else a coarse version (the original stays in the event log)."""
    if result.tier == FULL:
        return obs
    text = coarse_text(engine, owner, obs, result)
    out = {k: v for k, v in obs.items() if k not in ('gist', 'mentions', 'cued_memories', 'references')}
    if result.tier == GIST:
        out.update({k: obs[k] for k in ('mentions', 'references') if k in obs})
    return {**out, 'text': text, 'meaning': text, 'gist': text}


def record(meta, result, buffered=False):
    """Store the result on the memory receipt. NONE hides the receipt; GIST without the buffer is a gist memory."""
    meta['attention'] = asdict(result)
    if result.tier == NONE:
        meta['tier'] = UNATTENDED
    elif result.tier == GIST:
        meta['gist_only'] = True
        if not buffered:
            meta['tier'] = 'gist'


def emotion_scale(meta):
    """5.2: multiplier on an event's mood and arousal impulse: a, in full when captured, 0 for an unattended event."""
    record = meta.get('attention')
    if record is None or record['captured']:
        return 1.0
    return 0.0 if record['tier'] == NONE else record['weight']


def felt_ignored(engine, listener, event, obs, result):
    """5.5 (behind felt_ignored, default off): a face-to-face speaker may notice low attention and feel ignored.

    P(notice) = notice_gain x closeness(speaker, listener) x (1 - a). Only an existing tie of a living, materialized
    speaker changes, through Engine.relate; each change is logged in attention_stats.felt_ignored.
    """
    cfg = engine.state['config']['attention']
    speaker = obs['source']
    if (not cfg['felt_ignored'] or result.captured or speaker not in obs.get('encountered', [])
            or speaker not in engine.state['agents'] or not engine.agent(speaker)['alive']):
        return
    tie = engine.agent(speaker)['relationships'].get(listener)
    if tie is None:
        return
    chance = cfg['notice_gain'] * provider(engine, 'closeness')(engine, speaker, listener) * (1 - result.weight)
    if unit(engine.state.get('seed'), speaker, listener, event['id'], 'felt_ignored') >= chance:
        return
    closeness = max(0.0, tie.get('closeness', 0.0) - cfg['ignored_penalty'])
    engine.relate(speaker, listener, tie.get('role', 'acquaintance'), trust=tie.get('trust', .5), closeness=closeness)
    engine.state['attention_stats'].setdefault('felt_ignored', []).append(
        {'event': event['id'], 'speaker': speaker, 'listener': listener, 'weight': result.weight,
         'closeness_before': tie.get('closeness', 0.0), 'closeness_after': closeness})
