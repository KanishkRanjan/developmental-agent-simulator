"""Hippocampal buffer and sleep consolidation checks; synthetic, no model server. Parameters are design defaults."""
import inspect
import json
from math import exp, log
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

from devsim import sleep
from devsim.engine import Engine, FACET_NAMES
from devsim.lifetime import Lifetime

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
CFG = {k: v['value'] for k, v in sleep.parameters().items()}
NEUTRAL = {k: d for k, (_, _, d) in sleep.DIALS.items()}
WORDS = ('rain bus market lunch phone garden exam song bike letter kitchen tram film coffee paint river shelf '
         'ticket jacket candle oven street dinner ladder mirror window bread chair clock desk lamp shoes').split()


def world(seed=7, age=30, configure=True, **settings):
    e = Engine(seed)
    for key in ('ana', 'ben', 'cy'):
        e.entity(key, key.title())
    e.materialize('ana', dict.fromkeys(FACET_NAMES, 50), birth_day=-age * 365.25)
    if configure:
        sleep.configure(e, settings)
    return e


def schedule_mixed(e, n, rng, start=0.0, span=0.6, prefix='m'):
    """A mixed-arousal day: varied text, valence, arousal and importance, from two people."""
    for i in range(n):
        who = rng.choice(['ben', 'cy'])
        e.schedule(f'{prefix}{i}', start + span * i / n, 'Something happened.', {'ana': {
            'text': f'{who.title()} and I: ' + ' '.join(rng.sample(WORDS, 6)) + '.', 'source': who,
            'encountered': [who], 'valence': rng.uniform(-1, 1), 'arousal': rng.random(), 'importance': rng.random()}})


def entry(**fields):
    return {'id': 'buffer:x', 'timestamp': 0.0, 'raw_text': 'x', 'participants': [], 'arousal': 0.5, 'valence': 0.0,
            'novelty': 0.5, 'self_relevance': 0.5, 'rehearsal_count': 0, 'source_event_id': 'x', **fields}


def promote_rate(seeds, text='Ben shouted at me and I was frightened.', age=30, valence=-0.8, arousal=0.9, **dial):
    """Fraction of seeds in which one buffered entry is promoted."""
    e = world(age=age)
    if dial:
        sleep.set_dials(e, 'ana', **dial)
    e.schedule('one', 0.1, 'x', {'ana': {'text': text, 'source': 'ben', 'encountered': ['ben'],
                                         'valence': valence, 'arousal': arousal, 'importance': .5}})
    e.advance(0.1)
    snapshot = json.dumps(e.state)
    promoted = 0
    for seed in range(seeds):
        e.state = json.loads(snapshot)
        record = sleep.resolve_sleep(e, 'ana', 0.1, 2.0, Random(seed))
        promoted += record.counts['promoted']
    return promoted / seeds


