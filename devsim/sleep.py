"""Hippocampal buffer and lazy sleep consolidation. Every parameter is a design default, unverified.

With the 'sleep' policy, a received experience is logged cheaply in the agent's buffer instead of becoming a
long-term memory. Once the agent has been awake min_awake_hours, the next time step counts as a sleep
opportunity. The whole buffer is then triaged once, whatever the skipped length (O(buffer), no per-night loop):
promoted to an episodic memory, merged into a gist, or dropped. Design reference: the "Sleep Memory Simulator
Research" report, section 13 (its equations are missing from the export; the formulas here are the user's).

The engine's memory_meta entry is also the "this agent received this event" record that beliefs, development,
relationships and reminders validate against, so it is kept for every tier. Only its 'tier' decides whether
recall can reach it.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import logging
from math import exp, log, log1p
from random import Random
import re

from . import POLICY_DIR

LOG = logging.getLogger(__name__)
CONFIG_PATH = POLICY_DIR / 'sleep-consolidation.json'
HIDDEN = ('dropped', 'merged')  # tiers kept only as receipt and provenance records; recall never reaches them
DIALS = {'dysregulation': (0, 1, 0.0), 'mood_baseline_shift': (-1, 1, 0.0),
         'threat_sensitivity': (0, 1, 0.0), 'reality_testing': (0, 1, 1.0)}  # name: (low, high, neutral default)


def parameters():
    return json.loads(CONFIG_PATH.read_text())['parameters']


def configure(engine, overrides=None):
    """Store the full sleep policy in the world config (checkpointed). Archived worlds without it are unchanged."""
    from .engine import number
    spec = parameters()
    overrides = overrides or {}
    if not isinstance(overrides, dict) or set(overrides) - set(spec):
        raise ValueError('Unsupported sleep setting')
    settings = {key: overrides.get(key, item['value']) for key, item in spec.items()}
    for key, item in spec.items():
        if 'choices' in item:
            if settings[key] not in item['choices'] or type(settings[key]) is not type(item['value']):
                raise ValueError(f'{key} must be one of {item["choices"]}')
        else:
            number(settings[key], *item['range'], key)
    if settings['theta_drop'] >= settings['theta_episodic'] or settings['age_decline_start'] >= settings['age_decline_end']:
        raise ValueError('Need theta_drop < theta_episodic and age_decline_start < age_decline_end')
    if isinstance(settings['llm_batch_size'], bool) or not isinstance(settings['llm_batch_size'], int):
        raise ValueError('llm_batch_size must be an integer')
    current = engine.state['config'].get('sleep')
    if current is not None and current != settings:
        raise ValueError('Cannot silently replace sleep policy')
    engine.state['config']['sleep'] = settings


def set_dials(engine, owner, **values):
    """Scenario-set clinical dials. Unset dials stay neutral; no agent type or role changes these rules."""
    from .engine import number
    if set(values) - set(DIALS):
        raise ValueError('Unknown dial')
    for key, value in values.items():
        number(value, *DIALS[key][:2], key)
    engine.agent(owner).setdefault('dials', {}).update(values)


def dials(agent):
    return {key: agent.get('dials', {}).get(key, default) for key, (_, _, default) in DIALS.items()}


# Encoding and live phase

def buffer(engine, owner, event, obs):
    """Encoding path: a raw log entry only. No stability change, gist, node, edge or embedding work here."""
    cfg = engine.state['config']['sleep']
    agent = engine.agent(owner)
    agent['memory_meta'][event['id']]['tier'] = 'buffer'
    source = [obs['source']] if obs['source'] in engine.state['entities'] and obs['source'] != owner else []
    agent.setdefault('hippocampal_buffer', []).append({
        'id': 'buffer:' + event['id'], 'timestamp': event['day'], 'raw_text': obs['text'],
        'participants': sorted({*obs.get('encountered', []), *source}),
        'arousal': obs.get('arousal', 0), 'valence': obs.get('valence', 0),
        'novelty': 1 / (1 + obs['exposures']) if 'reused_appraisal' in obs else cfg['novelty_default'],
        'self_relevance': obs.get('importance', 0), 'rehearsal_count': 0, 'source_event_id': event['id']})
    agent.setdefault('sleep', {'wake_day': event['day']})


def encoding_multiplier(engine, owner):
    """Config-gated penalty on new memories' stability after poor sleep: 1 - strength * (1 - last Q)."""
    cfg = engine.state['config']['sleep']
    q = engine.agent(owner).get('sleep', {}).get('last_q')
    return 1.0 if not cfg['encoding_penalty'] or q is None else 1 - cfg['encoding_penalty_strength'] * (1 - q)


