"""Explicit physical information routing and bounded, elapsed household dialogue.

Rooms, waking windows and response latencies are scenario assumptions. The
controller owns routing; a model cannot grant itself listeners or world facts.
"""
from copy import deepcopy
from math import floor

from .engine import number
from . import calendar_time
def validate(engine, settings):
    if not isinstance(settings, dict) or set(settings)-{'rooms','locations','routines','moves','conversations',
                                                      'routes','groups','channels','invitations'}:
        raise ValueError('Unsupported household settings')
    rooms = settings.get('rooms', {})
    if not isinstance(rooms, dict) or not rooms:
        raise ValueError('Household needs named rooms')
    for key, room in rooms.items():
        if not isinstance(key,str) or not key or not isinstance(room,dict) or set(room)-{'label','audible_to'}:
            raise ValueError('Invalid room')
        if not isinstance(room.get('label'),str) or not room['label'].strip():
            raise ValueError('Room needs a label')
        links=room.get('audible_to',[])
        if not isinstance(links,list) or any(not isinstance(r,str) or r not in rooms or r==key for r in links) or len(set(links))!=len(links):
            raise ValueError('Audibility needs distinct other room ids')
    if not isinstance(settings.get('locations',{}),dict) or not isinstance(settings.get('routines',{}),dict):
        raise ValueError('Locations and routines must be objects')
    for owner, room in settings.get('locations',{}).items():
        engine.agent(owner)
        if room not in rooms: raise ValueError('Unknown initial room')
    for owner, routine in settings.get('routines',{}).items():
        engine.agent(owner)
        if not isinstance(routine,dict) or set(routine)-{'available_hours','response_minutes','in_person_response_minutes'}:
            raise ValueError('Unsupported daily routine')
        windows=routine.get('available_hours',[[0,24]])
        if not isinstance(windows,list): raise ValueError('Availability must be a list')
        previous=0
        for window in windows:
            if not isinstance(window,list) or len(window)!=2: raise ValueError('Use [start,end] hour windows; split overnight windows')
            if all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in window) and window[1]<=window[0]:
                raise ValueError(f'Availability window {window} crosses midnight or is empty; windows stay within one day, '
                                 'so write 23:00-07:00 as [[0,7],[23,24]]')
            number(window[0],previous,24,'availability start')
            number(window[1],window[0]+1e-8,24,'availability end')
            previous=window[1]
        delay=routine.get('response_minutes',[1,1])
        if not isinstance(delay,list) or len(delay)!=2: raise ValueError('Response minutes need [minimum,maximum]')
        number(delay[0],.1,60,'minimum response minutes')
        number(delay[1],delay[0],60,'maximum response minutes')
        if 'in_person_response_minutes' in routine:
            spoken=routine['in_person_response_minutes']
            if not isinstance(spoken,list) or len(spoken)!=2: raise ValueError('In-person response minutes need [minimum,maximum]')
            number(spoken[0],.05,10,'minimum in-person response minutes')
            number(spoken[1],spoken[0],10,'maximum in-person response minutes')
    _validate_places(engine, settings, rooms)
    for field in ('moves','conversations'):
        rules=settings.get(field,[])
        if not isinstance(rules,list): raise ValueError('Household rules must be lists')
        ids=[]
        for rule in rules:
            if not isinstance(rule,dict) or not isinstance(rule.get('id'),str) or not rule['id'].strip():
                raise ValueError('Household rules need ids')
            ids.append(rule['id'])
            number(rule.get('day'),0,1e8,'household event day')
            if field=='conversations' and 'channel' in rule:
                if 'room' in rule or 'exit_room' in rule or rule['channel'] not in settings.get('channels',{}):
                    raise ValueError('A channel conversation names one known channel and no room')
                if set(rule.get('participants',[]))-set(settings['channels'][rule['channel']]['members']):
                    raise ValueError('Channel conversation participants must be channel members')
            elif rule.get('room') not in rooms: raise ValueError('Household event needs a known room')
            if field=='moves':
                if set(rule)-{'id','day','actor','room'}: raise ValueError('Unsupported movement field')
                engine.agent(rule['actor'])
            else:
                if set(rule)-{'id','day','room','channel','participants','topic','max_turns','exit_room','interviewer','questions'}:
                    raise ValueError('Unsupported conversation field')
                people=rule.get('participants')
                if not isinstance(people,list) or not 2<=len(people)<=12 or not all(isinstance(p,str) for p in people) or len(set(people))!=len(people):
                    raise ValueError('Conversation needs two to twelve distinct participants')
                for owner in people: engine.agent(owner)
                if not isinstance(rule.get('topic'),str) or not rule['topic'].strip() or len(rule['topic'])>2000:
                    raise ValueError('Conversation needs a short public opening topic')
                turns=rule.get('max_turns',6)
                if isinstance(turns,bool) or not isinstance(turns,int) or not 1<=turns<=40:
                    raise ValueError('Conversation turn bound must be one to forty')
                if 'exit_room' in rule and (rule['exit_room'] not in rooms or rule['exit_room']==rule['room']):
                    raise ValueError('Exit room must be a distinct known room')
                validate_interview(rule)
        if len(set(ids))!=len(ids): raise ValueError('Duplicate household rule id')


