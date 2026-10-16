"""Cognition, constrained expansion and world/planning integration regressions."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from engine import Engine,FACET_NAMES
from lifetime import Lifetime
import cognition
import life_policy


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


def main():
    checks=[]
    e=world(); cognition.configure(e,{'reflection':True,'rumination_per_year':8})
    original=deepcopy(e.world.observations)
    with patch('engine.request_json',side_effect=stub): cognition.reflect(e,'a','episode',api='stub',model='stub')
    assert e.agent('a')['narrative_identity']['evidence']==['episode']
    assert e.agent('a')['goals']['work']['plan']==['Try a different approach.']
    e.advance(1000)
    view=e.memories('a','work evaluation')[0]
    assert view['representation']=='subjective_gist' and '918' not in json.dumps(view)
    stability=e.agent('a')['memory_meta']['episode']['stability_days']
    with patch('engine.request_json',side_effect=stub): cognition.semantic_recall(e,'a','An unfavorable assessment',api='stub',model='stub')
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
    # Received new evidence may revise meaning but not original episodes.
    with patch('engine.request_json',side_effect=stub): cognition.reflect(e,'a','similar0',api='stub',model='stub')
    assert e.agent('a')['memory_meta']['episode']['versions']
    assert e.world.observations['a'][0]==original['a'][0]
    before=deepcopy(e.state)
    with patch('engine.request_json',return_value={'summary':'Bad','topics':[],'revisions':[],
            'narrative':{'text':'Bad','confidence':.5,'evidence':['secret']},'plans':[],'probes':[]}):
        reject(lambda:cognition.reflect(e,'a','similar1',api='stub',model='stub'))
    assert e.state==before
    checks+=['conditional reinterpretation preserves original event and prior meaning','unreceived narrative evidence rejected before mutation']
    # Controlled historical expansion cannot promote an account into a fact or meeting.
    background={'id':'v1','slots':{'education':['trade-school','college']},'milestones':[{
        'id':'education-a','day':-365.25,'description':'A completed trade school.','participants':['a'],
        'requires_facts':{'education':'trade-school'}}]}
    with patch('engine.request_json',side_effect=stub): life_policy.expand_background(e,'a',background,api='stub',model='stub')
    assert e.state['entities']['a']['facts']['education']=='trade-school'
    assert e.world.observations['a'][0]==original['a'][0]
    assert not e.agent('a')['relationships'] and not e.state['entities']['b'].get('background_versions')
    before=deepcopy(e.state)
    bad=deepcopy(background);bad.update(id='v2');bad['slots']['education']=['college']
    with patch('engine.request_json',side_effect=stub): reject(lambda:life_policy.expand_background(e,'a',bad,api='stub',model='stub'))
    assert e.state==before
    checks+=['need-driven canonical biography commits shared history without invented memories','later expansion cannot overwrite committed facts']
    # Exact saved autonomous event streams, shared resource accounting and habits.
    with TemporaryDirectory() as directory:
        path=Path(directory)/'world.json'; p=policy(); whole=world(); split=world()
        with patch('engine.request_json',side_effect=stub):
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
        with patch('engine.request_json',side_effect=stub): Lifetime(limited,q).run(1)
        assert len(limited.state['actions'])==1
        checks.append('multiple same-day opportunities cannot exceed available hours')
        # Model failure after consequence computation rolls the entire event back.
        rollback=world(); c=Lifetime(rollback,p); initial=deepcopy(rollback.state)
        due=min(d for d in rollback.state['runtime']['next_opportunities'].values() if d is not None)
        def fail(system,context,api,model,max_tokens=600):
            if context.get('task')=='reflect_received_evidence': raise RuntimeError('fixture unavailable')
            return stub(system,context,api,model,max_tokens)
        with patch('engine.request_json',side_effect=fail): reject(lambda:c.run(due,path))
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
    with patch('engine.request_json',side_effect=probe_stub): cognition.reflect(probe_world,'a','account',api='stub',model='stub')
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
    with patch('engine.request_json',side_effect=capture): controller.run(due)
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
    with patch('engine.request_json',side_effect=social_stub): cognition.reflect(social,'a','meeting',api='stub',model='stub')
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
        with patch('engine.request_json',side_effect=bounded_social): cognition.reflect(social,'a',mid,api='stub',model='stub')
    assert abs(social.agent('a')['relationships']['b']['trust']-.58)<1e-9
    checks.append('same-day trust/closeness changes share an absolute budget')
    result={'passed':True,'scope':'synthetic integration checks; model responses stubbed, coefficients and world rules are provisional','checks':checks}
    Path(__file__).with_name('extended-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