def rehearse(agent, event_id):
    """A recalled buffer entry counts one rehearsal; its stability is set when sleep resolves it."""
    entry = next(e for e in agent['hippocampal_buffer'] if e['source_event_id'] == event_id)
    entry['rehearsal_count'] += 1


def lability(days, cfg):
    """Survival of an unconsolidated trace after `days` (retrieval, and step 3's delay). Replace freely."""
    return exp(-cfg['lambda_lability'] * max(0.0, days))


def due(engine, day):
    """Called by Engine.advance before each event and at the target day; resolves agents due for sleep."""
    min_awake = engine.state['config']['sleep']['min_awake_hours'] / 24
    for owner, agent in engine.state['agents'].items():
        clock = agent.get('sleep')
        if agent['alive'] and clock and day >= clock['wake_day'] + min_awake:
            resolve_sleep(engine, owner, clock['wake_day'], day)


# Steps 1-4

def sleep_quality(cfg, dial, mean_arousal):
    """Step 1: aggregate sleep quality Q over the skipped period, clipped to [q_floor, 1]."""
    q = (cfg['q_base'] * (1 - cfg['a_dysreg'] * dial['dysregulation'])
         * (1 - cfg['a_mood'] * max(0.0, -dial['mood_baseline_shift']))  # only a lowered baseline costs sleep
         * (1 - cfg['a_threat'] * dial['threat_sensitivity']) * (1 - cfg['a_stress'] * mean_arousal))
    return min(1.0, max(cfg['q_floor'], q))


def trace_weight(cfg, entry, threat):
    """Step 2: multiplicative tag-and-capture weight; threat sensitivity amplifies negative arousal only."""
    arousal = entry['arousal'] * (1 + cfg['threat_gain'] * threat) if entry['valence'] < 0 else entry['arousal']
    return ((1 + cfg['k_arousal'] * arousal) * (1 + cfg['k_rehearsal'] * log1p(entry['rehearsal_count']))
            * (1 + cfg['k_self'] * entry['self_relevance']) * (1 + cfg['k_novelty'] * entry['novelty']))


def age_multiplier(cfg, age_years):
    span = (age_years - cfg['age_decline_start']) / (cfg['age_decline_end'] - cfg['age_decline_start'])
    return 1 - (1 - cfg['age_floor']) * min(1.0, max(0.0, span))


def reality_capacity(cfg, reality_testing):
    return 1 - cfg['rt_strength'] * (1 - reality_testing)


def logistic(rng):
    u = min(max(rng.random(), 1e-12), 1 - 1e-12)
    return log(u / (1 - u))


def triage(cfg, score):
    """Step 4 thresholds: 'episodic', 'gist' or 'dropped'."""
    return 'episodic' if score >= cfg['theta_episodic'] else 'gist' if score >= cfg['theta_drop'] else 'dropped'


# Gist matching and summaries (pluggable)

def overlap_similarity(a, b):
    """Items are {'text', 'words', 'participants'} (sets). Fallback similarity in [0, 1]: mean Jaccard overlap of participants (when either has any) and content words."""
    def jaccard(x, y):
        return len(x & y) / len(x | y) if x | y else 0.0
    parts = [jaccard(a['words'], b['words'])]
    if a['participants'] or b['participants']:
        parts.append(jaccard(a['participants'], b['participants']))
    return sum(parts) / len(parts)