def initialize(engine, settings):
    validate(engine,settings)
    if engine.state['config'].get('household',settings)!=settings:
        raise ValueError('Cannot silently replace household policy')
    engine.state['config']['household']=deepcopy(settings)
    engine.state.setdefault('household',{'locations':deepcopy(settings.get('locations',{}))})
    engine.state['household'].setdefault('memberships',{g:list(s.get('members',[])) for g,s in settings.get('groups',{}).items()})
    runtime=engine.state['runtime']
    runtime.setdefault('household_moves',{r['id']:r['day'] for r in settings.get('moves',[]) if r['day']>=engine.day})
    runtime.setdefault('conversations',{r['id']:{'spec':deepcopy(r),'status':'scheduled','next_day':r['day'],
        'turns':[],'active':[],'cursor':0,'reservations':{}} for r in settings.get('conversations',[]) if r['day']>=engine.day})
    runtime.setdefault('trips',{})
    runtime.setdefault('group_meetings',{g:{'next_day':first_meeting(s['meetings']),'count':0} for g,s in settings.get('groups',{}).items()
        if 'meetings' in s and first_meeting(s['meetings'])>=engine.day})
    runtime.setdefault('invitations',{r['id']:{'next_day':r['day'],'attempts':0} for r in settings.get('invitations',[]) if r['day']>=engine.day})


def available(engine, owner, hours=0):
    """Entire half-open interval must fit explicit local-day waking windows."""
    routine=engine.state['config'].get('household',{}).get('routines',{}).get(owner,{})
    windows=routine.get('available_hours',[[0,24]])
    start=engine.day
    end=start+hours/24
    if not hours:
        hour=(start-floor(start))*24
        return any(a-1e-8<=hour<b-1e-8 for a,b in windows)
    while start<end:
        stop=min(end,floor(start)+1)
        low=(start-floor(start))*24
        high=(stop-floor(start))*24
        if not any(a-1e-8<=low and high<=b+1e-8 for a,b in windows): return False
        start=stop
    return True


def location(engine, owner):
    return engine.state.get('household',{}).get('locations',{}).get(owner)


def present(engine, owner, room):
    agent=engine.state['agents'].get(owner)
    return bool(room is not None and agent and agent['alive'] and agent['birth_day']<=engine.day and location(engine,owner)==room)


def view(engine, owner):
    room=location(engine,owner)
    if room is None: return None
    cfg=engine.state['config']['household']
    return {'room':room,'label':cfg['rooms'][room]['label'],
        'visible_people':[{'id':p,'name':engine.label(p)} for p in engine.state['agents']
            if p!=owner and present(engine,p,room)],
        'available_now':available(engine,owner)}


def conversation_memory(engine, owner, turns=8, previous_turns=4):
    """Working memory: the owner's own received turns of the conversation they are in now,
    and how the last session in the same place on the same topic ended.

    Search-ranked memories can bury the last few minutes (a silent reply shares no words with
    the situation text). These are only observations the owner already received; no shared transcript.
    """
    sessions=engine.state['runtime'].get('conversations',{})
    current=next((k for k,s in sessions.items() if s['status']!='closed' and owner in s['active']),None)
    if current is None: return None
    heard={}
    for o in engine.world.observations.get(owner,[]):
        if o.event_id.startswith('@conversation:'):
            heard.setdefault(o.event_id.split(':')[1],[]).append(o)
    clip=lambda text:text if len(text)<=300 else text[:299]+'…'
    result={'policy':'own_received_turns_oldest_first',
        'this_conversation':[{'minutes_ago':round((engine.day-o.day)*1440),'text':clip(o.text)} for o in heard.get(current,[])[-turns:]]}
    # Group meetings continue by group (topics may rotate); other conversations by place and topic.
    thread=lambda s:(s['spec'].get('room'),s['spec'].get('channel'),s['spec'].get('group') or s['spec']['topic'])
    earlier=[k for k in heard if k!=current and k in sessions and thread(sessions[k])==thread(sessions[current])]
    if earlier:
        last=max(earlier,key=lambda k:heard[k][-1].day)
        texts={o.event_id:o.text for o in heard[last]}
        if 'cognition' in engine.state['config']:
            # A week-old session is long-term memory: forgetting applies, so only accessible text or gist is shown.
            from .cognition import views
            available={r['event']:r['text'] for r in views(engine,owner,'',len(engine.agent(owner)['memory_meta']))}
            texts={k:available[k] for k in texts if k in available}
        if texts:
            result['previous_session']={'days_ago':round(engine.day-heard[last][-1].day,1),
                'last_turns':[clip(t) for t in list(texts.values())[-previous_turns:]]}
    return result


