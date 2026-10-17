"""Received-evidence cognition policies. All thresholds are provisional.

Semantic selection uses the configured local LLM over bounded private memory
views, not an embedding service. Inspection remains pure; cognition is explicit.
"""
from copy import deepcopy
from collections import Counter
from hashlib import sha256
from math import exp, log, log1p
import json
import re


# Defaults for newly built policies (archived policies keep their own). All are engineering choices, not fitted values:
# meaning-based cueing via the local embedding service; mood reactivity from traits; exact words last one day; recall odds rise e^2 per unit score; a maximal mood strengthens encoding 1.5x;
# 12 background recalls a year at middle neuroticism, scaled by e^(neuroticism) (0.37x to 2.7x).
MEMORY_DEFAULTS = {'semantic_matching': True, 'affect_from_traits': True, 'verbatim_days': 1, 'recall_beta': 2, 'mood_encoding_weight': .5,
                   'rumination_per_year': 12, 'rumination_neuroticism': 1}


def configure(engine, settings):
    from .engine import number
    allowed = {'semantic_candidates', 'detail_threshold', 'fan_weight', 'rumination_per_year',
               'rumination_minimum_gap_days', 'boredom_weight', 'boredom_days', 'reflection', 'semantic_recall', 'indexed_retrieval', 'reference_resolution', 'autonomous_goals', 'graphiti_retrieval', 'semantic_matching', 'affect_from_traits',
               'verbatim_days', 'recall_beta', 'mood_encoding_weight', 'rumination_neuroticism'}
    if not isinstance(settings, dict) or set(settings) - allowed:
        raise ValueError('Unsupported cognition setting')
    for key in ('reflection', 'semantic_recall', 'indexed_retrieval', 'reference_resolution', 'autonomous_goals', 'graphiti_retrieval', 'semantic_matching', 'affect_from_traits'):
        if key in settings and not isinstance(settings[key], bool):
            raise ValueError('Cognition flags must be boolean')
    n = settings.get('semantic_candidates', 24)
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 64:
        raise ValueError('Semantic candidate count must be between 1 and 64')
    for key, default, low, high in [('detail_threshold', .45, 0, 1), ('fan_weight', .15, 0, 2),
            ('rumination_per_year', 12, 0, 365), ('rumination_minimum_gap_days', 1, .01, 36525),
            ('boredom_weight', .5, 0, 5), ('boredom_days', 3, .1, 365)]:
        number(settings.get(key, default), low, high, key)
    # Optional (absent = previous behaviour, so archived policies replay unchanged).
    for key, low, high in [('verbatim_days', 0, 36525), ('recall_beta', .01, 100), ('mood_encoding_weight', 0, 10),
                           ('rumination_neuroticism', 0, 5)]:
        if key in settings:
            number(settings[key], low, high, key)
    current = engine.state['config'].get('cognition')
    if current is not None and current != settings:
        raise ValueError('Cannot silently replace cognition policy')
    engine.state['config']['cognition'] = deepcopy(settings)
    if settings.get('graphiti_retrieval'):
        from uuid import uuid4
        engine.state['config'].setdefault('graphiti_namespace',uuid4().hex)


def words(text):
    return set(re.findall(r'\w+', text.lower())) - {'the','a','an','i','me','my','you','your','is','was','and','or','to','of','in','for','it','do','what','with'}


def gumbel(*parts):
    """Deterministic standard Gumbel noise from a hash of its inputs (no shared random state is consumed)."""
    u = (int(sha256(repr(parts).encode()).hexdigest()[:13], 16) + .5) / 16**13
    return -log(-log(u))


