"""Routing, time, independent turns and recovery checks; synthetic model stubs."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import re
from time import monotonic
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
        assert all(abs(sum(e.agent(x)['time_use'].values())-(4/60+6/2.5/3600))<1e-8 for x in 'ab')  # + saying a's 6 words
        assert abs((turns[1]['day']-turns[0]['day'])*86400-(120+6/2.5))<1e-3  # b replies after a's line has been said
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
        assert abs((spoken[1]['day']-spoken[0]['day'])*1440-(.5+8/2.5/60))<1e-6  # pause + saying the 8-word scripted line
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
        def ring(answer=True,lines=('Hi, it is Kanishk.','How was school?'),until=.752,wait=300,ring_seconds=None,hang=False):
            world,policy=fixture(turns=6);phone=root/f'phone-{len(list(root.glob("phone-*")))}';phone.mkdir()
            control=Lifetime(world,policy);control.inbox=phone/'inbox.jsonl';control.call_wait_seconds=wait
            if ring_seconds is not None: control.ring_seconds=ring_seconds
            with patch('devsim.engine.request_json',side_effect=phone_stub(answer)):
                control.run(until)
                visit.call(phone,'a','Kanishk')
                if hang: visit.hang_up(phone)
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
        assert silent==[('ringing',None),('answered','Hello? Who is this?'),('said','Oh, hi.'),('ended','caller went silent')],silent
        assert 'they have said nothing for a while' in replies[0] and 'an unknown number stayed quiet' in replies[0]
        assert not any('Kanishk' in r for r in replies), 'an unknown caller was named in the person\'s own prompt'
        # Typing holds off the silence check: a line that arrives after the silence limit is still heard first.
        from threading import Timer
        replies.clear();world,policy=fixture(turns=6);typed=root/'typed';typed.mkdir()
        control=Lifetime(world,policy);control.inbox=typed/'inbox.jsonl';control.call_wait_seconds=.3
        with patch('devsim.engine.request_json',side_effect=phone_stub(True)):
            control.run(.752);visit.call(typed,'a','Kanishk');visit.typing(typed)
            Timer(.8,lambda:(visit.call_say(typed,'Sorry, slow typist.'),visit.hang_up(typed))).start()
            control.run(.753,typed/'world.json')
        assert [r['event'] for r in visit.call_log(typed)]==['ringing','answered','said','ended'] and 'said nothing' not in replies[0]
        # Ringing takes real time, and the caller can hang up while it rings.
        started=monotonic();_,rang=ring(answer=False,lines=(),ring_seconds=.6)
        assert rang==[('ringing',None),('not answered',None)] and monotonic()-started>=.6, rang
        replies.clear();hung_world,hung=ring(lines=(),ring_seconds=30,hang=True)
        assert hung==[('ringing',None),('ended','you hung up before it was answered')] and not replies, hung
        assert hung_world.state['runtime']['calls'][-1]['outcome']=='caller hung up'
        assert any(o.text=='I missed a phone call from an unknown number.' for o in hung_world.world.observations['a'])
        started=monotonic();_,night_hung=ring(until=1.95,ring_seconds=30,hang=True)
        assert night_hung[-1][0]=='missed' and night_hung[-1][1].startswith('you hung up') and monotonic()-started<10, night_hung
        checks+=['a researcher phone call rings the person, who decides to answer or let it ring; mid-conversation they step away and come '
                 'back, the room hears only their side, an unknown caller stays unknown, asleep means a missed call, silence ends it; '
                 'a paced call rings for real seconds and the caller can hang up while it rings; '
                 'a silent caller is checked on once, then the call ends; typing holds that off']
        # A later note of another kind ends the open call and keeps its own meaning (it used to be swallowed by the call).
        queued=root/'queued';queued.mkdir()
        moved,qpolicy=fixture(turns=4)
        qcontrol=Lifetime(moved,qpolicy,scripted=True);qcontrol.inbox=queued/'inbox.jsonl';qcontrol.call_wait_seconds=0
        visit.call(queued,'b',name='Kanishk');visit.call(queued,'a',name='Kanishk')
        visit.say(queued,'Please talk about the bicycle.',to='b',name='Kanishk');visit.call(queued,'c',name='Kanishk')
        qcontrol.run(.8,queued/'world.json')
        assert [c['to'] for c in moved.state['runtime']['calls']]==['b','a','c'], 'a queued call vanished inside an open call'
        assert moved.state['runtime']['visitor_log'][0]['text']=='Please talk about the bicycle.'
        assert not any(':heard' in o.event_id for o in moved.world.observations['a']), 'a conversation line was spoken on the phone'
        checks.append('a note of another kind ends an open call and keeps its own meaning: a conversation line reaches the conversation '
                      'and a second call still happens')
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
            if context.get('task')=='synthesize_character':
                return {'facets':{'E1':80},'background':['I just moved here from Pune.']}
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
        assert his==['I just moved here from Pune.','I went over to talk with A.','I said to A: Hey, are you in the robotics club?','A said to me: Maybe.',
                     'I said goodbye to A and left.'],his
        assert typed.agent('a')['relationships']['kabir']['firsthand'] and typed.agent('kabir')['relationships']['a']['firsthand']
        assert typed.agent('kabir')['facets']['E1']==80 and typed.agent('kabir')['memory_meta']['@introduce:kabir']['provenance']=='researcher_introduced'
        # An introduced relationship: a fact for both, grounded in the meeting; one introduction memory, no invented past.
        cousin,_,log=with_character(lambda d:(visit.send(d,'Ravi','a','Kanishk',"A's cousin from Delhi",19,relationship='cousin'),
                                             visit.hang_up(d)))
        intro=[k for k,m in cousin.agent('a')['memory_meta'].items() if m.get('provenance')=='researcher_introduced']
        assert len(intro)==1 and "Ravi (A's cousin from Delhi; my cousin) came over" in next(o.text for o in cousin.world.observations['a'] if o.event_id==intro[0])
        assert {k:cousin.agent('a')['relationships']['ravi'][k] for k in ('role','trust','closeness','firsthand')}=={'role':'relative','trust':.65,'closeness':.5,'firsthand':True}
        assert cousin.agent('ravi')['relationships']['a']['role']=='relative'
        bad=[]
        reject(lambda:visit.send(root,'Ravi','a','Kanishk','x',19,relationship='r'*61))
        quiet,qpolicy=fixture(turns=6);door=root/'send-scripted';door.mkdir()
        qcontrol=Lifetime(quiet,qpolicy,scripted=True);qcontrol.inbox=door/'inbox.jsonl';qcontrol.run(.752)
        visit.send(door,'Mo','a','Kanishk','a neighbour',40,relationship='neighbour');visit.hang_up(door)
        with patch('devsim.engine.request_json',side_effect=lambda *a,**k:bad.append(1)):
            qcontrol.run(.753)
        assert not bad and 'mo' in quiet.state['agents'] and quiet.agent('a')['relationships']['mo']['role']=='neighbour'
        checks+=['an introduced character gets facets and a private background synthesized from the description (no call in scripted runs); '
                 'its stated relationship becomes a fact for both at the first meeting, with one researcher-introduced introduction memory']
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
        reject(lambda:Lifetime(asleep,policy,scripted=True))
        asleep,policy=fixture();policy['household']['routines']['c']['available_hours']=[[7,17]]
        policy['household']['conversations'][0]['participants']=['a','b','c']
        Lifetime(asleep,policy,scripted=True).run(.8)
        assert asleep.state['actions'] and not any(a['owner']=='c' for a in asleep.state['actions'])
        checks+=['a conversation set when fewer than two participants are awake is rejected; an asleep invitee is not forced in']
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
        # A talk ends on its own after a silent round; a participant elsewhere comes to the room and goes back after.
        quiet,policy=fixture(turns=40)
        policy['household']['locations']['b']='hall'
        def hush(system,context,api,model,max_tokens=600):
            if 'new_observation' in context:
                return {'meaning':'Heard it.','valence':0,'arousal':.1,'importance':.5,'confidence':.6}
            talk=len(quiet.state['actions'])<2
            return {'action_id':'speak' if talk else 'listen','action':'Talk.','speech':'Hello there.' if talk else '',
                    'goal_id':None,'plan':[],'memory_ids':[]}
        with patch('devsim.engine.request_json',side_effect=hush): Lifetime(quiet,policy).run(.8)
        session=quiet.state['runtime']['conversations']['family']
        assert [t['choice'] for t in session['turns']]==['speak','speak','listen','listen']
        assert session['closed_reason']=='everyone fell silent' and session['spec']['origins']=={'b':'hall'}
        assert '@travel:family-b:arrive' not in quiet.agent('b')['memory_meta'] and household.location(quiet,'b')=='hall'
        checks+=['a conversation ends when a full round passes in silence; an invited participant elsewhere comes to the room and goes back']
        # Real-time pacing: the run waits on the wall clock, and pacing never changes what happens.
        import time
        fast,policy=fixture();Lifetime(fast,policy,scripted=True).run(.8)
        paced,policy=fixture();pace=.76*86400/1.5;start=monotonic()
        Lifetime(paced,policy,scripted=True,pace=pace).run(.8)
        took=monotonic()-start
        assert 1.4<took<6 and paced.state==fast.state,took
        reject(lambda:Lifetime(fixture()[0],policy,pace=-1))
        checks+=[f'real-time pacing waits on the wall clock ({took:.1f} s for 0.76 simulated days at {pace:.0f}x) and ends in the same world as an unpaced run']
        # Fast-forward: a researcher skip drops the waiting for those hours; every event still happens, the world is the same.
        hop=root/'skip';hop.mkdir()
        skipped,policy=fixture();control=Lifetime(skipped,policy,scripted=True,pace=pace);control.inbox=hop/'inbox.jsonl'
        visit.skip(hop,18,'Kanishk');start=monotonic();control.run(.8);took_skip=monotonic()-start
        same=lambda s:{**s,'runtime':{k:v for k,v in s['runtime'].items() if k not in ('skips','inbox_offset')}}
        assert took_skip<.8 and same(skipped.state)==same(fast.state),took_skip
        assert skipped.state['runtime']['skips'][0]['to_day']>.7 and 'skip_until' not in skipped.state['runtime']
        reject(lambda:visit.skip(hop,0));reject(lambda:visit.skip(hop,'two'));reject(lambda:visit.skip(hop,1000))
        checks+=[f'a researcher skip of 18 hours plays them without waiting ({took_skip:.2f} s instead of ~1.5 s) and ends in the same world']
        # Inner thoughts: private internal memories, only while awake and out of conversation.
        minds,policy=fixture();policy['inner_thoughts']={'mean_minutes':60}
        reasks=[]
        def thinking(system,context,api,model,max_tokens=600):
            if context.get('task')=='inner_thought':
                # Copies its last thought (test-2 run) unless shown the repeat notice.
                if 'repeat_notice' in context:
                    assert context['repeat_notice']['your_earlier_words'] in context['repeat_notice']['your_recent_thoughts']
                    reasks.append(context['repeat_notice']['your_earlier_words'])
                    return {'thought':f'Something else crosses my mind, number {len(reasks)}.','valence':.1,'arousal':.2,'importance':.3}
                return {'thought':'I wonder what '+context['identity']['id']+' should do next.','valence':.1,'arousal':.2,'importance':.3}
            return stub(system,context,api,model,max_tokens)
        with patch('devsim.engine.request_json',side_effect=thinking): Lifetime(minds,policy).run(.8)
        thoughts=[ev for ev in minds.state['events'] if ev['id'].startswith('@thought:')]
        said={}
        for ev in thoughts: said.setdefault(ev['id'].split(':')[1],[]).append(next(iter(ev['observations'].values()))['text'])
        assert reasks and all(all(x!=y for x,y in zip(t,t[1:])) for t in said.values()),said
        talk=minds.state['runtime']['conversations']['family']
        during=lambda d,p:p in talk['spec']['participants'] and talk['turns'][0]['day']-1e-9<=d<=talk['turns'][-1]['day']
        assert len({ev['id'].split(':')[1] for ev in thoughts})==5 and len(thoughts)>=20
        assert all(list(ev['observations'])==[ev['id'].split(':')[1]] and ev['observations'][ev['id'].split(':')[1]]['kind']=='internal'
                   and 7<=ev['day']%1*24<22 and not during(ev['day'],ev['id'].split(':')[1]) for ev in thoughts)
        assert all(ev['id'] not in minds.agent(p)['memory_meta'] for ev in thoughts for p in 'abcde' if p!=ev['id'].split(':')[1])
        reject(lambda:Lifetime(fixture()[0],{**policy,'inner_thoughts':{'mean_minutes':0}}))
        checks+=[f'inner thoughts ({len(thoughts)} in a day for 5 people) are private internal memories, only while awake and not in a conversation; a thought that copies a recent one is re-asked once with the earlier words shown']
    # Researcher edits and notifications through the inbox: applied at the next boundary, atomic, logged.
    with TemporaryDirectory() as box:
        door=Path(box)
        live,lpolicy=fixture()
        lpolicy={**lpolicy,'hormones':{},'skills':{}}
        control=Lifetime(live,lpolicy,scripted=True);control.inbox=door/'inbox.jsonl'
        control.run(.3)
        live.relate('a','b','classmate',trust=.5,closeness=.2)
        visit.edit(door,'a',{'facet:N1':90,'dial:threat_sensitivity':.7,'hormone:stress':.8,'mood':-.5,
                             'goal:add':{'id':'calm','description':'Find a calmer routine.','priority':.6},'tie:b:trust':.9,
                             'skill:violin':.4},'Kanishk')
        visit.edit(door,'a',{'facet:N1':95,'facet:XX':10},'Kanishk')  # one bad field: nothing applies
        visit.edit(door,'nobody',{'mood':.2},'Kanishk')
        visit.notify(door,'a','Your library book is due tomorrow.','Kanishk')
        control.run(.31)
        a=live.agent('a')
        from devsim import hormones as _h
        assert a['facets']['N1']==90 and a['dials']['threat_sensitivity']==.7 and .7<_h.read(live,'a').stress<=.8  # set to .8, then decaying
        assert a['goals']['calm']['status']=='active' and a['relationships']['b']['trust']==.9 and live.mood('a')['valence']<0
        log=live.state['runtime']['researcher_edits']
        from devsim import skills as _s
        assert abs(_s.level(live,'a','violin',.3)-.4)<1e-9 and _s.level(live,'a','violin',.31)<.4
        assert len([e for e in log if 'field' in e])==7 and len([e for e in log if 'rejected' in e])==2
        heard=[o.text for o in live.world.observations['a'] if o.event_id.startswith('@notify:')]
        assert heard==['A notification on my phone: Your library book is due tomorrow.']
        assert live.agent('a')['memory_meta'][next(o.event_id for o in live.world.observations['a'] if o.event_id.startswith('@notify:'))]['provenance']=='researcher_notification'
        live.agent('c')['alive']=False
        reject(lambda:visit.apply_edit(live,{'to':'c','changes':{'mood':.1}}))
    checks+=['researcher edits (facets, dials, hormones, mood, goals, ties) apply at the next event boundary all-or-nothing and are '
             'logged as interventions; bad fields, unknown or dead people are rejected and logged; a notification reaches the person once']
    # Silence habituates: the same "I listened quietly." is appraised once, then reused with fading weight.
    shy,spolicy=fixture(turns=12)
    silent=[]
    def shy_stub(system,context,api,model,max_tokens=600):
        if 'new_observation' in context:
            if context['new_observation']['text']=='I listened quietly.': silent.append(context['identity']['id'])
            return {'meaning':'Noted.','valence':-.6,'arousal':.3,'importance':.4,'confidence':.7}
        owner=context['identity']['id']
        return {'action_id':'speak' if owner=='b' else 'listen','action':'Talk.','speech':'Go on.' if owner=='b' else '',
                'goal_id':None,'plan':[],'memory_ids':[]}
    with patch('devsim.engine.request_json',side_effect=shy_stub): Lifetime(shy,spolicy).run(.8)
    quiet_turns=[t for t in shy.state['runtime']['conversations']['family']['turns'] if t['speaker']=='a']
    reused=[m for k,m in shy.agent('a')['memory_meta'].items() if k.startswith('@conversation:') and 'reused_appraisal' in m]
    assert len(quiet_turns)>=5 and silent.count('a')==1 and len(reused)==len(quiet_turns)-1
    checks+=[f'a person silent for {len(quiet_turns)} turns appraises their own silence once; repeats reuse it with fading weight']
    # The family cue only among family (v5 run: school talk was cued 'family' and drifted to "family stuff").
    from devsim.engine import Engine as _Engine
    seen=[]
    real=_Engine.context
    def spy(self,owner,situation,cues=(),options=None):
        if options: seen.append((owner,tuple(cues)))
        return real(self,owner,situation,cues,options)
    with patch.object(_Engine,'context',spy):
        peers,ppolicy=fixture(); Lifetime(peers,ppolicy,scripted=True).run(.8)
        peer_cues={c for o,c in seen}; seen.clear()
        kin,kpolicy=fixture(); kin.caregiver('b','a'); Lifetime(kin,kpolicy,scripted=True).run(.8)
        kin_cues={c for o,c in seen}
    assert peer_cues=={('social',)} and kin_cues=={('social','family')},(peer_cues,kin_cues)
    checks+=["conversation decisions carry the 'family' cue only when the speaker is talking with their own family"]
    # Relationships learn from interactions (v5 run: every tie stayed at its starting value for 62 days).
    from devsim import society, attention
    def ties(valences,reflection=False,tier=None,learning=True):
        w,_=fixture()
        if learning: society.configure_learning(w,{})
        if reflection: w.state['config']['cognition']={'reflection':True}
        w.relate('a','b','classmate',trust=.5,closeness=.2)
        for i,v in enumerate(valences):
            obs={'text':'B said something.','source':'b','kind':'direct','valence':v,'encountered':['b']}
            if tier:
                attention.configure(w)
                with patch('devsim.attention.allocate',return_value=attention.AttentionResult(.1,tier)):
                    w.schedule(f'x{i}',.5+i/1000,'A test.',{'a':obs}); w.advance(.5+i/1000)
            else:
                w.schedule(f'x{i}',.5+i/1000,'A test.',{'a':obs}); w.advance(.5+i/1000)
        r=w.agent('a')['relationships']['b']
        return r['closeness'],r['trust']
    warm,cold,flat=ties([.6]*10),ties([-.6]*10),ties([0]*10)
    assert warm[0]>flat[0]>.2>cold[0] and warm[1]>.5>cold[1] and flat[1]==.5
    assert ties([.6]*10,learning=False)==(.2,.5) and ties([.6]*10,reflection=True)==(.2,.5) and ties([.6]*10,tier='NONE')==(.2,.5)
    assert .2<ties([.6]*10,tier='GIST')[0]<warm[0] and all(0<=x<=1 for x in (*ties([1]*500),*ties([-1]*500)))
    checks+=[f'relationships learn from interactions: ten pleasant exchanges raise closeness to {warm[0]:.2f} and trust to {warm[1]:.2f}, '
             f'unpleasant ones lower them ({cold[0]:.2f}, {cold[1]:.2f}), neutral contact adds only familiarity; GIST counts half, '
             'an unattended event nothing, and reflection (when on) owns the change instead']
    result={'passed':True,'scope':'synthetic household engineering checks, not psychological validation','checks':checks}
    RESULTS_DIR.joinpath('household-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