def in_session(engine, owner, spec):
    """Room conversations need presence; channel conversations need membership of a living, born person."""
    if 'channel' in spec:
        agent=engine.state['agents'].get(owner)
        return bool(agent and agent['alive'] and agent['birth_day']<=engine.day and
                    owner in engine.state['config']['household']['channels'][spec['channel']]['members'])
    return present(engine,owner,spec['room'])


def listeners(engine, speaker, spec=None):
    if spec and 'channel' in spec:
        return [p for p in engine.state['config']['household']['channels'][spec['channel']]['members']
                if p!=speaker and in_session(engine,p,spec) and available(engine,p)]
    room=location(engine,speaker)
    if room is None: return []
    audible=[room,*engine.state['config']['household']['rooms'][room].get('audible_to',[])]
    return [p for p in engine.state['agents'] if p!=speaker and any(present(engine,p,r) for r in audible) and available(engine,p)]


def deliver(controller, event_id, description, observations, action_id=None, facts=None, routine=False):
    engine=controller.engine
    if not controller.scripted:
        observations={p:engine.appraise(p,o,api=controller.api,model=controller.model,routine=routine) for p,o in observations.items()}
    engine.schedule(event_id,engine.day,description,observations,facts=facts,
        requires={'alive':list(observations),**({'action':action_id} if action_id else {})})
    engine.advance(engine.day)
    for owner in observations: controller._after_received(owner,event_id)


def move(controller, owner, room, event_id):
    engine=controller.engine
    if not engine.agent(owner)['alive'] or engine.agent(owner)['birth_day']>engine.day: return
    old=location(engine,owner)
    if old==room: return
    name=engine.label(owner)
    cfg=engine.state['config']['household']
    observations={owner:{'text':'I entered '+cfg['rooms'][room]['label']+'.','source':'direct','kind':'direct',
        'encountered':[p for p in engine.state['agents'] if p!=owner and present(engine,p,room)]}}
    for p in engine.state['agents']:
        if p==owner or not available(engine,p): continue
        if present(engine,p,old):
            observations[p]={'text':name+' left the room.','source':'direct','kind':'direct','encountered':[owner]}
        elif present(engine,p,room):
            observations[p]={'text':name+' entered the room.','source':'direct','kind':'direct','encountered':[owner]}
    engine.state['household']['locations'][owner]=room
    deliver(controller,event_id,'A person changes rooms.',observations,routine=True)


def close(session, reason):
    session.update(status='closed',next_day=None,closed_reason=reason)


def queue_turn(controller, key):
    engine=controller.engine
    session=engine.state['runtime']['conversations'][key]
    spec=session['spec']
    active=[p for p in session['active'] if in_session(engine,p,spec) and available(engine,p)]
    if len(active)<2: return close(session,'fewer than two available participants')
    if 'questions' in spec and sum(t['speaker']==spec['interviewer'] for t in session['turns'])>=len(spec['questions']) \
            and session['turns'] and session['turns'][-1]['speaker']!=spec['interviewer']:
        return close(session,'questions finished')
    if len(session['turns'])>=spec.get('max_turns',6): return close(session,'turn limit')
    speaker=active[session['cursor']%len(active)]
    routine=engine.state['config']['household'].get('routines',{}).get(speaker,{})
    # Face-to-face replies take seconds to minutes; response_minutes (chat pace) remains the written-channel delay.
    delay=routine.get('in_person_response_minutes' if 'channel' not in spec and 'in_person_response_minutes' in routine else 'response_minutes',[1,1])
    minutes=controller.rng('conversation',key,len(session['turns'])).uniform(*delay)
    hours=minutes/60
    # Busy/unavailable invitees cannot be silently double-booked into a dialogue.
    active=[p for p in active if calendar_time.can_reserve(engine,p,hours)]
    if speaker not in active or len(active)<2: return close(session,'response interval conflicts with availability or calendar')
    reservation='@conversation:'+key+':'+str(len(session['turns']))
    session.update(active=active,speaker=speaker,reservation_id=reservation,
        reservations={p:calendar_time.reserve(engine,p,hours,reservation) for p in active},
        status='waiting',next_day=engine.day+hours/24)