def views(engine, owner, query, limit, collapse=False):
    """Fan overload lowers access, never stored stability or original records.

    At low access only an already encoded subjective meaning/gist is exposed.
    No LLM is asked to reconstruct missing objective detail.
    """
    from .identity_state_prototype import recall_availability
    from .sleep import HIDDEN, lability
    agent = engine.agent(owner)
    settings = engine.state['config']['cognition']
    observations = engine.world.observations.get(owner, [])
    tags = {o.event_id:set(agent['memory_meta'][o.event_id].get('topics', [])) for o in observations}
    fan = Counter(tag for value in tags.values() for tag in value)
    query_words = words(query)
    focus = agent.get('retrieval_focus', {})
    focused = set(focus.get('ids', [])) if focus.get('day') == engine.day and focus.get('situation') == query else set()
    mood = engine.mood(owner)
    window = settings.get('verbatim_days')
    # Inhibition of return (Memory Decay Research report p.10): memories recalled again and again lately
    # are transiently harder to retrieve; stored stability is untouched. This is memory mechanics, like
    # forgetting; how a person feels and acts about repetition comes from their situational signatures.
    days = settings.get('boredom_days', 3)
    proneness = settings.get('boredom_weight', .5)
    recent = Counter()
    for r in agent.get('recall_log', []):
        if 0 <= engine.day - r['day'] <= 10 * days:
            recent[r['memory']] += exp(-(engine.day - r['day']) / days)
    def gist_of(obs):
        retained = [b['text'] for b in agent['beliefs'].values() if obs.event_id in b.get('evidence', [])]
        return agent['memory_meta'][obs.event_id].get('summary') or (' '.join(retained) if retained else None)
    # Meaning-based cueing ("shouted" finds "yelled"): cosine of local BGE embeddings via the Graphiti service.
    # Unreachable service -> word matching, flagged on every result rather than silent.
    similarity, matching = {}, 'lexical'
    if settings.get('semantic_matching') and query.strip():
        pool = list(dict.fromkeys(t for obs in observations for t in (obs.text, gist_of(obs)) if t))
        try:
            from .graphiti_bridge import vectors
            found = vectors([query, *pool])
            similarity = {t: sum(a*b for a, b in zip(found[0], v)) for t, v in zip(pool, found[1:])}
            matching = 'semantic'
        except (OSError, ValueError, KeyError):
            matching = 'lexical_fallback'
    result = []
    for obs in observations:
        meta = agent['memory_meta'][obs.event_id]
        tier = meta.get('tier')  # sleep policy: buffered = vivid but fragile; dropped/merged = not retrievable
        if tier in HIDDEN:
            continue
        age = engine.day - (meta['last_recall_day'] if meta['last_recall_day'] is not None else obs.day)
        base = lability(age, engine.state['config']['sleep']) if tier == 'buffer' else recall_availability(age, meta['stability_days'])
        related = [fan[t]-1 for t in tags[obs.event_id]]
        penalty = 1 + settings.get('fan_weight', .15) * log1p(max(related, default=0))
        access = base / penalty
        # Matching uses available representation, not hidden original details.
        detailed = tier == 'buffer' or (tier != 'gist' and access >= settings.get('detail_threshold', .45))
        gist = gist_of(obs)
        # Fuzzy-trace (Graph DB Memory Decay Implementation p.9): exact wording fades within verbatim_days of the
        # event, rehearsal or not; the gist stays. Without any gist the original stays visible.
        exact = detailed and (window is None or engine.day - obs.day <= window or not gist)
        text = obs.text if exact else gist
        if not text:
            continue
        overlap = len(query_words & words(text + ' ' + ' '.join(tags[obs.event_id])))
        # BGE cosine: related sentences measured ~0.7, unrelated 0.37-0.48 on this project's text. A 0.7 match is worth
        # one shared word; a faded memory needs 0.6 to be cued. shortcut: hand-set from 8 pairs; tune on run data.
        sim = similarity.get(text)
        meaning_match = 15 * max(0, sim - .5) if sim is not None else 0
        if not detailed and not overlap and (sim is None or sim < .6) and obs.event_id not in focused and query:
            continue
        boredom = 1 + proneness * recent[obs.event_id]
        score = (3*overlap + meaning_match + access + meta['importance'] + .2*mood['valence']*obs.valence) / boredom \
            + (10 if obs.event_id in focused else 0)
        result.append({'event':obs.event_id, 'day':obs.day, 'text':text, 'source':obs.source,
            'kind':meta['kind'], 'meaning':meta['meaning'] if detailed else gist, 'confidence':meta['confidence'],
            'availability':access, 'provenance':meta['provenance'], 'score':score,
            'representation':'episodic_detail' if exact else 'subjective_gist',
            'original_detail_available':detailed, 'exact_words':exact, 'interference_factor':penalty, 'boredom_factor':round(boredom,3),
            'topics':sorted(tags[obs.event_id]), **({'matching':matching} if matching != 'lexical' else {}),
            **({'similarity':round(sim,3)} if sim is not None else {})})
    beta = settings.get('recall_beta')
    if beta:
        # Modern Hopfield retrieval (Ramsauer et al. 2020, Eq. 22: softmax(beta * similarity)): recall is a draw,
        # P ∝ exp(beta * score), taken without replacement via Gumbel keys seeded by the query, so inspection and
        # replay stay deterministic. Low beta lets the mind wander to weaker matches; high beta is near-greedy.
        for r in result:
            r['sample_key'] = beta * r['score'] + gumbel(engine.state.get('seed'), owner, r['event'], engine.day, query)
        result.sort(key=lambda r:(r['sample_key'],r['day'],r['event']), reverse=True)
    else:
        result.sort(key=lambda r:(r['score'],r['day'],r['event']), reverse=True)
    if collapse:
        # Memory collision: identical memories are linked, never merged or deleted (Graphiti/A-MEM style; Mem0's
        # deleting resolver lost facts). The best-ranked copy represents the rest with a count and first day.
        groups = {}
        for r in result:
            groups.setdefault((r['text'].strip().lower(), r['source']), []).append(r)
        for copies in groups.values():
            if len(copies) > 1:
                copies[0].update(times=len(copies), first_day=min(c['day'] for c in copies))
        result = [copies[0] for copies in groups.values()]
    return result[:limit]


