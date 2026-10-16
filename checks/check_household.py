"""Routing, time, independent turns and recovery checks; synthetic model stubs."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devsim.engine import Engine,FACET_NAMES
from devsim.lifetime import Lifetime
from devsim import household, calendar_time

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
def fixture(turns=2):
    e=Engine(seed=84)
    for p in 'abcde':
        e.entity(p,p.upper(),{'birth_day':-25*365.25})
        e.materialize(p,dict.fromkeys(FACET_NAMES,50),birth_day=-25*365.25)
        e.schedule('private-'+p,0,'A private thought.',{p:{'text':'PRIVATE_'+p,'source':'self','kind':'internal'}})
        e.advance(0)
    policy={'sampling':'event_driven','opportunities':[],
        'planning':{'calendar_mode':'elapsed','hours_per_day':8},
        'expression':{'age_appropriate_actions':True},
        'household':{'rooms':{'kitchen':{'label':'the kitchen','audible_to':['hall']},
            'hall':{'label':'the open hallway'},'closed':{'label':'a closed bedroom'}},
            'locations':{'a':'kitchen','b':'kitchen','c':'kitchen','d':'hall','e':'closed'},
            'routines':{p:{'available_hours':[[7,22]],'response_minutes':[2,2]} for p in 'abcde'},
            'conversations':[{'id':'family','day':.75,'room':'kitchen','participants':['a','b'],
                'topic':'Discuss how the afternoon went.','max_turns':turns,'exit_room':'closed'}]}}
    return e,policy


def reject(call):
    try: call()
    except (ValueError,RuntimeError): return
    raise AssertionError('Invalid operation accepted')


def stub(system,context,api,model,max_tokens=600):
    owner=context['identity']['id']
    serialized=json.dumps(context)
    assert all('PRIVATE_'+p not in serialized for p in 'abcde' if p!=owner)
    if 'new_observation' in context:
        return {'meaning':context['new_observation']['text'],'valence':-.2,'arousal':.3,'importance':.8,'confidence':.6}
    if owner=='b':
        assert 'I think E sold the bicycle.' in serialized
    return {'action_id':'speak','action':'Say what I think.','speech':'I think E sold the bicycle.' if owner=='a' else 'How do you know that?',
        'goal_id':None,'plan':[],'memory_ids':[]}


def main():
    checks=[]
    with TemporaryDirectory() as directory:
        root=Path(directory)
        e,p=fixture();c=Lifetime(e,p)
        with patch('devsim.engine.request_json',side_effect=stub): c.run(.8,root/'world.json')
        s=e.state['runtime']['conversations']['family'];turns=s['turns']
        assert [t['speaker'] for t in turns]==['a','b'] and s['status']=='closed'
        assert all(a['status']=='resolved' for a in e.state['actions'])
        assert turns[1]['day']>turns[0]['day']>.75
        assert all(abs(sum(e.agent(x)['time_use'].values())-4/60)<1e-8 for x in 'ab')
        checks+=['multiple independent private-context replies use previously received speech','elapsed response intervals resolve intended turns and account both participants']
        assert all(t['event'] in e.agent('c')['memory_meta'] for t in turns)
        assert all(t['event'] in e.agent('d')['memory_meta'] for t in turns)
        assert all(t['event'] not in e.agent('e')['memory_meta'] for t in turns)
        assert e.agent('c')['relationships']['a']['firsthand']
        assert 'a' not in e.agent('d')['relationships']
        assert all(not event['facts'] for event in e.state['events'])
        assert e.state['entities']['e']['facts']=={'birth_day':-25*365.25}
        assert e.mood('c')['valence']<0 and e.mood('e')['valence']==0
        checks+=['same-room bystanders overhear and acquire received affect','explicit adjoining-room audibility does not establish firsthand acquaintance',
            'closed-room person receives no conversation memory or mood update','spoken allegations never become canonical facts']
        view=e.context('a','Next?')['physical_environment']
        assert {x['id'] for x in view['visible_people']}=={'b','c'} and 'PRIVATE_b' not in json.dumps(e.context('a','Next?'))
        checks+=['agent environment context reveals only same-room presence, never private profiles or remote locations']
        e.save(root/'world.sqlite')
        assert Engine.load(root/'world.json').state==e.state==Engine.load(root/'world.sqlite').state
        checks+=['JSON and SQLite restore locations, received turns, calendar and conversation state']
        split,policy=fixture();Lifetime(split,policy,scripted=True).run(.75+1/1440,root/'split.json')
        restored=Engine.load(root/'split.json');assert not restored.state['actions']
        Lifetime(restored,policy,scripted=True).run(.8)
        whole,_=fixture();Lifetime(whole,policy,scripted=True).run(.8)
        assert restored.state==whole.state
        checks+=['mid-response checkpoint resumes identically without replaying completed events or time accounting']
        broken,policy=fixture();control=Lifetime(broken,policy)
        with patch('devsim.engine.request_json',side_effect=stub): control.run(.751,root/'broken.json')
        before=deepcopy(broken.state)
        def fail(system,context,api,model,max_tokens=600):
            if context.get('identity',{}).get('id')=='c' and 'new_observation' in context: raise RuntimeError('listener provider failed')
            return stub(system,context,api,model,max_tokens)
        with patch('devsim.engine.request_json',side_effect=fail): reject(lambda:control.run(.8,root/'broken.json'))
        assert broken.state==before==Engine.load(root/'broken.json').state
        with patch('devsim.engine.request_json',side_effect=stub): Lifetime(broken,policy).run(.8)
        assert len(broken.state['actions'])==2
        checks+=['failed bystander appraisal rolls back turn, action, calendars and all recipients; retry commits once']
        asleep,policy=fixture();policy['household']['routines']['b']['available_hours']=[[7,17]]
        Lifetime(asleep,policy,scripted=True).run(.8)
        assert not asleep.state['actions']
        checks+=['unavailable invited participant cannot be forced into a conversation']
        bounded,policy=fixture();policy['household']['routines']['a']['available_hours']=[[18,18.01]]
        Lifetime(bounded,policy,scripted=True).run(.8)
        assert not bounded.state['actions']
        checks+=['response interval cannot cross the end of a waking window']
        busy,policy=fixture();control=Lifetime(busy,policy,scripted=True);busy.advance(.75)
        calendar_time.reserve(busy,'a',1,'other-work')
        busy.state['runtime']['current_day']=busy.day;control.run(.8)
        assert not busy.state['actions']
        checks+=['calendar commitments prevent double-booked conversation participation']
        moved,policy=fixture();policy['household']['moves']=[{'id':'b-leaves','day':.751,'actor':'b','room':'closed'}]
        Lifetime(moved,policy,scripted=True).run(.8)
        assert not moved.state['actions'] and household.location(moved,'b')=='closed'
        assert moved.state['runtime']['conversations']['family']['status']=='closed'
        checks+=['movement during a response cancels speech before it is delivered']
        dead,policy=fixture();policy['world_events']=[{'id':'death','day':.751,'description':'A death.',
            'effects':{'deaths':['b']}}]
        Lifetime(dead,policy,scripted=True).run(.8)
        assert not dead.agent('b')['alive'] and not dead.state['actions']
        checks+=['death during a response prevents posthumous speech']
        leave,policy=fixture(4)
        def leaving(system,context,api,model,max_tokens=600):
            if 'new_observation' in context: return stub(system,context,api,model,max_tokens)
            return {'action_id':'leave-room','action':'Leave the room.','speech':'','goal_id':None,'plan':[],'memory_ids':[]}
        with patch('devsim.engine.request_json',side_effect=leaving): Lifetime(leave,policy).run(.8)
        assert household.location(leave,'a')=='closed' and len(leave.state['actions'])==1
        checks+=['independently chosen departure changes physical routing and ends an undersized conversation']
        infant,policy=fixture();infant.agent('a')['birth_day']=0;infant.state['entities']['a']['facts']['birth_day']=0
        Lifetime(infant,policy,scripted=True).run(.8)
        a=infant.state['actions'][0]['decision']
        assert a['action_id']=='signal' and a['speech']=='' and a['plan']==[]
        checks+=['infant conversation participation is nonverbal with no adult plan']
        invalid,policy=fixture();before=deepcopy(invalid.state)
        policy['household']['rooms']['kitchen']['audible_to']=['nonexistent']
        reject(lambda:Lifetime(invalid,policy));assert invalid.state==before
        checks+=['invalid physical policy is rejected before runtime mutation']
        old,_=fixture();legacy={'sampling':'event_driven','opportunities':[]}
        Lifetime(old,legacy,scripted=True).run(1)
        assert 'household' not in old.state and 'physical_environment' not in old.context('a','Next?')
        checks+=['archived policies remain free of implicit rooms or invented conversations']
        routine,policy=fixture();Lifetime(routine,policy,scripted=True);routine.advance(.9)
        assert not calendar_time.can_reserve(routine,'a',1)
        checks+=['daily availability also gates ordinary elapsed activity reservations']
        badspeech,policy=fixture();Lifetime(badspeech,policy,scripted=True)
        context=badspeech.context('a','Listen',options=[{'id':'listen','label':'Listen','speech_allowed':False}])
        reject(lambda:badspeech.validate_decision('a',{'action':'Listen','action_id':'listen','speech':'contradiction',
            'goal_id':None,'plan':[],'memory_ids':[]},context))
        checks+=['silent action contracts reject contradictory model speech']
        growth,policy=fixture();policy['development']={'crystallization':{'minimum_days':2}}
        Lifetime(growth,policy,scripted=True).run(.8)
        assert all(len(growth.agent(p)['developmental_exposures'])==1 for p in 'ab')
        assert not growth.agent('c').get('developmental_exposures')
        checks+=['resolved dialogue actions feed existing developmental exposure gates; overhearing alone does not count as enacted behavior']
        contact,policy=fixture();policy['household']['conversations']=[]
        policy['household']['locations']['b']='closed'
        option={'id':'talk','label':'Ask B to discuss a task.','contact':'b','room_contact':True,'duration_hours':1,
            'success_probability':1,'success_text':'We discussed the task.','failure_text':'The task was not discussed.',
            'contact_text':'I discussed the task.','valence_success':.2,'valence_failure':-.2}
        rule={'id':'local-contact','actor':'a','rate_per_year':0,'situation':'Consider a local discussion.','options':[option]}
        policy['opportunities']=[rule]
        control=Lifetime(contact,policy,scripted=True);control.run(.75)
        control.process(rule,0,occurrence=True)
        assert not contact.state['actions']
        checks+=['explicit room contact cannot begin with a remotely located person']
        contact.state['household']['locations']['b']='kitchen'
        control.process(rule,1,occurrence=True)
        assert len(contact.state['runtime']['pending_activities'])==1
        contact.state['household']['locations']['b']='closed'
        control.run(.8)
        assert contact.state['actions'][0]['status']=='cancelled'
        assert not contact.state['runtime']['pending_activities']
        checks+=['physical contact activity cannot resolve after a participant leaves its room']
    result={'passed':True,'scope':'synthetic household engineering checks, not psychological validation','checks':checks}
    RESULTS_DIR.joinpath('household-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
