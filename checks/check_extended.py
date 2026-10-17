"""Cognition, constrained expansion and world/planning integration regressions."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devsim.engine import Engine,FACET_NAMES
from devsim.lifetime import Lifetime
from devsim import cognition
from devsim import life_policy

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
def world():
    e=Engine(seed=12)
    for owner in ('a','b','private'):
        e.entity(owner,owner.upper(),{'birth_day':-30*365.25})
        e.materialize(owner,dict.fromkeys(FACET_NAMES,50),birth_day=-30*365.25)
    e.goal('a','work','Make useful work',priority=.8)
    e.goal('a','rest','Make time for rest',priority=.6)
    e.agent('a')['resources']={'money':10}
    e.schedule('episode',0,'A receives a setback.',{'a':{'text':'The red numbered folder 918 was rejected.',
        'source':'direct','meaning':'My red numbered folder 918 was rejected.','importance':.8,'valence':-.6}})
    e.schedule('secret',0,'Private receives unrelated information.',{'private':{'text':'PRIVATE_PERSON_SECRET','source':'direct'}})
    e.advance(0)
    return e


def reject(call):
    try: call()
    except (ValueError,RuntimeError): return
    raise AssertionError('Invalid operation accepted')


def reflection(context):
    event=context['new_evidence']['event']
    assert event not in {m['event'] for m in context['memories']}, 'New evidence was offered as its own revision target'
    earlier='episode' if event!='episode' and any(m['event']=='episode' for m in context['memories']) else None
    return {'summary':'A difficult experience left me unsure of how my work is received.',
        'topics':['evaluation','work'], 'revisions':([] if not earlier else [{
        'memory_id':earlier,'decision':'revise','reason':'The received response offers another interpretation.',
        'meaning':'A setback need not mean a permanent rejection of me.','confidence':.6,'evidence':[earlier,event]}]),
        'narrative':{'text':'I am learning how to respond to setbacks.','confidence':.6,'evidence':[event]},
        'plans':([{'goal_id':'work','steps':['Try a different approach.']}] if context['goals'].get('work',{}).get('status')=='active' else []),'probes':[]}


def stub(system,context,api,model,max_tokens=600):
    assert 'PRIVATE_PERSON_SECRET' not in json.dumps(context)
    task=context.get('task')
    if task=='semantic_recall':
        return {'memory_ids':[context['memory_candidates'][0]['event']]}
    if task=='reflect_received_evidence': return reflection(context)
    if task=='expand_constrained_background':
        return {'choices':{k:0 for k in context['slots']},'milestone_ids':[m['id'] for m in context['milestone_alternatives']],
                'summary':'A bounded synthetic background chosen from committed alternatives.'}
    if 'new_observation' in context:
        return {'meaning':'I interpreted the received experience.','valence':.1,'arousal':.2,'importance':.6,'confidence':.7}
    return {'action_id':context['available_actions'][0]['id'],'action':'Take the offered step.',
            'speech':'Let us work on this.','goal_id':None,'plan':[],'memory_ids':[]}


def policy():
    return {'sampling':'event_driven','cognition':{'semantic_recall':True,'reflection':True,
        'rumination_per_year':8,'semantic_candidates':12},'planning':{'hours_per_day':3},
        'opportunities':[{'id':'work','actor':'a','rate_per_year':20,'min_age':0,'max_age':100,
            'situation':'How should I respond to an unfavorable evaluation?', 'cues':['work'],
            'options':[{'id':'try','label':'Try the work differently.','goal_id':'work','duration_hours':2,'costs':{'money':1},
                'success_probability':1,'success_text':'My attempt helped.','failure_text':'My attempt did not help.',
                'valence_success':.3,'valence_failure':-.2,'progress_gain':.1,
                'effects_success':{'resources':{'a':{'money':2}},'facts':{'a':{'employment':'project-worker'}}}}]}]}


def memory_physics():
    """Exact-word fading, Hopfield-style sampled recall, neuroticism rumination and mood-strengthened encoding."""
    from devsim.engine import InvalidModelOutput
    checks=[]
    long='Kiara, the dance is just logistics; my closed-loop feedback system with real-time latency compensation is the only thing keeping this together.'
    e=world(); cognition.configure(e,{'verbatim_days':1})
    gist=lambda s,c,a,m,t=600: {**stub(s,c,a,m,t),'gist':'Rohan said his robot code matters more than the dance.'}
    with patch('devsim.engine.request_json',side_effect=stub):
        try: e.appraise('a',{'text':'Rohan said: '+long,'source':'b'},api='stub',model='stub'); raise AssertionError('gist missing')
        except InvalidModelOutput: pass
    with patch('devsim.engine.request_json',side_effect=gist):
        heard=e.appraise('a',{'text':'Rohan said: '+long,'source':'b'},api='stub',model='stub')
    e.schedule('rohan-line',e.day,'Rohan speaks.',{'a':heard}); e.advance(e.day)
    seen=lambda: next(v for v in cognition.views(e,'a','robot dance',30) if v['event']=='rohan-line')
    assert seen()['text']=='Rohan said: '+long and seen()['exact_words']
    e.advance(e.day+2)
    later=seen()
    assert later['text']==heard['gist'] and not later['exact_words'] and later['original_detail_available']
    assert e.world.observations['a'][-1].text=='Rohan said: '+long  # the stored original is untouched
    assert next(v for v in cognition.views(e,'a','folder rejected',30) if v['event']=='episode')['exact_words']  # no gist: kept
    plain=world(); plain.schedule('line',plain.day,'Speech.',{'a':{'text':long,'source':'b','gist':'A short gist.'}})
    plain.advance(plain.day+2); cognition.configure(plain,{})
    assert next(v for v in cognition.views(plain,'a','dance',30) if v['event']=='line')['text']==long  # setting absent: unchanged
    reject(lambda: world().schedule('bad',0,'x',{'a':{'text':'x','source':'b','gist':''}}))
    checks.append('with verbatim_days, appraisal must return a short gist; exact words are shown only within the window, '
                  'then the gist while the episode stays accessible; originals are stored unchanged; without the setting nothing changes')

    # Meaning-based cueing: a faded memory sharing no words with the cue is found by meaning; fallback is flagged.
    concepts=[{'shouted','yelled','screamed'},{'father','dad'},{'robot','arm'}]
    def fake(texts):
        out=[]
        for t in texts:
            w=set(cognition.words(t)); v=[float(bool(w&c)) for c in concepts]+[.3]; n=sum(x*x for x in v)**.5; out.append([x/n for x in v])
        return out
    m=world(); cognition.configure(m,{'semantic_matching':True})
    m.schedule('dad',0,'Childhood.',{'a':{'text':'Father yelled loudly.','source':'direct','importance':.3,'gist':'My father yelled at me.'}}); m.advance(400)
    cue='Rohan shouted today.'
    with patch('devsim.graphiti_bridge.vectors',side_effect=fake):
        found=next(v for v in cognition.views(m,'a',cue,30) if v['event']=='dad')
    assert found['similarity']>.6 and found['matching']=='semantic' and not found['original_detail_available']
    # Ranking too: with no shared words, the meaning match outranks an unrelated memory the tie-break would favour.
    m.schedule('aaa-related',m.day,'Earlier.',{'a':{'text':'Dad screamed again.','source':'direct','importance':.4}}); m.advance(m.day)
    m.schedule('zzz-unrelated',m.day+.01,'Later.',{'a':{'text':'The arm jammed.','source':'direct','importance':.4}}); m.advance(m.day+.01)
    with patch('devsim.graphiti_bridge.vectors',side_effect=fake):
        ranked=[v['event'] for v in cognition.views(m,'a',cue,30) if v['event'] in ('aaa-related','zzz-unrelated')]
    assert ranked==['aaa-related','zzz-unrelated']
    lexical=deepcopy(m); lexical.state['config']['cognition']={}
    assert all(v['event']!='dad' for v in cognition.views(lexical,'a',cue,30))
    m.schedule('now',m.day,'Lunch.',{'a':{'text':'Rohan shouted today at lunch.','source':'direct'}}); m.advance(m.day)
    with patch('devsim.graphiti_bridge.vectors',side_effect=OSError('service down')):
        down=cognition.views(m,'a',cue,30)
    assert down and all(v['matching']=='lexical_fallback' for v in down) and all(v['event']!='dad' for v in down)
    checks.append('semantic_matching cues a faded memory by meaning ("shouted" finds "yelled") with no shared words; '
                  'an unreachable embedding service falls back to word matching, flagged on every result')

    # Hopfield-style recall: P ∝ exp(beta * score), deterministic per query, read-only.
    def crowd(beta):
        w=world(); cognition.configure(w,{'recall_beta':beta} if beta else {})
        for i in range(12):
            w.schedule(f'm{i}',0,'Robot.',{'a':{'text':f'Robot practice {i}.','source':'direct','importance':i/12}})
        w.advance(1); return w
    order=lambda w,q='robot practice': [v['event'] for v in cognition.views(w,'a',q,12)]
    greedy,sharp,loose=crowd(None),crowd(100),crowd(.01)
    before=deepcopy(loose.state)
    assert order(sharp)==order(greedy) and order(loose)!=order(greedy) and order(loose)==order(loose) and loose.state==before
    tops=lambda w: sum(order(w,f'robot practice {q}')[0]=='m11' for q in ('a','b','c','d','e','f','g','h','i','j'))
    assert tops(crowd(3))>tops(crowd(.01))
    checks.append('recall_beta samples memories in proportion to exp(beta * score): high beta matches greedy ranking, low beta wanders, '
                  'the draw is deterministic per query and inspection stays read-only')

    # Neuroticism: more frequent background recall, leaning toward negative memories.
    def person(n,k):
        w=Engine(seed=12); w.entity('a','A',{'birth_day':-30*365.25}); w.materialize('a',dict.fromkeys(FACET_NAMES,50),birth_day=-30*365.25)
        cognition.configure(w,{'rumination_per_year':12,'rumination_neuroticism':k})
        w.agent('a')['facets'].update({f'N{i}':n for i in range(1,7)})
        w.schedule('good',0,'Praise.',{'a':{'text':'My work was praised.','source':'direct','importance':.6,'valence':.6}})
        w.schedule('bad',0,'Mockery.',{'a':{'text':'I was mocked at lunch.','source':'direct','importance':.5,'valence':-.6}})
        w.advance(0); return w
    rate=lambda n,k: Lifetime(person(n,k),{'sampling':'event_driven','opportunities':[],
        'cognition':{'rumination_per_year':12,'rumination_neuroticism':k}},scripted=True)._rumination_rate('a')
    assert rate(90,1)>rate(50,1)==12>rate(10,1) and rate(90,0)==rate(10,0)==12
    pick=lambda n,k: cognition.ruminate(person(n,k),'a','a:ruminate:0')
    assert pick(90,0)=='good' and pick(90,2)=='bad' and pick(10,2)=='good'
    checks.append('rumination_neuroticism raises background recall rate with neuroticism and leans it toward negative memories; k=0 is unchanged')

    # Mood and Memory pathway 1: a strong mood at encoding makes the new memory more durable.
    def encoded(weight,explicit=None):
        w=world(); cognition.configure(w,{'mood_encoding_weight':weight} if weight else {})
        w.schedule('blow',w.day,'Loss.',{'a':{'text':'A loss.','source':'direct','valence':-1,'arousal':1}}); w.advance(w.day)
        w.schedule('next',w.day,'Note.',{'a':{'text':'A note.','source':'direct',**({'stability_days':explicit} if explicit else {})}})
        w.advance(w.day); return w.agent('a')['memory_meta']['next']['stability_days']
    assert encoded(1)>encoded(0) and encoded(1,5.0)==encoded(0,5.0)==5.0
    checks.append('mood_encoding_weight strengthens memories encoded in a strong mood; explicit stability and the default are unchanged')

    # Mood reactivity from current traits (Mood and Memory trait table), normalized so an average person is unchanged.
    def tempered(n,e_=50,explicit=None):
        w=Engine(seed=3); w.entity('a','A',{'birth_day':-9000}); w.materialize('a',dict.fromkeys(FACET_NAMES,50),birth_day=-9000,affect=explicit)
        w.agent('a')['facets'].update({**{f'N{i}':n for i in range(1,7)},**{f'E{i}':e_ for i in range(1,7)}})
        cognition.configure(w,{'affect_from_traits':True}); return w
    mid,anxious,outgoing=tempered(50).affect('a'),tempered(90).affect('a'),tempered(50,90).affect('a')
    assert mid=={'recovery_multiplier':1,'positive_reactivity':1,'negative_reactivity':1,'rumination_fraction':.25}
    assert anxious['negative_reactivity']>1 and anxious['recovery_multiplier']>1 and anxious['rumination_fraction']>.25
    assert outgoing['positive_reactivity']>1 and outgoing['negative_reactivity']==1
    assert tempered(90,explicit={'negative_reactivity':.5}).affect('a')['negative_reactivity']==.5 and world().affect('a')=={}
    def hit(w): w.schedule('insult',w.day,'Insult.',{'a':{'text':'Mocked.','source':'direct','valence':-.5,'arousal':.3}}); w.advance(w.day); return w.mood('a')['valence']
    assert hit(tempered(90))<hit(tempered(10))
    checks.append('affect_from_traits derives reactivity, inertia and rumination from current neuroticism/extraversion; '
                  'an average person is unchanged and explicit affect_parameters win')

    # Average mood kernel: steady mild days stay mild where summed kernels saturate; strong events still dominate.
    def stream(kernel,big=False):
        w=Engine(seed=4,mood_kernel=kernel); w.entity('a','A',{'birth_day':-9000}); w.materialize('a',dict.fromkeys(FACET_NAMES,50),birth_day=-9000)
        for i in range(300):
            w.schedule(f's{i}',i/10,'Chatter.',{'a':{'text':f'Small talk {i}.','source':'direct','valence':.1,'arousal':.2}})
        if big: w.schedule('loss',30,'Loss.',{'a':{'text':'A friend moved away.','source':'direct','valence':-.9,'arousal':.9}})
        w.advance(30); return w.mood('a')
    calm,summed=stream('average'),stream('power_law')
    assert summed['arousal']>.9 and calm['arousal']<.3 and 0<calm['valence']<.2
    assert stream('average',True)['valence']<-.2  # one strong loss flips a day of mild chatter (+0.04 -> about -0.28)
    assert Engine(seed=5,mood_kernel='average').state['config']['mood_kernel']=='average'
    checks.append('the average mood kernel keeps a steady stream of mild events mild (the power-law sum saturates arousal), '
                  'lets a strong event dominate, and stays within bounds')
    return checks


def main():
    checks=[]
    e=world(); cognition.configure(e,{'reflection':True,'rumination_per_year':8})
    original=deepcopy(e.world.observations)
    with patch('devsim.engine.request_json',side_effect=stub): cognition.reflect(e,'a','episode',api='stub',model='stub')
    assert e.agent('a')['narrative_identity']['evidence']==['episode']
    assert e.agent('a')['goals']['work']['plan']==['Try a different approach.']
    e.advance(1000)
    view=e.memories('a','work evaluation')[0]
    assert view['representation']=='subjective_gist' and '918' not in json.dumps(view)
    stability=e.agent('a')['memory_meta']['episode']['stability_days']
    with patch('devsim.engine.request_json',side_effect=stub): cognition.semantic_recall(e,'a','An unfavorable assessment',api='stub',model='stub')
    assert e.agent('a')['retrieval_focus']['ids']==['episode']
    assert e.agent('a')['memory_meta']['episode']['stability_days']==stability
    assert e.agent('a')['memory_meta']['episode']['last_recall_day'] is None
    before=deepcopy(e.state)
    for _ in range(4): e.context('a','An unfavorable assessment')
    assert e.state==before
    checks+=['semantic selection before decisions from own available representations','gist-only recall cannot restore original detail or reset encoding clock','inspection remains read-only','evidence-linked narrative and replanning']
    # Association overload changes access but not the encoding parameter.
    baseline=view['availability']
    for i in range(4):
        e.schedule('similar'+str(i),e.day,'Another evaluation.',{'a':{'text':'Another evaluation.', 'source':'direct','meaning':'An evaluation occurred.'}})
        e.advance(e.day); e.agent('a')['memory_meta']['similar'+str(i)].update(summary='Another evaluation.',topics=['evaluation','work'])
    assert next(v for v in e.memories('a','work evaluation',30) if v['event']=='episode')['availability']<baseline
    checks.append('fan overload lowers retrieval accessibility without destroying storage')
    # The overnight environment run died when recall cited a memory shown in context but not among candidates.
    e.state['config']['cognition']['semantic_candidates']=1
    def cite(choose):
        return lambda s,c,a,m,t=600: {'memory_ids':choose(c)} if c.get('task')=='semantic_recall' else stub(s,c,a,m,t)
    shown=lambda c:[next(m['event'] for m in c['memories'] if m['event'] not in {x['event'] for x in c['memory_candidates']})]
    with patch('devsim.engine.request_json',side_effect=cite(shown)): cited=cognition.semantic_recall(e,'a','Another evaluation at work',api='stub',model='stub')
    assert len(cited)==1 and cited[0] in e.agent('a')['memory_meta']
    before=deepcopy(e.agent('a'))
    with patch('devsim.engine.request_json',side_effect=cite(lambda c:['never-received'])):
        assert cognition.semantic_recall(e,'a','A further evaluation',api='stub',model='stub')==[]
    assert e.agent('a')==before and e.state['runtime']['skipped_model_steps'][-1]['step']=='semantic_recall'
    del e.state['config']['cognition']['semantic_candidates']
    checks.append('semantic recall accepts a memory already shown in its own context; ids never shown are rejected, and after failed repairs the optional step is skipped and recorded instead of ending the run')
    # Boredom (inhibition of return): identical memories tie until one is recalled again and again.
    for twin in ('twin-1','twin-2'):
        e.schedule(twin,e.day,'The robot arm jammed.',{'a':{'text':'The robot arm jammed.','source':'direct','meaning':'A jam.','importance':.5}})
    e.advance(e.day)
    shown=[v for v in e.memories('a','robot arm jammed',30) if v['event'].startswith('twin')]
    assert len(shown)==1 and shown[0]['times']==2 and len(e.agent('a')['memory_meta'])==len(e.world.observations['a'])
    checks.append('identical memories collide into one context entry with a count; both stay stored')
    rank=lambda: next(v for v in cognition.views(e,'a','robot arm jammed',30) if v['event'].startswith('twin'))
    assert rank()['event']=='twin-2' and rank()['boredom_factor']==1
    stability=e.agent('a')['memory_meta']['twin-2']['stability_days']
    for i in range(4): e.recall('a','twin-2',f'a:bored:{i}')
    assert rank()['event']=='twin-1' and e.agent('a')['memory_meta']['twin-2']['stability_days']==stability
    factor=lambda: next(v for v in cognition.views(e,'a','robot arm jammed',30) if v['event']=='twin-2')['boredom_factor']
    assert factor()>1
    e.advance(e.day+31); assert factor()==1
    checks.append('inhibition of return transiently lowers retrieval of over-recalled memories, then fades; storage unchanged')
    # Received new evidence may revise meaning but not original episodes.
    with patch('devsim.engine.request_json',side_effect=stub): cognition.reflect(e,'a','similar0',api='stub',model='stub')
    assert e.agent('a')['memory_meta']['episode']['versions']
    assert e.world.observations['a'][0]==original['a'][0]
    before=deepcopy(e.state)
    with patch('devsim.engine.request_json',return_value={'summary':'Bad','topics':[],'revisions':[],
            'narrative':{'text':'Bad','confidence':.5,'evidence':['secret']},'plans':[],'probes':[]}):
        assert cognition.reflect(e,'a','similar1',api='stub',model='stub') is None  # optional step: skipped, not fatal
    assert e.state['runtime']['skipped_model_steps'].pop()['step']=='reflection'
    assert e.state==before
    checks+=['conditional reinterpretation preserves original event and prior meaning','unreceived narrative evidence rejected before mutation']
    # Controlled historical expansion cannot promote an account into a fact or meeting.
    background={'id':'v1','slots':{'education':['trade-school','college']},'milestones':[{
        'id':'education-a','day':-365.25,'description':'A completed trade school.','participants':['a'],
        'requires_facts':{'education':'trade-school'}}]}
    with patch('devsim.engine.request_json',side_effect=stub): life_policy.expand_background(e,'a',background,api='stub',model='stub')
    assert e.state['entities']['a']['facts']['education']=='trade-school'
    assert e.world.observations['a'][0]==original['a'][0]
    assert not e.agent('a')['relationships'] and not e.state['entities']['b'].get('background_versions')
    before=deepcopy(e.state)
    bad=deepcopy(background);bad.update(id='v2');bad['slots']['education']=['college']
    with patch('devsim.engine.request_json',side_effect=stub): reject(lambda:life_policy.expand_background(e,'a',bad,api='stub',model='stub'))
    assert e.state==before
    checks+=['need-driven canonical biography commits shared history without invented memories','later expansion cannot overwrite committed facts']
    # Exact saved autonomous event streams, shared resource accounting and habits.
    with TemporaryDirectory() as directory:
        path=Path(directory)/'world.json'; p=policy(); whole=world(); split=world()
        with patch('devsim.engine.request_json',side_effect=stub):
            Lifetime(whole,p).run(365.25,path)
            Lifetime(split,p).run(180,path); split=Engine.load(path); Lifetime(split,p).run(365.25,path)
        assert whole.state==split.state
        assert whole.agent('a')['habits'] and whole.agent('a')['time_use']
        assert whole.agent('a')['resources']['money']>=10
        assert any(t.get('kind')=='autonomous_recall' and t.get('memory') for t in whole.state['runtime']['trace'])
        assert whole.agent('a')['narrative_versions']
        assert Engine.load(path).state==split.state
        checks+=['autonomous recall is event-driven and checkpoint reproducible','competing-goal actions honor time and resource budgets','resolved actions build bounded habits','world consequences and all new state survive resume']
        # Same-day total duration excludes a second expensive action.
        q=policy();q.pop('cognition'); q['opportunities'][0]['rate_per_year']=10000
        limited=world()
        with patch('devsim.engine.request_json',side_effect=stub): Lifetime(limited,q).run(1)
        assert len(limited.state['actions'])==1
        checks.append('multiple same-day opportunities cannot exceed available hours')
        # Model failure after consequence computation rolls the entire event back.
        rollback=world(); c=Lifetime(rollback,p); initial=deepcopy(rollback.state)
        due=min(d for d in rollback.state['runtime']['next_opportunities'].values() if d is not None)
        def fail(system,context,api,model,max_tokens=600):
            if context.get('task')=='reflect_received_evidence': raise RuntimeError('fixture unavailable')
            return stub(system,context,api,model,max_tokens)
        with patch('devsim.engine.request_json',side_effect=fail): reject(lambda:c.run(due,path))
        # Background events before this opportunity may validly commit; only the
        # failed opportunity's activity/resource/memory changes must roll back.
        assert not rollback.state['actions'] and rollback.agent('a')['resources']=={'money':10}
        assert 'employment' not in rollback.state['entities']['a']['facts']
        checks.append('reflection failure rolls back action, world effect, budget and habit updates')
        # Shared transition, birth, illness and death use controller facts only.
        demographic=world()
        rules=[{'id':'partner','day':1,'description':'A and B become partners.',
            'observations':{'a':{'text':'B and I became partners.','source':'direct','encountered':['b']},
                            'b':{'text':'A and I became partners.','source':'direct','encountered':['a']}},
            'effects':{'relationships':[{'a':'a','b':'b','role':'partner'}]}},
            {'id':'birth','day':2,'description':'A child is born.','observations':{},
                'effects':{'births':[{'id':'child','name':'Child','biological_parents':['a','b'],'caregivers':['a','b']}]}},
            {'id':'illness','day':3,'description':'A has an illness.','observations':{'a':{'text':'I became ill.','source':'direct'}},
                'effects':{'facts':{'a':{'health_status':'ill'}}}},
            {'id':'death','day':4,'description':'B dies.','observations':{'a':{'text':'B died.','source':'direct'}},
                'effects':{'deaths':['b']}}]
        Lifetime(demographic,{'sampling':'event_driven','opportunities':[],'world_events':rules},scripted=True).run(5,path)
        assert demographic.agent('a')['relationships']['b']['role']=='partner'
        assert not demographic.agent('b')['alive'] and demographic.agent('child')['birth_day']==2
        assert demographic.state['entities']['child']['facts']['caregivers']==['a','b']
        assert not demographic.agent('child')['memory_meta']
        assert demographic.state['entities']['a']['facts']['health_status']=='ill'
        assert Engine.load(path).state==demographic.state
        checks+=['joint demographic transitions require actual shared observation','birth respects separate biological parents/caregivers without ancestry recursion','illness/death are explicit world transitions and checkpointed']
    # Deferred contradiction is queued; an explicit question is transmitted on
    # an actual selected contact, never converted into a world fact or meeting.
    probe_world=world(); cognition.configure(probe_world,{'reflection':True,'rumination_per_year':0})
    probe_world.schedule('account',1,'A hears an uncertain account.',{'a':{'text':'B says a surprising thing.',
        'source':'B','kind':'testimony','references':['b'],'meaning':'An uncertain claim.'}})
    probe_world.advance(1)
    def probe_stub(system,context,api,model,max_tokens=600):
        if context.get('task')=='reflect_received_evidence':
            out=reflection(context)
            out['revisions']=[{'memory_id':'episode','decision':'defer','reason':'Accounts do not yet resolve the interpretation.',
                'meaning':'I am unsure.','confidence':.4,'evidence':['episode','account']}]
            out['probes']=[{'target_id':'b','question':'Could you explain what happened?',
                'reason':'The account surprised me.','evidence':['account']}]
            return out
        return stub(system,context,api,model,max_tokens)
    with patch('devsim.engine.request_json',side_effect=probe_stub): cognition.reflect(probe_world,'a','account',api='stub',model='stub')
    assert probe_world.agent('a')['reinterpretation_queue'] and not probe_world.agent('a')['memory_meta']['episode']['versions']
    assert not probe_world.agent('a')['relationships'] and not probe_world.state['entities']['b']['facts'].get('surprising_claim')
    interaction={'sampling':'event_driven','opportunities':[{'id':'ask','actor':'a','rate_per_year':365,
        'situation':'B is available to talk.','options':[{'id':'ask','label':'Talk to B.','contact':'b',
        'success_probability':1,'success_text':'B and I talked.','failure_text':'We did not talk.',
        'contact_text':'A asked me a question.','valence_success':.1,'valence_failure':-.1,
        'contact_responses':[{'id':'answer','label':'Offer an account.','success_text':'B gave an uncertain account.',
            'failure_text':'B did not answer.','contact_text':'I offered an account to A.'}]}]}]}
    controller=Lifetime(probe_world,interaction)
    due=probe_world.state['runtime']['next_opportunities']['ask']
    captured=[]
    def capture(system,context,api,model,max_tokens=600):
        captured.append(deepcopy(context));return stub(system,context,api,model,max_tokens)
    with patch('devsim.engine.request_json',side_effect=capture): controller.run(due)
    assert any(c['identity']['id']=='b' and 'Could you explain what happened?' in c['situation'] for c in captured)
    assert probe_world.agent('a')['probe_queue'][0]['status']=='asked'
    checks+=['unresolved reinterpretation is deferred without overwriting meaning','curiosity sends a question only through a selected real interaction','asking does not validate testimony or fabricate acquaintance']
    # A single-parent household may be generated before the child's disposition,
    # without generating a second parent or recursive ancestry.
    family=world(); family.schedule('new-family',1,'A family is introduced.',{});family.advance(1)
    life_policy.apply_effects(family,{'births':[{'id':'new-child','name':'New child','biological_parents':['new-parent'],
        'caregivers':['new-parent'],'new_caregivers':[{'id':'new-parent','name':'New parent','age_years':28}]}]},'new-family')
    assert family.agent('new-child')['birth_day']==1
    assert family.state['entities']['new-child']['facts']['biological_parents']==['new-parent']
    assert not family.agent('new-parent')['memory_meta']
    checks.append('necessary single-parent context precedes child generation with no fabricated ancestry')
    # Newborn opportunities join the same event scheduler and resume without
    # duplicating identities, actions or generation-specific random streams.
    generation={'sampling':'event_driven','opportunities':[],'world_events':[{'id':'birth','day':1,
        'description':'A child is born.','observations':{},'effects':{'births':[{'id':'next-child','name':'Next child',
        'biological_parents':['a'],'caregivers':['a']}]}}],
        'newborn_opportunities':[{'id':'ask-caregiver','actor':'$actor','min_age':0,'max_age':2,'rate_per_year':365,
        'situation':'You need help with a small task.','options':[{'id':'ask','label':'Ask for help.',
        'contact':'$caregiver','contact_text':'I helped the child.','success_probability':1,
        'success_text':'My caregiver helped me.','failure_text':'I was still stuck.',
        'valence_success':.3,'valence_failure':-.2}]}]}
    with TemporaryDirectory() as directory:
        path=Path(directory)/'world.json';whole=world();split=world()
        Lifetime(whole,generation,scripted=True).run(10)
        Lifetime(split,generation,scripted=True).run(3,path);split=Engine.load(path)
        Lifetime(split,generation,scripted=True).run(10)
        assert whole.state==split.state
        assert any(a['owner']=='next-child' for a in whole.state['actions'])
        assert len(whole.state['runtime']['dynamic_opportunities'])==1
        broken=deepcopy(generation);broken['newborn_opportunities'].append({**deepcopy(generation['newborn_opportunities'][0]),
            'id':'broken','rate_per_year':-1})
        rollback=world();controller=Lifetime(rollback,broken,scripted=True);before=deepcopy(rollback.state)
        reject(lambda:controller.run(2,path))
        assert rollback.state==before and 'next-child' not in rollback.state['agents']
        assert not controller.policy['opportunities']
    checks+=['newborns acquire declared age-eligible opportunities automatically','multi-generation scheduler resumes identically without duplicate registration',
        'malformed new-generation policy rolls back birth and dynamic scheduling']
    social=world();cognition.configure(social,{'reflection':True,'rumination_per_year':0})
    social.schedule('meeting',1,'A and B meet.',{'a':{'text':'B listened to my concern.','source':'direct','encountered':['b']}});social.advance(1)
    def social_stub(system,context,api,model,max_tokens=600):
        out=reflection(context)
        out['relationship_updates']=[{'target_id':'b','trust_delta':.03,'closeness_delta':.02,
            'reason':'B listened during this encounter.','evidence':['meeting']}]
        return out
    with patch('devsim.engine.request_json',side_effect=social_stub): cognition.reflect(social,'a','meeting',api='stub',model='stub')
    assert social.agent('a')['relationships']['b']['trust']==.53
    assert social.agent('a')['relationships']['b']['closeness']==.02
    social.schedule('meeting2',2,'A and B meet again.',{'a':{'text':'I saw B.','source':'direct','encountered':['b']}});social.advance(2)
    assert social.agent('a')['relationships']['b']['versions']
    checks.append('trust and closeness update separately from direct evidence with retained provenance')
    # New evidence is never offered as its own reconsolidation target.
    checks.append('reflection separates new evidence from eligible earlier revision targets')
    # Exact-time world death takes precedence over a simultaneous choice.
    coincident=world();base_policy=policy();base_policy.pop('cognition');
    tmp=Lifetime(coincident,base_policy,scripted=True)
    first=coincident.state['runtime']['next_opportunities']['work']
    coincident=world();base_policy['world_events']=[{'id':'death','day':first,'description':'A dies.',
        'observations':{},'effects':{'deaths':['a']}}]
    Lifetime(coincident,base_policy,scripted=True).run(first)
    assert not coincident.agent('a')['alive'] and not coincident.state['actions']
    checks.append('simultaneous death precedes action eligibility')
    # A daily absolute budget prevents rapid repeated interactions saturating
    # trust merely because there were many events in one simulated instant.
    for mid in ('social1','social2','social3'):
        social.schedule(mid,social.day,'A and B talk.',{'a':{'text':'B listened.','source':'direct','encountered':['b']}});social.advance(social.day)
        def bounded_social(system,context,api,model,max_tokens=600):
            out=reflection(context);out['relationship_updates']=[{'target_id':'b','trust_delta':.05,'closeness_delta':.05,
                'reason':'A received conversation.','evidence':[context['new_evidence']['event']]}];return out
        with patch('devsim.engine.request_json',side_effect=bounded_social): cognition.reflect(social,'a',mid,api='stub',model='stub')
    assert abs(social.agent('a')['relationships']['b']['trust']-.58)<1e-9
    checks.append('same-day trust/closeness changes share an absolute budget')
    checks+=memory_physics()
    result={'passed':True,'scope':'synthetic integration checks; model responses stubbed, coefficients and world rules are provisional','checks':checks}
    RESULTS_DIR.joinpath('extended-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