def semantic_recall(engine, owner, situation, *, api, model):
    """One bounded, explicit semantic retrieval stage before appraisal/action.

    A truncated candidate scan is recorded. No unavailable/private-other detail
    is sent. Selected gist does not reset the original-detail forgetting clock.
    """
    from .engine import validated_json, InvalidModelOutput
    agent = engine.agent(owner)
    if not agent['alive']:
        raise ValueError('Dead agent cannot retrieve')
    settings = engine.state['config'].get('cognition', {})
    if not settings.get('semantic_recall', True):
        return []
    previous = agent.get('retrieval_focus', {})
    if previous.get('day') == engine.day and previous.get('situation') == situation:
        return previous['ids']
    queries = []
    graph_info = None
    candidates = None
    if settings.get('graphiti_retrieval',False):
        try:
            from .graphiti_bridge import candidates as graph_candidates
            candidates, graph_info = graph_candidates(engine,owner,situation,settings.get('semantic_candidates',24))
        except (OSError,ValueError,RuntimeError,TimeoutError) as exc:
            # A graph outage never grants access to broader data. The existing
            # private FTS path remains usable and the downgrade is recorded.
            graph_info={'backend':'graphiti','status':'fallback_private_fts','error':str(exc)[:400]}
    if candidates is None and settings.get('indexed_retrieval',False):
        from .retrieval import candidates as indexed_candidates
        candidates, queries = indexed_candidates(engine,owner,situation,api=api,model=model,
                                                 limit=settings.get('semantic_candidates',24))
    elif candidates is None:
        candidates = views(engine, owner, '', settings.get('semantic_candidates',24))
    if not candidates:
        return []
    context = engine.context(owner, situation)
    context.update(task='semantic_recall', memory_candidates=candidates)
    system = ('Select up to three supplied memory event ids that bear on the current situation by meaning, '
              'including paraphrases and analogous experiences, not just matching words. '
              'Use only supplied representations. A subjective_gist is an uncertain retained interpretation, '
              'not access to original details. Return JSON with memory_ids (distinct supplied ids). Empty is allowed.')
    # The context's own accessible memories are also shown to the model; citing one is not an invention
    # (the overnight environment run died after three such citations).
    allowed = {r['event']:r for r in [*context.get('memories',[]), *candidates]}
    def validate(result):
        ids = result.get('memory_ids')
        if not isinstance(ids,list) or len(ids)>3 or not all(isinstance(x,str) for x in ids) or len(set(ids))!=len(ids) or any(x not in allowed for x in ids):
            raise ValueError('Semantic retrieval cited unavailable memory')
    try:
        result = validated_json(system,context,validate,api,model,200)
    except InvalidModelOutput as exc:
        engine.skip_model_step('semantic_recall', owner, exc)
        return []
    digest = sha256(json.dumps([engine.day,situation]).encode()).hexdigest()[:16]
    for mid in result['memory_ids']:
        engine.recall(owner,mid,f'{owner}:semantic:{digest}:{mid}',
            rehearse=allowed[mid]['original_detail_available'],affect=True)
    agent['retrieval_focus'] = {'day':engine.day,'situation':situation,'ids':result['memory_ids'],
        'policy':'local_llm_semantic_selection','candidate_count':len(candidates),
        'omitted_candidates':max(0,len(agent['memory_meta'])-len(candidates)),
        'retrieval_queries':queries,'indexed_corpus':bool(settings.get('indexed_retrieval',False)),
        **({'graph_retrieval':graph_info} if graph_info is not None else {})}
    return result['memory_ids']