def step(controller, key):
    """One queue event. Lifetime supplies atomic rollback/checkpoint boundaries."""
    engine=controller.engine
    session=engine.state['runtime']['conversations'][key]
    spec=session['spec']
    if session['status']=='scheduled':
        session['active']=list(spec['participants'])
        queue_turn(controller,key)
        if session['status']=='waiting':
            host=session['speaker']
            people=[host,*listeners(engine,host,spec)]
            deliver(controller,'@conversation:'+key+':opening','A public conversation topic is introduced.',
                {p:{'text':'A conversation begins on this topic: '+spec['topic'],
                    'source':'direct','kind':'direct'} for p in people},routine=True)
        return
    previous=list(session['active'])
    active=[p for p in previous if in_session(engine,p,spec) and available(engine,p)]
    for p in session['reservations']:
        calendar_time.finish(engine,p,session['reservation_id'],cancel=p not in active)
    session['reservations']={}
    session['active']=active
    if len(active)<2: return close(session,'participants left, died or became unavailable')
    speaker=session['speaker']
    if speaker not in active:
        session['cursor']=0
        return queue_turn(controller,key)
    infant=(engine.day-engine.agent(speaker)['birth_day'])/365.25<2
    channel='channel' in spec
    where=('the written channel '+engine.state['config']['household']['channels'][spec['channel']]['label'] if channel
           else 'this room')
    asked=sum(t['speaker']==spec.get('interviewer') for t in session['turns'])
    interview='questions' in spec
    menu=[{'id':'listen','label':'Listen quietly without speaking.' if not channel else 'Read without replying.',
           'speech_allowed':False,'plan_allowed':not infant},
        {'id':'signal' if infant else 'speak','label':'Make a nonverbal signal.' if infant else
         ('Write a message.' if channel else
          # v2 run: Kiara and Rohan averaged 56-63 words a turn, speeches rather than conversation.
          'Say something or ask a question, as one spoken turn (usually one to three sentences); you may introduce a different topic.'),
         'speech_allowed':not infant,'plan_allowed':not infant},
        {'id':'leave','label':'Stop participating in this conversation.','speech_allowed':False,'plan_allowed':not infant}]
    if interview and speaker!=spec['interviewer']:
        menu=[{'id':'speak','label':'Answer the question in your own words.','speech_allowed':True},
              {'id':'listen','label':'Decline to answer this question.','speech_allowed':False},
              {'id':'leave','label':'End the interview.','speech_allowed':False}]
    if 'exit_room' in spec and not infant and not interview:
        menu.append({'id':'leave-room','label':'Leave for '+engine.state['config']['household']['rooms'][spec['exit_room']]['label']+'.',
                     'speech_allowed':False})
    # No shared transcript: each person sees their own received memories only.
    situation=('You are in a conversation in '+where+'. The opening topic was: '+spec['topic']+
        ' Choose your next turn using only what you have personally perceived. '+
        ('Only channel members read these messages. ' if channel else 'Other people may overhear normal room speech. ')+
        'Listening or leaving must have empty speech. Speech is a claim, not proof that its content happened.')
    if interview and speaker!=spec['interviewer']:
        interviewer=engine.label(spec['interviewer'])
        situation=(interviewer+' is interviewing you in '+where+' and has just asked: "'+spec['questions'][asked-1]+'" '
            'Answer from what you have personally experienced, decline, or end the interview. Your answer is your own '
            'account and may be incomplete. Declining or ending must have empty speech.')
    if interview and speaker==spec['interviewer']:
        # The interviewer's turns are the researcher's fixed questions: no model call, but a committed, routed action.
        proposal={'owner':speaker,'day':engine.day,'context':engine.context(speaker,situation,['social'],menu),
            'decision':{'action_id':'speak','action':'Ask the next interview question.','speech':spec['questions'][asked],
                        'goal_id':None,'plan':[],'memory_ids':[]}}
    else:
        controller._before_decision(speaker,situation)
        if not controller.scripted and 'situational_personality' in controller.policy:
            engine.generate_signatures(speaker,api=controller.api,model=controller.model)
            engine.prepare_situation(speaker,situation,f'@conversation:{key}:{len(session["turns"])}:situation',
                cues=['family','social'],half_life_days=controller.policy['situational_personality'].get('recovery_half_life_days',1),
                api=controller.api,model=controller.model)
        if controller.scripted:
            choice='signal' if infant else 'speak'
            proposal={'owner':speaker,'day':engine.day,'context':engine.context(speaker,situation,['family','social'],menu),
                'decision':{'action_id':choice,'action':'Take my conversation turn.','speech':'' if infant else 'I would like to hear what you think.',
                            'goal_id':None,'plan':[],'memory_ids':[]}}
        else:
            proposal=engine.propose(speaker,situation,cues=['family','social'],options=menu,api=controller.api,model=controller.model)
    event_id=f'@conversation:{key}:{len(session["turns"])}'
    action_id=event_id+':action'
    engine.commit_action(action_id,proposal)
    decision=proposal['decision']; choice=decision['action_id']
    name=engine.label(speaker)
    speech=decision['speech'] if choice=='speak' else ''
    behavior=({'listen':'declined to answer.' if interview else ('read without replying.' if channel else 'listened quietly.'),
        'leave':'stopped participating.','leave-room':'stood up to leave the room.',
        'signal':'made a nonverbal signal.'}.get(choice) or ('wrote: ' if channel else 'said: ')+speech)
    observations={speaker:{'text':'I '+behavior,'source':'self','kind':'direct'}}
    recipients=listeners(engine,speaker,spec) if choice in ('speak','signal') else [p for p in active if p!=speaker]
    for p in recipients:
        # A channel message is read directly but is not a physical encounter.
        same=not channel and location(engine,p)==location(engine,speaker)
        observations[p]={'text':name+' '+behavior,'source':speaker,'kind':'direct' if same or channel else 'testimony',
                         'encountered':[speaker] if same else [],'provenance':event_id}
    observations[speaker]['encountered']=[] if channel else [p for p in active if p!=speaker and location(engine,p)==location(engine,speaker)]
    deliver(controller,event_id,'A conversation turn is observed; spoken claims are not world facts.',observations,action_id)
    if choice=='speak' and 'society_layer' in engine.state['config']:
        from .population.bridge import after_turn
        after_turn(engine,speaker,[p for p in recipients if p!=speaker])
    crystal=controller.policy.get('development',{}).get('crystallization')
    if crystal is not None:
        engine.crystallize(speaker,action_id,event_id,**crystal)
    session['turns'].append({'event':event_id,'action':action_id,'speaker':speaker,'day':engine.day,
        'choice':choice,'recipients':list(observations)})
    if choice in ('leave','leave-room'):
        session['cursor']=active.index(speaker)
        session['active'].remove(speaker)
        if choice=='leave-room': move(controller,speaker,spec['exit_room'],event_id+':move')
    else:
        session['cursor']=active.index(speaker)+1
    if not controller.scripted and controller.policy.get('consolidation_batch_size'):
        for p in observations: engine.consolidate(p,api=controller.api,model=controller.model,batch_size=controller.policy['consolidation_batch_size'])
    queue_turn(controller,key)