def main():
    checks = []

    # Step functions.
    assert sleep.sleep_quality(CFG, NEUTRAL, 0) == CFG['q_base']
    low = sleep.sleep_quality(CFG, NEUTRAL | {'mood_baseline_shift': -1}, 0)
    assert abs(low - CFG['q_base'] * (1 - CFG['a_mood'])) < 1e-12
    assert sleep.sleep_quality(CFG, NEUTRAL | {'mood_baseline_shift': 1}, 0) == CFG['q_base'], 'raised mood must not cost sleep'
    worst = NEUTRAL | {'dysregulation': 1, 'mood_baseline_shift': -1, 'threat_sensitivity': 1}
    assert CFG['q_floor'] <= sleep.sleep_quality(CFG, worst, 1) < sleep.sleep_quality(CFG, NEUTRAL, 1) < sleep.sleep_quality(CFG, NEUTRAL, 0)
    assert sleep.sleep_quality(CFG | {'q_base': 0.01}, NEUTRAL, 0) == CFG['q_floor']
    checks.append('step 1: Q is the clipped product of dial, mood-baseline, threat and stress terms; low mood baseline lowers Q')

    base = sleep.trace_weight(CFG, entry(arousal=0, self_relevance=0, novelty=0), 0)
    assert base == 1
    assert sleep.trace_weight(CFG, entry(arousal=.8, valence=.5), 1) == sleep.trace_weight(CFG, entry(arousal=.8, valence=.5), 0)
    assert sleep.trace_weight(CFG, entry(arousal=.8, valence=-.5), 1) > sleep.trace_weight(CFG, entry(arousal=.8, valence=-.5), 0)
    a, r = sleep.trace_weight(CFG, entry(arousal=1), 0), sleep.trace_weight(CFG, entry(rehearsal_count=3), 0)
    both = sleep.trace_weight(CFG, entry(arousal=1, rehearsal_count=3), 0)
    assert abs(both * sleep.trace_weight(CFG, entry(), 0) - a * r) < 1e-9, 'factors must multiply'
    checks.append('step 2: weight multiplies arousal, rehearsal, self-relevance and novelty; threat amplifies negative arousal only')

    assert sleep.lability(0, CFG) == 1 and abs(sleep.lability(2, CFG) - exp(-2 * CFG['lambda_lability'])) < 1e-12
    assert sleep.lability(-1, CFG) == 1
    checks.append('step 3: lability is an isolated exponential of delay days')

    assert sleep.triage(CFG, CFG['theta_episodic']) == 'episodic' and sleep.triage(CFG, CFG['theta_drop']) == 'gist'
    assert sleep.triage(CFG, CFG['theta_drop'] - 1e-9) == 'dropped'
    assert sleep.age_multiplier(CFG, 30) == 1 == sleep.age_multiplier(CFG, 60) and sleep.age_multiplier(CFG, 100) == CFG['age_floor']
    assert 1 > sleep.age_multiplier(CFG, 70) > sleep.age_multiplier(CFG, 80) > CFG['age_floor']
    assert sleep.reality_capacity(CFG, 1) == 1 and sleep.reality_capacity(CFG, 0) == 1 - CFG['rt_strength']
    samples = [sleep.logistic(Random(i)) for i in range(4000)]
    assert abs(sum(samples) / len(samples)) < .15 and abs(sum(s * s for s in samples) / len(samples) - 3.29) < .4
    checks.append('step 4: two thresholds, flat-then-declining age multiplier, monotone reality-testing capacity, logistic noise')

    a = {'text': 'x', 'words': {'bus', 'rain'}, 'participants': {'ben'}}
    assert sleep.overlap_similarity(a, a) == 1
    assert sleep.overlap_similarity(a, {'text': 'y', 'words': {'exam'}, 'participants': {'cy'}}) == 0
    assert sleep.overlap_similarity(a | {'participants': set()}, a | {'participants': set()}) == 1
    e = world()
    e.schedule('s', 0, 'x', {'ana': {'text': 'Ben fixed my bike. Then we ate lunch.', 'source': 'ben', 'encountered': ['ben']}})
    e.schedule('g', 0, 'x', {'ana': {'text': 'Long text.', 'source': 'ben', 'gist': 'Ben helped me.'}})
    e.advance(0)
    held = e.agent('ana')['hippocampal_buffer']
    assert sleep.extractive(e, 'ana', held) == ['Ben helped me.', 'Ben fixed my bike.']  # same-day events apply in id order
    checks.append('gist matching falls back to participant and word overlap; extractive summaries reuse the appraisal gist')

    # Encoding and buffer-aware retrieval.
    e = world()
    e.schedule('hit', 0.2, 'x', {'ana': {'text': 'Ben shouted at me in the kitchen.', 'source': 'ben', 'encountered': ['ben'],
                                         'valence': -.7, 'arousal': .8, 'importance': .6}})
    e.advance(0.3)
    agent = e.agent('ana')
    [held] = agent['hippocampal_buffer']
    assert set(held) == {'id', 'timestamp', 'raw_text', 'participants', 'arousal', 'valence', 'novelty', 'self_relevance',
                         'rehearsal_count', 'source_event_id'} and held['participants'] == ['ben']
    meta = agent['memory_meta']['hit']
    assert meta['tier'] == 'buffer' and meta['stability_days'] == meta['encoding_stability_days'] and 'summary' not in meta
    [seen] = e.memories('ana', 'kitchen shouted')
    assert seen['text'] == 'Ben shouted at me in the kitchen.' and abs(seen['availability'] - sleep.lability(.1, CFG)) < 1e-12
    from devsim import cognition
    cognition.configure(e, {})
    [view] = cognition.views(e, 'ana', 'kitchen', 5)
    assert view['original_detail_available'] and view['representation'] == 'episodic_detail'
    checks.append('encoding writes only a raw buffer entry; buffered memories are retrievable in full with lability retrievability')

    # Rehearsal wiring: a buffered recall counts toward the trace weight; afterwards the existing rule applies.
    stability = meta['stability_days']
    e.recall('ana', 'hit', 'r1', rehearse=True)
    assert held['rehearsal_count'] == 1 and meta['stability_days'] == stability and meta['last_recall_day'] is None
    e.state['config']['sleep'].update(theta_drop=-60, theta_episodic=-50)  # force promotion
    e.advance(1.5)
    assert meta['tier'] == 'episodic' and not agent['hippocampal_buffer']
    promoted = meta['stability_days']
    e.recall('ana', 'hit', 'r2', rehearse=True)
    assert abs(meta['stability_days'] - promoted * (1 + e.state['config']['rehearsal_gain'])) < 1e-9 and meta['last_recall_day'] == 1.5
    checks.append('rehearsal: a buffered recall increments rehearsal_count only; after promotion the existing rule multiplies S and resets the clock')

    # Edge cases: short skip, empty buffer, determinism, long skip.
    e = world()
    schedule_mixed(e, 20, Random(1), span=0.3)
    e.advance(0.3)
    e.advance(0.65)  # a 0.35-day skip; under 16 h since waking at day 0, so nothing resolves
    assert len(e.agent('ana')['hippocampal_buffer']) == 20 and 'last' not in e.agent('ana')['sleep']
    empty = world()
    record = sleep.resolve_sleep(empty, 'ana', 0, 5)
    assert record.counts == {'promoted': 0, 'gist_merged': 0, 'gist_new': 0, 'dropped': 0} and record.q == CFG['q_base']
    checks.append('a skip shorter than one sleep opportunity leaves the buffer untouched; an empty buffer gives zero counts')

    snapshot = json.dumps(e.state)
    runs = []
    for seed in (11, 11, 12):
        e.state = json.loads(snapshot)
        runs.append(sleep.resolve_sleep(e, 'ana', 0, 3, Random(seed)))
    assert runs[0] == runs[1] and runs[0] != runs[2]
    e.state = json.loads(snapshot)
    agent, cfg = e.agent('ana'), e.state['config']['sleep']
    q = sleep.sleep_quality(cfg, NEUTRAL, sum(x['arousal'] for x in agent['hippocampal_buffer']) / 20)
    def fixed(x):  # the score without noise
        w = sleep.trace_weight(cfg, x, 0) * sleep.lability((cfg['min_awake_hours'] / 24 - x['timestamp']) / q, cfg)
        return log(w) + log(q)
    margin = {x['id']: min(abs(fixed(x) - cfg['theta_drop']), abs(fixed(x) - cfg['theta_episodic'])) for x in agent['hippocampal_buffer']}
    tier = [{i: k for k, ids in r.ids.items() for i in ids} for r in runs]
    changed = [i for i in tier[0] if tier[0][i] != tier[2][i]]
    assert changed and all(margin[i] < 10 * cfg['sigma'] for i in changed)
    flat = []
    for seed in (11, 12):
        e.state = json.loads(snapshot)
        e.state['config']['sleep']['sigma'] = 0
        flat.append(sleep.resolve_sleep(e, 'ana', 0, 3, Random(seed)).ids)
    assert flat[0] == flat[1]
    # The default rng depends only on (world seed, agent, skip), so a checkpoint replay matches.
    e.state = json.loads(snapshot)
    e.advance(5)
    first = (e.agent('ana')['sleep']['last'], e.agent('ana')['memory_meta'])
    with TemporaryDirectory() as directory:
        e.state = json.loads(snapshot)
        e.save(Path(directory) / 'w.json')
        reloaded = Engine.load(Path(directory) / 'w.json')
    reloaded.advance(5)
    assert (reloaded.agent('ana')['sleep']['last'], reloaded.agent('ana')['memory_meta']) == first
    checks.append('same seed gives identical records (also after a checkpoint round trip); another seed changes only near-threshold entries; sigma 0 is seed-independent')

    calls = []
    original = sleep.resolve_sleep
    def counted(*args, **kwargs):
        calls.append(args[2:4])
        return original(*args, **kwargs)
    timing = {}
    for years in (1 / 365.25, 50):
        big = world()
        schedule_mixed(big, 600, Random(3))
        big.advance(0.6)
        calls.clear()
        start = time.perf_counter()
        with patch.object(sleep, 'resolve_sleep', counted):
            big.advance(0.6 + 365.25 * years)
        timing[years] = time.perf_counter() - start
        assert len(calls) == 1 and not big.agent('ana')['hippocampal_buffer']
        assert sum(big.agent('ana')['sleep']['last']['counts'].values()) == 600
    assert timing[50] < 5 * timing[1 / 365.25] + 0.5, timing
    checks.append('a 50-year skip with a 600-entry buffer resolves once, in about the time of a one-day skip (no per-night loop)')

    # Statistical monotonicity over many seeds.
    high, low = promote_rate(1500, threat_sensitivity=1), promote_rate(1500, threat_sensitivity=0)
    assert high > low + .03, (high, low)
    calm_high, calm_low = promote_rate(1500, valence=.5, threat_sensitivity=1), promote_rate(1500, valence=.5, threat_sensitivity=0)
    assert calm_high <= calm_low, 'threat sensitivity should not favor positive memories'
    sharp, impaired = promote_rate(1500, arousal=.5, valence=.2), promote_rate(1500, arousal=.5, valence=.2, reality_testing=0)
    young, old = sharp, promote_rate(1500, arousal=.5, valence=.2, age=85)
    insomnia = promote_rate(1500, arousal=.5, valence=.2, dysregulation=1, mood_baseline_shift=-1, threat_sensitivity=1)
    assert impaired < .8 * sharp and old < .8 * young and insomnia < .3 * sharp, (sharp, impaired, old, insomnia)
    checks.append('over 1500 seeds: threat sensitivity promotes a high-arousal negative memory more often; low reality testing, '
                  'old age and near-floor Q lower promotion (insomnia promotes under 30% as often)')

    penalised = world(encoding_penalty=True)
    sleep.set_dials(penalised, 'ana', dysregulation=1, mood_baseline_shift=-1, threat_sensitivity=1)
    plain = world()
    sleep.set_dials(plain, 'ana', dysregulation=1, mood_baseline_shift=-1, threat_sensitivity=1)
    for w in (penalised, plain):
        w.schedule('a', 0, 'x', {'ana': {'text': 'A hard day.', 'source': 'ben', 'arousal': .9, 'valence': -.9}})
        w.schedule('b', 2, 'x', {'ana': {'text': 'The morning after.', 'source': 'ben', 'arousal': .3}})
        w.advance(2)
    q = penalised.agent('ana')['sleep']['last_q']
    assert q == plain.agent('ana')['sleep']['last_q'] and q < .3
    ratio = penalised.agent('ana')['memory_meta']['b']['stability_days'] / plain.agent('ana')['memory_meta']['b']['stability_days']
    assert abs(ratio - (1 - CFG['encoding_penalty_strength'] * (1 - q))) < 1e-9
    checks.append('config-gated encoding penalty: after near-floor sleep, new memories encode with stability x (1 - strength x (1 - Q))')

    # Integration: a lazy skip through the existing Lifetime resolver, with experiences also arising inside the skip.
    e = world(configure=False)
    schedule_mixed(e, 400, Random(5))
    policy = {'sampling': 'event_driven', 'sleep': {}, 'opportunities': [{
        'id': 'walk', 'actor': 'ana', 'min_age': 0, 'max_age': 100, 'rate_per_year': 30, 'situation': 'A free evening.',
        'options': [{'id': 'go', 'label': 'Walk to the river.', 'success_probability': .7, 'arousal': .3,
                     'success_text': 'I walked by the river.', 'failure_text': 'It rained on my walk.',
                     'valence_success': .3, 'valence_failure': -.2}]}]}
    Lifetime(e, policy, scripted=True).run(365.25 * 2)
    agent = e.agent('ana')
    tiers = [agent['memory_meta'][f'm{i}']['tier'] for i in range(400)]
    share = {t: tiers.count(t) / 400 for t in ('episodic', 'gist', 'merged', 'dropped')}
    assert 'buffer' not in tiers and .08 <= share['episodic'] <= .25 and .35 <= share['gist'] + share['merged'] <= .65, share
    later = {k: m['tier'] for k, m in agent['memory_meta'].items() if not k.startswith('m')}
    waiting = {x['source_event_id'] for x in agent['hippocampal_buffer']}
    assert later and set(later.values()) - {'buffer'} and waiting == {k for k, t in later.items() if t == 'buffer'}
    assert all(x['timestamp'] >= agent['sleep']['wake_day'] for x in agent['hippocampal_buffer']), 'skip-time events share the pipeline'
    hidden = {k for k, m in agent['memory_meta'].items() if m['tier'] in sleep.HIDDEN}
    cognition.configure(e, {})
    visible = {m['event'] for m in cognition.views(e, 'ana', '', 10000)}
    gists = {k for k, m in agent['memory_meta'].items() if m['tier'] == 'gist'}
    assert hidden and not hidden & visible and gists <= visible  # old episodes may have faded by the existing rule
    assert all(agent['memory_meta'][k]['summary'] for k, m in agent['memory_meta'].items() if m['tier'] == 'gist')
    checks.append(f'Lifetime 2-year scripted skip drains the buffer: {share["episodic"]:.0%} episodic, '
                  f'{share["gist"] + share["merged"]:.0%} gist, {share["dropped"]:.0%} dropped; skip-time events follow '
                  'the same pipeline; dropped and merged entries are never retrieved')

    # Batched optional LLM summarizer, called through the pluggable hook.
    e = world(summarizer='llm', llm_batch_size=4, sim_threshold=1)
    schedule_mixed(e, 30, Random(9))
    e.state['config']['sleep'].update(theta_drop=-60, theta_episodic=60)  # everything becomes gist
    sizes = []
    def stub(system, context, validate, api, model, max_tokens=600):
        sizes.append(len(context['memories']))
        reply = {'gists': [{'id': m['id'], 'gist': 'Summary of ' + m['id']} for m in context['memories']]}
        validate(reply)
        return reply
    e.sleep_summarizer = sleep.llm_summarizer('http://127.0.0.1:1', 'none')
    with patch('devsim.engine.validated_json', side_effect=stub):
        e.advance(3)
    record = e.agent('ana')['sleep']['last']
    assert sizes and max(sizes) <= 4 and sum(sizes) == record['counts']['gist_new']
    assert all(e.agent('ana')['memory_meta'][i.removeprefix('buffer:')]['summary'].startswith('Summary') for i in record['ids']['gist_new'])
    checks.append('the optional LLM summarizer is batched (at most llm_batch_size memories per call), behind the summarizer flag')

    # Forgotten stays forgotten: no reader passes a dropped memory back to the model or replays its feeling.
    from devsim import cognition, household
    e = world(theta_drop=19, theta_episodic=20)  # every entry scores below theta_drop
    for i in range(8):
        e.schedule(f'@conversation:k:{i}', .3 + i / 1440, 'x', {'ana': {'text': f'Ben asked: did you see the red kite {i}?',
                   'source': 'ben', 'encountered': ['ben'], 'valence': -.6, 'arousal': .6}})
    e.advance(1.2)  # awake 16 h, then this step is a sleep opportunity
    assert all(m['tier'] == 'dropped' for m in e.agent('ana')['memory_meta'].values())
    seen = []
    def model(system, context, *rest, **kw):
        seen.append(context)
        return {'meaning': 'm', 'valence': 0, 'arousal': 0, 'importance': 0, 'confidence': .5}
    with patch('devsim.engine.validated_json', side_effect=model):
        assert e.consolidate('ana', batch_size=1) == 0
        cognition.reflect(e, 'ana', '@conversation:k:0', api='http://127.0.0.1:1', model='none')
        assert not seen, 'consolidation or reflection sent a dropped memory to the model'
        e.appraise('ana', {'text': 'Ben asked: did you see the red kite?', 'source': 'ben'})
    assert 'earlier_questions_from_speaker' not in seen[0] and 'kite' not in json.dumps(seen[0]['memories'])
    e.state['runtime'] = {'conversations': {'k': {'status': 'open', 'active': ['ana', 'ben'], 'spec': {'topic': 't'}}}}
    assert household.conversation_memory(e, 'ana')['this_conversation'] == []
    feelings = len(e.agent('ana')['affect_events'])
    e.recall('ana', '@conversation:k:0', 'reminder-of-dropped', rehearse=True, affect=True)
    assert len(e.agent('ana')['affect_events']) == feelings
    checks.append('dropped memories never reach the model again: not consolidated, reflected on, shown as earlier questions '
                  'or recent conversation, and a reminder brings back no feeling')

    source = inspect.getsource(sleep).lower()
    assert not any(word in source for word in ('focal', 'narciss', 'psychopath', "['role']", 'agent_type'))
    try:
        sleep.configure(world(configure=False), {'theta_drop': 2, 'theta_episodic': 1})
        raise AssertionError('inverted thresholds accepted')
    except ValueError:
        pass
    checks.append('no branch keyed on agent type, role or trait; invalid or inverted settings are rejected')

    result = {'passed': True, 'scope': 'synthetic engineering checks of design defaults (unverified); no calibrated sleep claim',
              'checks': checks}
    RESULTS_DIR.joinpath('sleep-engineering-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