def reflect(engine, owner, evidence_id, *, api, model):
    """Gate meaning changes on received evidence; original events stay immutable."""
    from .engine import validated_json, number, InvalidModelOutput
    agent = engine.agent(owner)
    if not agent['alive'] or evidence_id not in agent['memory_meta']:
        raise ValueError('Reflection requires a living agent and received evidence')
    update_id = f'{owner}:reflection:{evidence_id}'
    if any(u['id']==update_id for u in engine.state['updates']):
        return
    observed = next(o for o in engine.world.observations[owner] if o.event_id==evidence_id)
    context = engine.context(owner, observed.text)
    context['memories'] = [m for m in context['memories'] if m['event'] != evidence_id]
    context.update(task='reflect_received_evidence', new_evidence={
        'event':evidence_id,'text':observed.text,'kind':agent['memory_meta'][evidence_id]['kind'],
        'source':observed.source,'meaning':agent['memory_meta'][evidence_id]['meaning']},
        previous_narrative=deepcopy(agent.get('narrative_identity')),
        pending_reinterpretations=deepcopy(agent.get('reinterpretation_queue',[])[-8:]),
        revision_target_ids=[m['event'] for m in context['memories']])
    available = {x['event'] for x in context['memories']} | {evidence_id}
    # Narrative evidence may refer to retained gist sources, without exposing episodes.
    for belief in context['beliefs'].values():
        available.update(belief['evidence'])
    targets = set(context['heard_about']) | set(context['relationships'])
    goal_capacity=max(0,8-sum(g['status']=='active' for g in agent['goals'].values()))
    if context['identity']['age_years']<2: goal_capacity=0
    if engine.state['config'].get('cognition',{}).get('autonomous_goals'):
        context['new_goal_capacity']=min(2,goal_capacity)
    system = ('Reflect as this fictional agent on received evidence. Return JSON with summary (short retained '
        'subjective gist of new_evidence), topics (up to five short topic labels), revisions (up to three objects '
        'with memory_id from revision_target_ids (never new_evidence itself), decision retain/defer/revise, '
        'reason, meaning, confidence 0..1, '
        'and evidence including the target and new_evidence event ids), narrative (null or object with text, '
        'confidence 0..1 and nonempty supplied evidence ids), plans (up to three objects with an existing '
        'active goal_id and steps list), probes (up to two objects with target_id from heard_about or '
        'relationships, question, reason, evidence), and relationship_updates (optional list of at most two '
        'objects with target_id directly encountered in new_evidence, trust_delta and closeness_delta '
        'each between -0.05 and 0.05, reason, evidence including new_evidence). Treat these as subjective '
        'expectation changes, never verification of a claim. Revise only when new evidence changes the meaning of '
        'the earlier experience; mere repetition does not suffice. Defer unresolved contradictory accounts. '
        'Narrative is a subjective evolving self-story, not a diagnosis or new events. Testimony remains '
        'testimony. Questions express curiosity; they do not establish claims, existence or acquaintance. '
        'Empty lists and null narrative are valid. Never restore or invent lost original detail.')
    if 'new_goal_capacity' in context:
        system += (' You may also return new_goals, at most new_goal_capacity objects with description, '
            'priority 0..1 and evidence. These are self-set intentions for a small achievable next step, '
            'never achievements, external obligations or new world facts. Use [] when no new goal is needed.')
    infant=engine.state['config'].get('expression',{}).get('age_appropriate_actions',False) and context['identity']['age_years']<2
    if infant:
        system += ' For this infant use a simple sensory/affective summary; narrative must be null, plans and probes must be [], and do not invent adult verbal self-reflection.'
    def text(value,label):
        if not isinstance(value,str) or not value.strip() or len(value)>1800:
            raise ValueError(label+' needs bounded nonempty text')
    def sources(value):
        if not isinstance(value,list) or not value or not all(isinstance(x,str) and x in available for x in value):
            raise ValueError('Reflection cites unavailable evidence')
    def validate(result):
        text(result.get('summary'),'Summary')
        topics=result.get('topics')
        if not isinstance(topics,list) or len(topics)>5 or not all(isinstance(t,str) and 0<len(t)<=60 for t in topics):
            raise ValueError('Invalid memory topics')
        for field, maximum in [('revisions',3),('plans',3),('probes',2)]:
            if not isinstance(result.get(field),list) or len(result[field])>maximum:
                raise ValueError('Invalid reflection '+field)
        seen=set()
        for revision in result['revisions']:
            mid=revision.get('memory_id')
            if mid not in {m['event'] for m in context['memories']} or mid==evidence_id or mid in seen:
                raise ValueError('Revision target must be a distinct earlier memory in revision_target_ids; never new_evidence. Use revisions: [] if none need reconsideration.')
            seen.add(mid)
            if revision.get('decision') not in ('retain','defer','revise'):
                raise ValueError('Invalid revision gate')
            text(revision.get('reason'),'Revision reason'); text(revision.get('meaning'),'Meaning')
            number(revision.get('confidence'),0,1,'revision confidence'); sources(revision.get('evidence'))
            if mid not in revision['evidence'] or evidence_id not in revision['evidence']:
                raise ValueError('Revision requires both original and new evidence')
        narrative=result.get('narrative')
        if infant and (narrative is not None or result['plans'] or result['probes']):
            raise ValueError('Infant reflection must omit verbal narrative, plans and questions')
        if narrative is not None:
            text(narrative.get('text'),'Narrative'); number(narrative.get('confidence'),0,1,'narrative confidence'); sources(narrative.get('evidence'))
        for plan in result['plans']:
            if plan.get('goal_id') not in agent['goals'] or agent['goals'][plan['goal_id']]['status']!='active':
                raise ValueError('Replanning requires an existing active goal')
            if not isinstance(plan.get('steps'),list) or len(plan['steps'])>8:
                raise ValueError('Invalid plan steps')
            for step in plan['steps']: text(step,'Plan step')
        for probe in result['probes']:
            if probe.get('target_id') not in targets:
                raise ValueError('Probe target is not known to listener')
            text(probe.get('question'),'Question'); text(probe.get('reason'),'Probe reason'); sources(probe.get('evidence'))
        goals=result.get('new_goals',[])
        if not isinstance(goals,list) or len(goals)>context.get('new_goal_capacity',0):
            raise ValueError('New goals exceed available intentional capacity')
        for goal in goals:
            text(goal.get('description'),'New goal');number(goal.get('priority'),0,1,'new goal priority');sources(goal.get('evidence'))
        social = result.get('relationship_updates', [])
        if not isinstance(social,list) or len(social)>2:
            raise ValueError('Invalid social expectation updates')
        seen_targets = set()
        for update in social:
            target = update.get('target_id')
            if target not in agent['memory_meta'][evidence_id]['encountered'] or target in seen_targets:
                raise ValueError('Social expectation changes need a distinct directly encountered target')
            seen_targets.add(target)
            number(update.get('trust_delta'),-.05,.05,'trust delta')
            number(update.get('closeness_delta'),-.05,.05,'closeness delta')
            text(update.get('reason'),'Social update reason'); sources(update.get('evidence'))
            if evidence_id not in update['evidence']:
                raise ValueError('Social update requires current received evidence')
    try:
        result=validated_json(system,context,validate,api,model,1500)
    except InvalidModelOutput as exc:
        return engine.skip_model_step('reflection', owner, exc)
    # All suboperations below are prevalidated, and the controller rolls back the
    # whole event on transport or validation failure.
    agent['memory_meta'][evidence_id].update(summary=result['summary'],topics=list(dict.fromkeys(t.lower() for t in result['topics'])))
    for revision in result['revisions']:
        mid=revision['memory_id']
        record={**deepcopy(revision),'day':engine.day,'new_evidence':evidence_id}
        if revision['decision']=='revise':
            engine.revise(owner,mid,revision['meaning'],revision['confidence'],revision['evidence'],update_id+':'+mid)
            agent['memory_meta'][mid]['summary'] = revision['meaning']
        agent.setdefault('reinterpretation_queue',[])[:] = [r for r in agent.get('reinterpretation_queue',[]) if r['memory_id']!=mid]
        if revision['decision']=='defer': agent['reinterpretation_queue'].append(record)
    if result.get('narrative') is not None:
        agent.setdefault('narrative_versions',[]).append(deepcopy(agent.get('narrative_identity')))
        agent['narrative_identity']={**deepcopy(result['narrative']),'day':engine.day,'policy':'subjective_evidence_linked_model_inference'}
    for plan in result['plans']:
        goal=agent['goals'][plan['goal_id']]
        goal.setdefault('plan_versions',[]).append({'day':engine.day,'plan':list(goal['plan']),'evidence':evidence_id})
        goal['plan']=list(plan['steps'])
        from .goal_plans import request_replan
        request_replan(goal)
    for index,goal in enumerate(result.get('new_goals',[])):
        key='self-goal-'+sha256(f'{update_id}:{index}'.encode()).hexdigest()[:16]
        engine.goal(owner,key,goal['description'],priority=goal['priority'])
        agent['goals'][key].update(origin='self_set_intention',evidence=list(goal['evidence']))
    for index,probe in enumerate(result['probes']):
        agent.setdefault('probe_queue',[]).append({**deepcopy(probe),'id':f'{update_id}:probe:{index}',
            'status':'pending','day':engine.day})
    for update in result.get('relationship_updates', []):
        relation = agent['relationships'][update['target_id']]
        relation.setdefault('versions', []).append({'day':engine.day,'trust':relation['trust'],
            'closeness':relation['closeness'],'evidence':list(update['evidence']),'reason':update['reason']})
        for field in ('trust','closeness'):
            from math import floor
            budget = agent.setdefault('social_update_budget', {})
            key = f'{floor(engine.day)}:{update["target_id"]}:{field}'
            remaining = max(0,.05-budget.get(key,0))
            delta = max(-remaining,min(remaining,update[field+'_delta']))
            relation[field] = min(1,max(0,relation[field]+delta))
            budget[key] = budget.get(key,0)+abs(delta)
    engine.state['updates'].append({'id':update_id,'kind':'reflection','owner':owner,'day':engine.day,
        'evidence':[evidence_id],'revision_decisions':deepcopy(result['revisions'])})