def _validate_places(engine, settings, rooms):
    """Routes, groups, channels and invitations: the places and memberships information can travel through."""
    pairs=set()
    for route in settings.get('routes',[]) if isinstance(settings.get('routes',[]),list) else [None]:
        if not isinstance(route,dict) or set(route)!={'a','b','minutes'} or route['a'] not in rooms or route['b'] not in rooms \
                or route['a']==route['b'] or frozenset((route['a'],route['b'])) in pairs:
            raise ValueError('Routes join two distinct known rooms once, with minutes')
        number(route['minutes'],1,600,'route minutes')
        pairs.add(frozenset((route['a'],route['b'])))
    for field in ('channels','groups'):
        if not isinstance(settings.get(field,{}),dict): raise ValueError(field+' must be an object')
    for key,channel in settings.get('channels',{}).items():
        if not isinstance(channel,dict) or set(channel)!={'label','members'} or not isinstance(channel['label'],str) or not channel['label'].strip():
            raise ValueError('A channel needs a label and members')
        members=channel['members']
        if not isinstance(members,list) or len(members)<2 or len(set(members))!=len(members): raise ValueError('A channel needs two or more distinct members')
        for owner in members: engine.agent(owner)
    for key,group in settings.get('groups',{}).items():
        if not isinstance(group,dict) or set(group)-{'label','place','members','meetings'} or not isinstance(group.get('label'),str) \
                or not group['label'].strip() or group.get('place') not in rooms:
            raise ValueError('A group needs a label and a known meeting place')
        members=group.get('members',[])
        if not isinstance(members,list) or len(set(members))!=len(members): raise ValueError('Group members must be distinct')
        for owner in members: engine.agent(owner)
        if 'meetings' in group:
            meeting=group['meetings']
            topics=meeting.get('topic') if isinstance(meeting,dict) else None
            topics=[topics] if isinstance(topics,str) else topics
            if not isinstance(meeting,dict) or set(meeting)-{'first_day','start_hour','duration_hours','every_days','topic','max_turns'} \
                    or not isinstance(topics,list) or not 1<=len(topics)<=30 \
                    or not all(isinstance(t,str) and t.strip() and len(t)<=2000 for t in topics):
                raise ValueError('Group meetings need first_day, start_hour, duration_hours, every_days and a topic '
                                 '(one opening topic, or a list of up to 30 used in turn)')
            if isinstance(meeting.get('first_day'),bool) or not isinstance(meeting.get('first_day'),int) or meeting['first_day']<0:
                raise ValueError('Meeting first_day is a whole day number; the time of day is start_hour')
            number(meeting.get('start_hour'),0,24-1e-9,'meeting start_hour (time of day, 0-24)')
            number(meeting.get('every_days'),.5,365,'days between meetings')
            number(meeting.get('duration_hours'),.25,12,'meeting duration_hours (length, not a time window)')
            turns=meeting.get('max_turns',6)
            if isinstance(turns,bool) or not isinstance(turns,int) or not 1<=turns<=40: raise ValueError('Meeting turn bound must be one to forty')
    ids=[]
    for rule in settings.get('invitations',[]) if isinstance(settings.get('invitations',[]),list) else [None]:
        if not isinstance(rule,dict) or set(rule)!={'id','day','group','invitee','inviter'} or rule['group'] not in settings.get('groups',{}):
            raise ValueError('An invitation needs id, day, a known group, invitee and inviter')
        number(rule['day'],0,1e8,'invitation day')
        engine.agent(rule['invitee']); engine.agent(rule['inviter'])
        if rule['invitee']==rule['inviter'] or rule['invitee'] in settings['groups'][rule['group']].get('members',[]):
            raise ValueError('The invitee must be someone else who is not already a member')
        ids.append(rule['id'])
    if len(set(ids))!=len(ids): raise ValueError('Duplicate invitation id')