def matcher(engine, items):
    """(similarity function, threshold). Local BGE vectors when the cognition policy uses them, else overlap."""
    cfg = engine.state['config']['sleep']
    if engine.state['config'].get('cognition', {}).get('semantic_matching'):
        try:
            from .graphiti_bridge import vectors
            texts = list(dict.fromkeys(item['text'] for item in items))
            found = dict(zip(texts, vectors(texts)))  # one batched request; cached in process
            return (lambda a, b: sum(x * y for x, y in zip(found[a['text']], found[b['text']]))), cfg['sim_threshold_embedding']
        except (OSError, ValueError, KeyError):
            LOG.debug('embedding service unavailable; sleep gist matching falls back to overlap')
    return overlap_similarity, cfg['sim_threshold']


def extractive(engine, owner, entries):
    """Default summarizer: the appraisal's own gist if present, else the first sentence, at most 25 words."""
    meta = engine.agent(owner)['memory_meta']
    return [meta[e['source_event_id']].get('summary') or
            ' '.join(re.split(r'(?<=[.!?])\s+', e['raw_text'].strip())[0].split()[:25]) for e in entries]


def llm_summarizer(api, model):
    """Optional summarizer: one local-model call per llm_batch_size memories; a failed batch keeps extractive text."""
    def summarize(engine, owner, entries):
        from .engine import InvalidModelOutput, validated_json
        result = extractive(engine, owner, entries)
        size = engine.state['config']['sleep']['llm_batch_size']
        for start in range(0, len(entries), size):
            chunk = entries[start:start + size]
            ids = [e['id'] for e in chunk]
            def validate(r):
                gists = r.get('gists')
                if (not isinstance(gists, list) or [g.get('id') if isinstance(g, dict) else None for g in gists] != ids
                        or not all(isinstance(g.get('gist'), str) and 0 < len(g['gist'].strip()) <= 300 for g in gists)):
                    raise ValueError('Return gists: one {id, gist} per supplied memory, in order')
            context = {'memories': [{'id': e['id'], 'text': e['raw_text'], 'participants': e['participants']} for e in chunk]}
            try:
                reply = validated_json('Compress each supplied memory of this fictional agent to one short plain sentence '
                                       '(at most 25 words) keeping who did what; drop time and place details. Invent nothing. '
                                       'Return JSON gists: a list of {id, gist}, one per memory, in the supplied order.',
                                       context, validate, api, model, 60 * len(chunk) + 100)
            except (InvalidModelOutput, RuntimeError) as exc:
                engine.skip_model_step('sleep_gist', owner, exc)
                continue
            result[start:start + len(chunk)] = [g['gist'].strip() for g in reply['gists']]
        return result
    return summarize


# Step 5

@dataclass
class SleepResolutionRecord:
    owner: str
    t_start: float
    t_end: float
    skip_id: str
    seed: str
    q: float
    theta_drop: float
    theta_episodic: float
    counts: dict
    ids: dict