def neuroticism(agent):
    """Mean N1-N6 percentile mapped to -1..1 (0 = population middle)."""
    facets=agent.get('facets',{})
    return (sum(facets.get(f'N{i}',50) for i in range(1,7))/6-50)/50


def ruminate(engine,owner,event_id,minimum_gap_days=1):
    """Autonomous scheduled recall, not background world fabrication."""
    agent=engine.agent(owner)
    if not agent['alive']:
        return None
    previous=agent.get('last_autonomous_recall')
    if previous is not None and engine.day-previous<minimum_gap_days:
        return None
    candidates=views(engine,owner,'',64)
    if not candidates: return None
    settings=engine.state['config']['cognition']
    mood=engine.mood(owner)['valence']
    valence={o.event_id:o.valence for o in engine.world.observations[owner]}
    # Memory Decay Research ("phantom" access) and Mood and Memory (neuroticism -> rumination, strong evidence):
    # higher neuroticism leans background recall toward negative memories. shortcut: linear, provisional weight.
    lean=settings.get('rumination_neuroticism',0)*max(0,neuroticism(agent))
    def value(r):
        v=valence[r['event']]
        return (agent['memory_meta'][r['event']]['importance']+.3*r['availability']+(.2 if mood and mood*v>0 else 0)
                +lean*max(0,-v))
    beta=settings.get('recall_beta')
    selected=max(candidates,key=lambda r:((beta*value(r)+gumbel(engine.state.get('seed'),owner,event_id,r['event'])) if beta
                                          else value(r),r['event']))
    engine.recall(owner,selected['event'],event_id,rehearse=selected['original_detail_available'],affect=True)
    agent['last_autonomous_recall']=engine.day
    return selected['event']