def validate_interview(rule):
    if ('questions' in rule)!=('interviewer' in rule): raise ValueError('An interview names an interviewer and questions')
    if 'questions' not in rule: return
    questions=rule['questions']
    if len(rule['participants'])!=2 or rule['interviewer'] not in rule['participants'] or rule['participants'][0]!=rule['interviewer']:
        raise ValueError('An interview has two participants, interviewer first')
    if not isinstance(questions,list) or not 1<=len(questions)<=10 or not all(isinstance(q,str) and q.strip() and len(q)<=300 for q in questions):
        raise ValueError('An interview has one to ten short questions')
    if rule.get('max_turns',2*len(questions))!=2*len(questions): raise ValueError('Interview turns are two per question')


def first_meeting(meeting):
    return meeting['first_day']+meeting['start_hour']/24


def route_minutes(engine, a, b):
    return next((r['minutes'] for r in engine.state['config']['household'].get('routes',[]) if {r['a'],r['b']}=={a,b}),None)


def travel(controller, owner, room, key):
    """Leave now and arrive after the route's minutes (instantly without a route). None if busy or not placeable."""
    engine=controller.engine
    agent=engine.agent(owner)
    if not agent['alive'] or agent['birth_day']>engine.day: return None
    old=location(engine,owner)
    if old is None:
        # In transit, a new journey used to teleport the person and the old arrival still fired later. They turn back
        # instead: the pending arrival is cancelled and they set off from where it began.
        # shortcut: distance already covered is ignored; a leg without a recorded origin cannot be interrupted.
        pending=heading(engine,owner)
        if pending is None or 'origin' not in pending[1]: return None
        engine.state['runtime']['trips'].pop(pending[0])
        calendar_time.finish(engine,owner,pending[1]['reservation'],cancel=True)
        old=engine.state['household']['locations'][owner]=pending[1]['origin']
    if old==room: return engine.day
    minutes=route_minutes(engine,old,room) if old else None
    if not minutes:
        move(controller,owner,room,'@travel:'+key)
        return engine.day
    hours=minutes/60
    if not calendar_time.can_reserve(engine,owner,hours): return None
    reservation='@travel:'+key
    calendar_time.reserve(engine,owner,hours,reservation)
    cfg=engine.state['config']['household']
    name=engine.label(owner)
    observations={owner:{'text':'I set off for '+cfg['rooms'][room]['label']+'.','source':'direct','kind':'direct'}}
    for p in engine.state['agents']:
        if p!=owner and available(engine,p) and present(engine,p,old):
            observations[p]={'text':name+' left.','source':'direct','kind':'direct','encountered':[owner]}
    engine.state['household']['locations'][owner]=None  # in transit: nowhere to be overheard or met
    deliver(controller,reservation+':depart','A person sets off on a journey.',observations,routine=True)
    arrival=engine.day+hours/24
    engine.state['runtime']['trips'][key]={'actor':owner,'room':room,'day':arrival,'phase':'arrive','reservation':reservation,'origin':old}
    return arrival