def resolve_sleep(engine, owner, t_start, t_end, rng=None):
    """Resolve every buffer entry encoded by t_end in one pass. rng defaults to one seeded by (world seed, agent, skip)."""
    cfg = engine.state['config']['sleep']
    max_stability = engine.state['config']['max_stability_days']
    agent = engine.agent(owner)
    meta = agent['memory_meta']
    skip_id = f'{t_start!r}:{t_end!r}'
    seed = 'caller_rng'
    if rng is None:
        seed = sha256(json.dumps([engine.state['seed'], owner, skip_id]).encode()).hexdigest()
        rng = Random(int(seed, 16))
    held = agent.get('hippocampal_buffer', [])
    entries = sorted((e for e in held if e['timestamp'] <= t_end), key=lambda e: (e['timestamp'], e['id']))
    dial = dials(agent)
    q = sleep_quality(cfg, dial, sum(e['arousal'] for e in entries) / len(entries) if entries else 0.0)
    capacity = (log(q) + log(age_multiplier(cfg, (t_end - agent['birth_day']) / 365.25))
                + log(reality_capacity(cfg, dial['reality_testing'])))
    first_sleep = t_start + cfg['min_awake_hours'] / 24
    noise = [logistic(rng) for _ in entries]  # drawn up front, so another seed moves only the noise
    ids = {'promoted': [], 'gist_merged': [], 'gist_new': [], 'dropped': []}
    gists = []
    for entry, eps in zip(entries, noise):
        w_eff = trace_weight(cfg, entry, dial['threat_sensitivity']) * lability(
            max(0.0, first_sleep - entry['timestamp']) / max(q, cfg['q_floor']), cfg)
        tier = triage(cfg, log(w_eff) + capacity + cfg['sigma'] * eps)
        record = meta[entry['source_event_id']]
        if tier == 'episodic':
            record.update(tier='episodic', stability_days=min(max_stability,
                          record['stability_days'] * w_eff ** cfg['promote_stability_exponent']))
            ids['promoted'].append(entry['id'])
        elif tier == 'gist':
            gists.append((entry, w_eff))
        else:
            record['tier'] = 'dropped'
            ids['dropped'].append(entry['id'])
    if gists:
        _merge_gists(engine, owner, gists, ids, cfg, max_stability)
    agent['hippocampal_buffer'] = [e for e in held if e['timestamp'] > t_end]
    result = SleepResolutionRecord(owner, t_start, t_end, skip_id, seed, q, cfg['theta_drop'], cfg['theta_episodic'],
                                   {k: len(v) for k, v in ids.items()}, ids)
    agent['sleep'] = {'wake_day': t_end, 'last_q': q, 'last': asdict(result)}
    LOG.debug('sleep resolution %s', json.dumps(asdict(result)))
    return result


def _merge_gists(engine, owner, gists, ids, cfg, max_stability):
    """Gist tier: boost a similar existing memory, else start (or extend) a compressed gist memory."""
    from .cognition import words
    meta = engine.agent(owner)['memory_meta']
    observed = {o.event_id: o for o in engine.world.observations.get(owner, [])}
    def item(event_id, text, participants):
        return {'id': event_id, 'text': text, 'words': words(text), 'participants': set(participants)}
    existing = [item(mid, m.get('summary') or observed[mid].text, m.get('encountered', []))
                for mid, m in meta.items() if m.get('tier', 'episodic') in ('episodic', 'gist') and mid in observed]
    incoming = [item(e['source_event_id'], e['raw_text'], e['participants']) for e, _ in gists]
    similar, threshold = matcher(engine, existing + incoming)
    created, founders = set(), []
    # shortcut: compares each gist with every long-term memory (O(gists x memories)); index by participant past ~1e5.
    for (entry, w_eff), new in zip(gists, incoming):
        score, best = max(((similar(new, node), node['id']) for node in existing), default=(None, None))
        record = meta[new['id']]
        if best is not None and score >= threshold:
            target = meta[best]
            target['stability_days'] = min(max_stability, target['stability_days'] * (1 + cfg['gist_stability_gain']))
            if best in created:  # a gist memory started this night grows; earlier memories only strengthen
                target['gist_members'].append(new['id'])
            record.update(tier='merged', merged_into=best)
            ids['gist_merged'].append(entry['id'])
            continue
        # Context and time edges dropped: only the summary is recalled; participants stay in 'encountered'.
        record.update(tier='gist', gist_members=[], stability_days=min(
            max_stability, record['stability_days'] * w_eff ** cfg['promote_stability_exponent']))
        created.add(new['id'])
        founders.append(entry)
        existing.append(new)
        ids['gist_new'].append(entry['id'])
    summarize = getattr(engine, 'sleep_summarizer', None) if cfg['summarizer'] == 'llm' else None
    for entry, text in zip(founders, (summarize or extractive)(engine, owner, founders)):
        meta[entry['source_event_id']]['summary'] = text
