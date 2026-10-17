"""Routing, time, independent turns and recovery checks; synthetic model stubs."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import re
from devsim.engine import Engine,FACET_NAMES
from devsim.lifetime import Lifetime
from devsim import household, calendar_time, situation

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
        memory,policy=fixture(turns=3)
        policy['household']['conversations'].append(dict(policy['household']['conversations'][0],id='family-2',day=1.75))
        seen={};irritation=[]
        def recording(system,context,api,model,max_tokens=600):
            if 'new_observation' in context and context.get('earlier_questions_from_speaker'):
                return {**stub(system,context,api,model,max_tokens),'asked_before':context['earlier_questions_from_speaker'][-1]['id']}
            if 'new_observation' not in context and context['identity']['id']=='b':
                irritation.append(context.get('repeated_question'))
            if 'new_observation' not in context:
                seen.setdefault(context['identity']['id'],[]).append((context.get('conversation_so_far'),context.get('repeat_notice')))
                return {'action_id':'listen' if context['identity']['id']=='b' else 'speak','action':'Take my turn.',
                    'speech':'' if context['identity']['id']=='b' else 'Did you finish the report?','goal_id':None,'plan':[],'memory_ids':[]}
            return stub(system,context,api,model,max_tokens)
        with patch('devsim.engine.request_json',side_effect=recording): Lifetime(memory,policy).run(1.8)
        # a's calls per session: first turn, third turn and its repeat re-ask; the next session's first turn is a repeat too.
        recent=[x for x,_ in seen['a']];notices=[n for _,n in seen['a']]
        assert [n is not None for n in notices]==[False,False,True,False,True,False,True]
        assert [x['text'] for x in recent[1]['this_conversation']][-2:]==['I said: Did you finish the report?','B listened quietly.']
        assert 'previous_session' not in recent[1] and recent[3]['previous_session']['last_turns'][-1]=='I said: Did you finish the report?'
        assert 'B listened quietly.' in recent[3]['previous_session']['last_turns']
        assert memory.context('c','Next?').get('conversation_so_far') is None and 'PRIVATE_b' not in json.dumps(seen)
        checks+=['speakers always see their own received turns of the current conversation and the end of the previous same-topic session, regardless of retrieval rank; bystanders and non-participants get none']
        assert notices[2]['your_earlier_words']=='Did you finish the report?'
        assert sum(a['decision']['speech']=='Did you finish the report?' for a in memory.state['actions'])==4
        assert memory.repeated_speech('a','Yes.') is None and memory.repeated_speech('a','Something entirely different to talk about') is None
        # Lines over 200 characters: character-level difflib autojunk scored this near-copy 0.06 in the v2 run.
        old='You keep talking about the dance like it matters, but my system forces a safety state on corrupted data, which is the only thing keeping the whole performance from crashing in front of the judges. If you want to talk about the stage, fine, but do not pretend that is what the judges will care about.'
        memory.state['actions'].append({'id':'long-line','owner':'a','day':memory.day,'status':'resolved','decision':{'speech':old}})
        assert memory.repeated_speech('a',old.replace('dance','stage').replace('whole ',''))['id']=='long-line'
        assert memory.repeated_speech('a','I would rather hear how your week went, and whether the lab felt calmer today than it did on Monday when everyone was arguing about the deadline.') is None
        memory.state['actions'].pop()
        checks+=['a near-repeat of the speaker\'s own recent words is re-asked once with the earlier words shown; a second repeat is kept, never fatal; short replies are exempt']
        assert irritation[0] is None and irritation[1]['times_asked_before']==2 and irritation[1]['from']=='A'
        assert abs(irritation[1]['first_asked_days_ago']-1)<.01
        assert max(m.get('times_asked_before',0) for m in memory.agent('b')['memory_meta'].values())==3
        assert not any('repeat_of' in m for m in memory.agent('a')['memory_meta'].values())  # "B listened quietly." asks nothing
        bad,policy=fixture(turns=3)
        def invented(system,context,api,model,max_tokens=600):
            if 'new_observation' in context and context.get('earlier_questions_from_speaker'):
                return {**stub(system,context,api,model,max_tokens),'asked_before':'never-received'}
            return recording(system,context,api,model,max_tokens)
        with patch('devsim.engine.request_json',side_effect=invented): reject(lambda: Lifetime(bad,policy).run(.8))
        reject(lambda: memory.schedule('forged',memory.day,'A forged repeat.',{'b':{'text':'A said: Again?','source':'a','repeat_of':'never-received'}}))
        # The reaction to repetition is personal: it comes from the listener's own signatures via construal.
        caps,policy=fixture(turns=3)
        policy['household']['conversations'].append(dict(policy['household']['conversations'][0],id='family-2',day=1.75))
        policy['situational_personality']={'recovery_half_life_days':1}
        prompts,construed,decided=[],[],[]
        def personal(system,context,api,model,max_tokens=600):
            task=context.get('task')
            if task=='generate_situational_signatures':
                prompts.append(system)
                return {'rules':[{'id':'repeat','dimension':'Negativity','trigger_context':'Asked the same thing again.',
                    'narrative_shift':'Answers curtly or walks away.','state_modifiers':{'A':-6,'N':4}}]+
                    [{'id':f'r{i}','dimension':'Duty','trigger_context':f'Rule {i}.','narrative_shift':'Works steadily.','state_modifiers':{'C':1}} for i in range(4)]}
            if task=='construe_situation':
                if context['identity']['id']=='b': construed.append(context.get('repeated_question'))
                return {'meaning':'A moment.','dimensions':{d:(.8 if d=='Negativity' else .1) for d in situation.DIMENSIONS},'controllability':.5,
                    'active_rule_ids':['repeat'] if context.get('repeated_question') else []}
            if 'new_observation' not in context and context['identity']['id']=='b':
                decided.append([r['id'] for r in context['active_situation_rules']])
            return recording(system,context,api,model,max_tokens)
        with patch('devsim.engine.request_json',side_effect=personal): Lifetime(caps,policy).run(1.8)
        assert prompts and all('same thing keeps happening' in p for p in prompts)
        assert construed[0] is None and construed[-1]['times_asked_before']>=2
        assert decided[0]==[] and decided[-1]==['repeat'] and caps.agent('b')['situational_state']['offsets']['A1']<0
        checks+=['repetition reaches the listener\'s situation construal; their own model-written repetition signature (one is required) then shapes the decision and temporary state']
        checks+=['a listener\'s appraisal links a question to the same person\'s earlier one; the running count reaches later decisions as irritation for anyone; links to unreceived memories are rejected']
        # Routine habituation: an identical routine observation reuses the person's own recent full appraisal.
        hab,_=fixture();trip={'text':'I set off for the hospital ward.','source':'direct','kind':'direct'}
        hab.schedule('trip-0',hab.day,'A journey.',{'a':{**trip,'meaning':'Off to work again.','valence':-.4,'arousal':.6,'importance':.8,'confidence':.7}})
        hab.advance(hab.day)
        def no_model(*args,**kwargs): raise AssertionError('routine reuse must not call the model')
        for i in (1,2):
            with patch('devsim.engine.request_json',side_effect=no_model): seen_trip=hab.appraise('a',trip,routine=True)
            assert seen_trip['reused_appraisal']=='trip-0' and seen_trip['exposures']==i and seen_trip['meaning']=='Off to work again.'
            assert abs(seen_trip['valence']+.4/(1+i))<1e-9 and abs(seen_trip['importance']-.8/(1+i))<1e-9
            hab.schedule(f'trip-{i}',hab.day,'A journey.',{'a':seen_trip});hab.advance(hab.day)
        assert hab.agent('a')['memory_meta']['trip-2']['exposures']==2
        fresh=lambda *a,**k:{'meaning':'A new look at the trip.','valence':-.1,'arousal':.2,'importance':.5,'confidence':.6}
        with patch('devsim.engine.request_json',side_effect=fresh):
            assert 'reused_appraisal' not in hab.appraise('a',trip)  # not marked routine
            assert 'reused_appraisal' not in hab.appraise('a',{**trip,'text':'I set off for the school lab.'},routine=True)
            hab.advance(hab.day+31); assert 'reused_appraisal' not in hab.appraise('a',trip,routine=True)
        reject(lambda: hab.schedule('forged-trip',hab.day,'A journey.',{'a':{**trip,'reused_appraisal':'never-received','exposures':1}}))
        checks+=['identical routine observations reuse the person\'s own recent full appraisal without a model call, habituating as 1/(1+n); new, non-routine or stale (30-day) ones get a full appraisal']
        # A situation with room and hours happens only there and then; occurrences outside are postponed, not lost.
        timed,policy=fixture();policy['household']['conversations']=[]
        opt=lambda i:{'id':f'o{i}','label':f'Option {i}.','success_probability':1,'success_text':'Done.','failure_text':'Not done.',
            'valence_success':.1,'valence_failure':-.1}
        policy['opportunities']=[{'id':'lunch','actor':'a','situation':'Lunch.','rate_per_year':200,'room':'kitchen','hours':[12,13],'options':[opt(0),opt(1)]},
            {'id':'away','actor':'a','situation':'Elsewhere.','rate_per_year':200,'room':'closed','options':[opt(0),opt(1)]}]
        Lifetime(timed,policy,scripted=True).run(20)
        lunches=[x for x in timed.state['actions'] if '-lunch' in x['id']]
        assert len(lunches)>=5 and all(12<=(x['day']%1)*24<13 for x in lunches)
        assert not any('-away' in x['id'] for x in timed.state['actions'])
        statuses={(t.get('opportunity'),t.get('status')) for t in timed.state['runtime']['trace']}
        assert ('lunch','postponed_to_window') in statuses and ('away','skipped_outside_window') in statuses
        reject(lambda: Lifetime(fixture()[0],{**policy,'opportunities':[{**policy['opportunities'][0],'room':'mars'}]},scripted=True))
        checks+=['a situation with room and hours occurs only while the actor is there within the hours; out-of-window occurrences are postponed, and skipped after 14 tries at an unreachable place']
        quick,policy=fixture()
        for p in 'ab': policy['household']['routines'][p]['in_person_response_minutes']=[.5,.5]
        Lifetime(quick,policy,scripted=True).run(.8)
        spoken=quick.state['runtime']['conversations']['family']['turns']
        assert abs((spoken[1]['day']-spoken[0]['day'])*1440-.5)<1e-6
        checks+=['face-to-face turns use in_person_response_minutes; response_minutes stays the written-channel delay']
        # A watching researcher joins a conversation through the run's inbox (devsim.visit / watcher key t).
        from devsim import visit
        from devsim.watch import load as watch_load
        guest,policy=fixture(turns=4);room=root/'visit';room.mkdir()
        control=Lifetime(guest,policy,scripted=True);control.inbox=room/'inbox.jsonl'
        visit.say(room,'Please talk about the bicycle.',to='b',name='Kanishk')
        control.run(.7)
        assert not guest.state['runtime'].get('visitor_log')  # no conversation yet: the line waits
        control.run(.8,room/'world.json')
        log=guest.state['runtime']['visitor_log']
        assert len(log)==1 and log[0]['conversation']=='family' and set(log[0]['hearers'])=={'a','b','c','d'}  # d: audible hallway
        assert guest.state['entities']['visitor-kanishk']['name']=='Kanishk'
        session=guest.state['runtime']['conversations']['family']
        assert len(session['turns'])==4 and session['spec']['day']<=log[0]['day']<session['turns'][-1]['day']  # no turn used
        heard=[o.text for o in guest.world.observations['b'] if o.event_id.startswith('@conversation:family:')]
        assert 'Kanishk said to B: Please talk about the bicycle.' in heard and heard.index('Kanishk said to B: Please talk about the bicycle.')<len(heard)-1
        assert not any('bicycle' in o.text for o in guest.world.observations['e'])  # closed room hears nothing
        visit.say(room,'Anyone there?',to='nobody',name='Kanishk')
        control.run(.85,room/'world.json')
        assert len(guest.state['runtime']['visitor_log'])==1  # stays queued: no matching conversation, never redelivered
        shown=watch_load(room)
        assert shown['waiting_to_say']==1 and any(f['name']=='Kanishk (you)' for f in shown['feed'])
        reject(lambda: visit.say(room,'x'*700))
        checks+=['a researcher line from the inbox waits for an active conversation, is heard by participants and room listeners (not closed rooms), '
                 'uses no turn, is delivered once, persists its offset, and appears in the watcher feed']
        view=e.context('a','Next?')['physical_environment']
        assert {x['id'] for x in view['visible_people']}=={'b','c'} and 'PRIVATE_b' not in json.dumps(e.context('a','Next?'))
        checks+=['agent environment context reveals only same-room presence, never private profiles or remote locations']
        # Two people named Priya: unique @handles keep them apart wherever they are perceived.
        from devsim import references
        twins,policy=fixture(turns=2)
        for p in ('a','b'):
            twins.state['entities'][p]['name']='Priya'; twins.state['entities'][p]['facts']['handle']=twins._new_handle(p,'Priya')
        ha,hb=(twins.state['entities'][p]['facts']['handle'] for p in 'ab')
        assert ha!=hb and all(re.fullmatch(r'priya\d{4}',h) for h in (ha,hb))
        Lifetime(twins,policy,scripted=True).run(.8)
        heard=[o.text for o in twins.world.observations['c'] if o.event_id.startswith('@conversation:family:') and 'said' in o.text]
        assert any(t.startswith(f'Priya (@{ha}) said:') for t in heard) and any(t.startswith(f'Priya (@{hb}) said:') for t in heard)
        assert twins.context('a','Next?')['identity']['handle']=='@'+ha
        said=lambda text: references.normalize(twins,'c',{'text':text,'source':'d','encountered':['a','b']},[{'span':text.split()[0]}])[0]
        assert said('Priya is late.')['resolved_id'] is None and sorted(said('Priya is late.')['candidate_ids'])==['a','b']
        assert said(f'@{hb} is late.')['resolved_id']=='b'
        assert twins.label('c')=='C' and fixture()[0].label('a')=='A'  # no handle: plain name, as before
        reject(lambda: twins.entity('clone','Priya',{'handle':ha}))
        auto=Engine(seed=5); auto.state['config']['identity_handles']=True
        auto.entity('p1','Priya'); auto.entity('p2','Priya')
        assert auto.state['entities']['p1']['facts']['handle']!=auto.state['entities']['p2']['facts']['handle']
        wanted=auto._new_handle('p3','Priya'); auto.entity('x','Priya',{'handle':wanted}); auto.entity('p3','Priya')
        assert auto.state['entities']['p3']['facts']['handle']!=wanted  # a taken handle moves to the next free number
        guests,policy=fixture(turns=4);door=root/'visit-twins';door.mkdir()
        for p in ('a','b'):
            guests.state['entities'][p]['name']='Priya'; guests.state['entities'][p]['facts']['handle']=twins.state['entities'][p]['facts']['handle']
        control=Lifetime(guests,policy,scripted=True);control.inbox=door/'inbox.jsonl'
        visit.say(door,'Hi.',to='@'+hb,name='Kanishk'); visit.say(door,'Hello.',to='Priya',name='Kanishk')
        control.run(.8,door/'world.json')
        lines=[o.text for o in guests.world.observations['c'] if o.source=='visitor-kanishk']
        assert lines==[f'Kanishk said to Priya (@{hb}): Hi.','Kanishk said: Hello.']  # a shared bare name addresses nobody
        # A phone call: the person decides to answer, steps out of the conversation, talks, hangs up and comes back.
        replies=[]
        def phone_stub(answer):
            def respond(system,context,api,model,max_tokens=600):
                situation=context.get('situation','')
                if 'new_observation' not in context and situation.startswith('Your phone rings'):
                    return {'action_id':'answer' if answer else 'ignore','action':'Respond.','speech':'Hello? Who is this?' if answer else '',
                            'goal_id':None,'plan':[],'memory_ids':[]}
                if 'new_observation' not in context and situation.startswith('You are on a phone call'):
                    replies.append(situation)
                    return {'action_id':'speak' if len(replies)==1 else 'hang_up','action':'Reply.',
                            'speech':'Oh, hi.' if len(replies)==1 else 'I have to go.','goal_id':None,'plan':[],'memory_ids':[]}
                return stub(system,context,api,model,max_tokens)
            return respond
        def ring(answer=True,lines=('Hi, it is Kanishk.','How was school?'),until=.752,wait=300):
            world,policy=fixture(turns=6);phone=root/f'phone-{len(list(root.glob("phone-*")))}';phone.mkdir()
            control=Lifetime(world,policy);control.inbox=phone/'inbox.jsonl';control.call_wait_seconds=wait
            with patch('devsim.engine.request_json',side_effect=phone_stub(answer)):
                control.run(until)
                visit.call(phone,'a','Kanishk')
                for line in lines: visit.call_say(phone,line)
                control.run(until+.001,phone/'world.json')
            return world,[(r['event'],r.get('text') or r.get('reason')) for r in visit.call_log(phone)]
        talked,log=ring()
        assert log==[('ringing',None),('answered','Hello? Who is this?'),('said','Oh, hi.'),('said','I have to go.'),('ended','A hung up')]
        mine=[o.text for o in talked.world.observations['a'] if o.event_id.startswith('@call:')]
        assert mine[0]=='I answered a phone call from an unknown number. I said: Hello? Who is this?'
        assert 'an unknown number (on the phone): Hi, it is Kanishk.' in mine and 'I said on the phone: Oh, hi.' in mine
        room=[o.text for o in talked.world.observations['c'] if o.event_id.startswith('@call:')]
        assert room[0]=='A stepped away from the conversation to answer a phone call.' and 'A said on the phone: Oh, hi.' in room
        assert not any('Kanishk' in t for t in room) and not any(o.event_id.startswith('@call:') for o in talked.world.observations['e'])
        assert talked.state['runtime']['calls'][0]['outcome']=='they hung up' and len(replies)==2
        assert 'A came back to the conversation.' in room
        _,ignored=ring(answer=False)
        assert ignored==[('ringing',None),('not answered',None)]
        night,missed=ring(until=1.95)
        assert missed[-1][0]=='missed' and any(o.text=='I missed a phone call from an unknown number.' for o in night.world.observations['a'])
        replies.clear();_,silent=ring(lines=(),wait=.3)
        assert silent[-1]==('ended','caller went silent')
        checks+=['a researcher phone call rings the person, who decides to answer or let it ring; mid-conversation they step away and come '
                 'back, the room hears only their side, an unknown caller stays unknown, asleep means a missed call, silence ends it']
        # Face to face: every researcher line gets the person's own turn, with the exchange so far (run-2: lines were ignored).
        asked=[]
        def talk_stub(system,context,api,model,max_tokens=600):
            situation=context.get('situation','')
            if 'new_observation' not in context and situation.startswith('Kanishk is standing with you'):
                asked.append(situation)
                return {'action_id':'speak' if len(asked)==1 else 'listen','action':'Reply.','speech':'Hi Kanishk.' if len(asked)==1 else '',
                        'goal_id':None,'plan':[],'memory_ids':[]}
            return stub(system,context,api,model,max_tokens)
        def visit_in_person(until=.752,lines=('How was school?',),again=False):
            world,policy=fixture(turns=6);door=root/f'talk-{len(list(root.glob("talk-*")))}';door.mkdir()
            control=Lifetime(world,policy);control.inbox=door/'inbox.jsonl'
            with patch('devsim.engine.request_json',side_effect=talk_stub):
                control.run(until)
                visit.talk(door,'a','Hi, I am Kanishk.','Kanishk')
                for line in lines: visit.call_say(door,line)
                visit.hang_up(door)
                control.run(until+.001,door/'world.json')
                if again:  # a second visit, a little later in the same world
                    visit.talk(door,'a','Me again.','Kanishk');visit.hang_up(door);control.run(until+.002,door/'world.json')
            return world,[(r['event'],r.get('text') or r.get('reason')) for r in visit.call_log(door)]
        met,log=visit_in_person()
        assert log==[('approaching',None),('joined',None),('said','Hi Kanishk.'),('quiet',None),('ended','caller hung up')],log
        assert len(asked)==2 and 'So far: Kanishk: Hi, I am Kanishk. / You: Hi Kanishk. / Kanishk: How was school?' in asked[1]
        mine=[o.text for o in met.world.observations['a'] if o.event_id.startswith('@call:')]
        assert mine[:3]==['Kanishk came over to talk with me, so I stepped aside from the conversation.',
                          'Kanishk said to me: Hi, I am Kanishk.','I said to Kanishk: Hi Kanishk.'] and 'I stayed quiet.' in mine
        assert met.agent('a')['relationships']['visitor-kanishk']['firsthand']
        room=[o.text for o in met.world.observations['c'] if o.event_id.startswith('@call:')]
        assert room==['Kanishk came over to talk with A.','Kanishk walked away from A.','A came back to the conversation.'],room
        assert met.state['runtime']['calls'][0]['mode']=='in_person' and next(a for a in met.state['actions'] if a['id']=='@call:0:reply-1:action')['decision']['action_id']=='listen'
        asked.clear();twice,_=visit_in_person(again=True)
        focus=twice.agent('a')['retrieval_focus']
        assert focus['policy']=='person_cued_recall' and focus['ids'] and all(i.startswith('@call:0:') for i in focus['ids'])
        # The researcher's own character: typed, played by the model toward a goal, switched both ways, recalled.
        envoy=[]
        def character_stub(system,context,api,model,max_tokens=600):
            situation=context.get('situation','')
            if 'new_observation' not in context and situation.startswith('You are Kabir'):
                envoy.append(situation)
                done=len(envoy)>=2
                return {'action_id':'end' if done else 'speak','action':'Talk.','speech':'See you around.' if done else 'Want to sit with us at lunch?',
                        'goal_id':None,'plan':[],'memory_ids':[]}
            if 'new_observation' not in context and ' is standing with you' in situation:
                asked.append(situation)
                return {'action_id':'speak','action':'Reply.','speech':'Maybe.','goal_id':None,'plan':[],'memory_ids':[]}
            return stub(system,context,api,model,max_tokens)
        def with_character(script,until=.752,world=None):
            world,policy=world or fixture(turns=6);door=root/f'send-{len(list(root.glob("send-*")))}';door.mkdir()
            control=Lifetime(world,policy);control.inbox=door/'inbox.jsonl'
            world.state['runtime']['inbox_offset']=0  # a fresh inbox file for a reused world
            with patch('devsim.engine.request_json',side_effect=character_stub):
                control.run(until)
                script(door)
                control.run(until+.001,door/'world.json')
            return world,policy,[(r['event'],r.get('label'),r.get('text') or r.get('reason')) for r in visit.call_log(door)]
        asked.clear()
        typed,policy,log=with_character(lambda d:(visit.send(d,'Kabir','a','Kanishk','a new classmate',15),
                                                 visit.call_say(d,'Hey, are you in the robotics club?'),visit.hang_up(d)))
        kabir=typed.state['entities']['kabir']
        assert kabir['facts']['sent_by']=='Kanishk' and 'kabir' in typed.state['agents'] and round((typed.day-kabir['facts']['birth_day'])/365.25)==15
        assert log==[('approaching','A',None),('joined','A',None),('said','A','Maybe.'),('ended',None,'caller hung up')],log
        theirs=[o.text for o in typed.world.observations['a'] if o.event_id.startswith('@call:')]
        assert theirs[0]=='Kabir (a new classmate) came over to talk with me, so I stepped aside from the conversation.'
        his=[o.text for o in typed.world.observations['kabir']]
        assert his==['I went over to talk with A.','I said to A: Hey, are you in the robotics club?','A said to me: Maybe.',
                     'I said goodbye to A and left.'],his
        assert typed.agent('a')['relationships']['kabir']['firsthand'] and typed.agent('kabir')['relationships']['a']['firsthand']
        envoy.clear()
        sent,_,log=with_character(lambda d:visit.send(d,'Kabir','a','Kanishk','a new classmate',15,goal='make friends with A'))
        assert [e[0] for e in log]==['approaching','joined','said','said','ended'] and log[2][1:]==('Kabir','Want to sit with us at lunch?')
        assert log[-1][2]=='character left' and 'Your aim: make friends with A.' in envoy[0] and 'So far:' in envoy[1]
        assert all(a['status']=='resolved' for a in sent.state['actions'] if a['owner']=='kabir')
        assert 'Kabir said goodbye and walked away. Kabir said: See you around.' in [o.text for o in sent.world.observations['a']]
        envoy.clear()
        _,_,log=with_character(lambda d:(visit.send(d,'Kabir','a','Kanishk','a new classmate',15,goal='make friends'),
                                         visit.call_say(d,'I will take it from here.'),visit.hang_up(d)))
        assert not envoy and log[-1][2]=='caller hung up', 'typing takes the character back from the model'
        _,_,log=with_character(lambda d:(visit.send(d,'Kabir','a','Kanishk','a new classmate',15),visit.call_say(d,'Hi.'),
                                         visit.auto(d,'ask about lunch')))
        assert len(envoy)==2 and 'Your aim: ask about lunch.' in envoy[0] and log[-1][2]=='character left'
        _,_,log=with_character(lambda d:visit.send(d,'B','a','Kanishk'))
        assert log[-1][0]=='failed' and 'belongs to the simulated world' in log[-1][2]
        _,_,log=with_character(lambda d:visit.send(d,'Zed','a','Kanishk'))
        assert log[-1][0]=='failed' and '--who' in log[-1][2]
        asked.clear()
        _,_,log=with_character(lambda d:(visit.talk(d,'kabir','How did it go?','Kanishk'),visit.hang_up(d)),until=.752+.002,
                               world=(typed,policy))
        assert log[-1]==('ended',None,'caller hung up') and ('said','Kabir','Maybe.') in log, 'your character can be asked how it went'
        checks+=['a sent character is your own persistent agent (introduced by --who on first meeting) that remembers both sides; you type '
                 'its lines or the model plays it toward a goal, typing takes it back, /auto hands it over, hanging up recalls it; '
                 'world people cannot be puppeted; you can later ask your character how it went']
        asked.clear();sleeping,log=visit_in_person(until=1.95,lines=())
        assert log[-1][0]=='failed' and not asked and not any(o.event_id.startswith('@call:') for o in sleeping.world.observations['a'])
        checks+=['face to face, each researcher line gets the person\'s own reply turn (speak, stay quiet or end) with the exchange so far; '
                 'they step aside from a group conversation and come back, the room sees the visitor arrive and leave, asleep means no meeting; '
                 'a later visit brings the person\'s memories of the visitor to the top of recall (person-cued)']
        checks+=['two people with the same name get distinct @handles and are perceived as "Priya (@priya0123)"; the bare name stays '
                 'ambiguous for testimony while an @handle resolves; duplicate handles are rejected; worlds without handles are unchanged']
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