def heading(engine, owner):
    """(trip key, arrival leg) of someone currently travelling, or None."""
    return next(((k,t) for k,t in engine.state['runtime'].get('trips',{}).items() if t['actor']==owner and t['phase']=='arrive'),None)


def trip(controller, key):
    engine=controller.engine
    runtime=engine.state['runtime']
    leg=runtime['trips'][key]
    if leg['phase']=='arrive':
        del runtime['trips'][key]
        if engine.agent(leg['actor'])['alive']:
            calendar_time.finish(engine,leg['actor'],leg['reservation'])
            move(controller,leg['actor'],leg['room'],leg['reservation']+':arrive')
        return
    # A scheduled departure (such as going home after a meeting) waits while the person is busy.
    del runtime['trips'][key]
    if travel(controller,leg['actor'],leg['room'],key) is None and leg.get('attempts',0)<48 and engine.agent(leg['actor'])['alive']:
        runtime['trips'][key+'r']={**leg,'day':engine.day+.5/24,'attempts':leg.get('attempts',0)+1}


def meet(controller, group_id):
    """A recurring group meeting: available members travel to the place, talk, and go back afterwards."""
    engine=controller.engine
    runtime=engine.state['runtime']
    group=engine.state['config']['household']['groups'][group_id]
    meeting=group['meetings']
    state=runtime['group_meetings'][group_id]
    n=state['count']
    state.update(count=n+1,next_day=engine.day+meeting['every_days'])
    arrivals={}
    for owner in engine.state['household']['memberships'][group_id]:
        pending=heading(engine,owner) if location(engine,owner) is None else None
        origin=pending[1]['room'] if pending else location(engine,owner)  # where they were going is where they return
        if not available(engine,owner,meeting['duration_hours']): continue
        arrival=travel(controller,owner,group['place'],f'group-{group_id}-{n}-{owner}')
        if arrival is not None: arrivals[owner]=(arrival,origin)
    if not arrivals:
        runtime['trace'].append({'day':engine.day,'group':group_id,'meeting':n,'status':'no member could attend'})
        return
    start=max(a for a,_ in arrivals.values())+1/1440
    key=f'group-{group_id}-{n}'
    if len(arrivals)>=2:
        # A topic list rotates one per meeting, so a daily class does not open on the same subject every day.
        topic=meeting['topic'] if isinstance(meeting['topic'],str) else meeting['topic'][n%len(meeting['topic'])]
        spec={'id':key,'day':start,'room':group['place'],'participants':list(arrivals),'topic':topic,'group':group_id,
              'max_turns':meeting.get('max_turns',6)}
        runtime['conversations'][key]={'spec':spec,'status':'scheduled','next_day':start,'turns':[],'active':[],'cursor':0,'reservations':{}}
    else:  # one attendee (a solo work shift, or everyone else away): presence without a conversation
        runtime['trace'].append({'day':engine.day,'group':group_id,'meeting':n,'status':'one attendee; no conversation'})
    end=start+meeting['duration_hours']/24
    for owner,(_,origin) in arrivals.items():
        if origin and origin!=group['place']:
            runtime['trips'][f'{key}-{owner}-home']={'actor':owner,'room':origin,'day':end,'phase':'depart'}


def decide(controller, owner, situation, menu, scripted_choice, event_id):
    """One routed choice by a person: model decision (or scripted fixture), committed before any outcome."""
    engine=controller.engine
    controller._before_decision(owner,situation)
    if controller.scripted:
        proposal={'owner':owner,'day':engine.day,'context':engine.context(owner,situation,['social'],menu),
            'decision':{'action_id':scripted_choice,'action':'Choose.','speech':'','goal_id':None,'plan':[],'memory_ids':[]}}
    else:
        proposal=engine.propose(owner,situation,cues=['social'],options=menu,api=controller.api,model=controller.model)
    engine.commit_action(event_id+':action',proposal)
    return proposal['decision']['action_id']


def invite(controller, invitation_id):
    """Someone invites a person into a group; the invitee decides, and acceptance is a committed membership fact."""
    engine=controller.engine
    runtime=engine.state['runtime']
    cfg=engine.state['config']['household']
    rule=next(r for r in cfg['invitations'] if r['id']==invitation_id)
    state=runtime['invitations'][invitation_id]
    invitee,inviter,group_id=rule['invitee'],rule['inviter'],rule['group']
    members=engine.state['household']['memberships'][group_id]
    if not engine.agent(invitee)['alive'] or not engine.agent(inviter)['alive'] or invitee in members:
        state['next_day']=None
        return
    if not available(engine,invitee):
        state['attempts']+=1
        state['next_day']=engine.day+1/24 if state['attempts']<72 else None
        return
    state['next_day']=None
    group=cfg['groups'][group_id]
    names={p:engine.label(p) for p in (invitee,inviter)}
    same=location(engine,invitee) is not None and location(engine,invitee)==location(engine,inviter)
    event_id='@invitation:'+invitation_id
    deliver(controller,event_id,'An invitation to join a group.',{
        invitee:{'text':names[inviter]+' invited me to join '+group['label']+'.','source':inviter,'kind':'direct',
                 'encountered':[inviter] if same else []},
        inviter:{'text':'I invited '+names[invitee]+' to join '+group['label']+'.','source':'self','kind':'direct',
                 'encountered':[invitee] if same else []}})
    schedule=group.get('meetings')
    situation=(names[inviter]+' has invited you to join '+group['label']+', which meets at '+cfg['rooms'][group['place']]['label']+
               (f' about every {schedule["every_days"]:g} days' if schedule else '')+'. Decide whether to join.')
    menu=[{'id':'accept','label':'Accept the invitation and join.','speech_allowed':False},
          {'id':'decline','label':'Decline the invitation.','speech_allowed':False}]
    choice=decide(controller,invitee,situation,menu,'accept',event_id)
    verb='accepted' if choice=='accept' else 'declined'
    if choice=='accept': members.append(invitee)
    deliver(controller,event_id+':reply','A reply to an invitation.',{
        invitee:{'text':'I '+verb+' the invitation to join '+group['label']+'.','source':'self','kind':'direct'},
        inviter:{'text':names[invitee]+' '+verb+' the invitation to join '+group['label']+'.','source':invitee,'kind':'direct',
                 'encountered':[invitee] if same else []}},
        action_id=event_id+':action',facts={invitee:{'member_'+group_id:choice=='accept'}})


def start_conversation(controller, owner, contact, settings, key):
    """An agent-initiated conversation or interview with a contact in the same room or a shared channel."""
    engine=controller.engine
    cfg=engine.state['config'].get('household',{})
    room=location(engine,owner)
    spec={'id':key,'day':engine.day,'participants':[owner,contact],'topic':settings['topic'],
          'max_turns':settings.get('max_turns',2*len(settings.get('questions',[])) or 6)}
    if room is not None and present(engine,contact,room):
        spec['room']=room
    else:
        channel=next((c for c,v in cfg.get('channels',{}).items() if owner in v['members'] and contact in v['members']),None)
        if channel is None:
            engine.state['runtime']['trace'].append({'day':engine.day,'conversation':key,'status':'contact not reachable'})
            return
        spec['channel']=channel
    if 'questions' in settings:
        spec.update(interviewer=owner,questions=list(settings['questions']))
    engine.state['runtime']['conversations'][key]={'spec':spec,'status':'scheduled','next_day':engine.day,'turns':[],
                                                    'active':[],'cursor':0,'reservations':{}}
