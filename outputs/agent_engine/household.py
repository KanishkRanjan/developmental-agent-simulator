"""Explicit physical information routing and bounded, elapsed household dialogue.

Rooms, waking windows and response latencies are scenario assumptions. The
controller owns routing; a model cannot grant itself listeners or world facts.
"""
from copy import deepcopy
from math import floor

from engine import number
import calendar_time


def validate(engine, settings):
    if not isinstance(settings, dict) or set(settings)-{'rooms','locations','routines','moves','conversations'}:
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
        if not isinstance(routine,dict) or set(routine)-{'available_hours','response_minutes'}:
            raise ValueError('Unsupported daily routine')
        windows=routine.get('available_hours',[[0,24]])
        if not isinstance(windows,list): raise ValueError('Availability must be a list')
        previous=0
        for window in windows:
            if not isinstance(window,list) or len(window)!=2: raise ValueError('Use [start,end] hour windows; split overnight windows')
            number(window[0],previous,24,'availability start')
            number(window[1],window[0]+1e-8,24,'availability end')
            previous=window[1]
        delay=routine.get('response_minutes',[1,1])
        if not isinstance(delay,list) or len(delay)!=2: raise ValueError('Response minutes need [minimum,maximum]')
        number(delay[0],.1,60,'minimum response minutes')
        number(delay[1],delay[0],60,'maximum response minutes')
    for field in ('moves','conversations'):
        rules=settings.get(field,[])
        if not isinstance(rules,list): raise ValueError('Household rules must be lists')
        ids=[]
        for rule in rules:
            if not isinstance(rule,dict) or not isinstance(rule.get('id'),str) or not rule['id'].strip():
                raise ValueError('Household rules need ids')
            ids.append(rule['id'])
            number(rule.get('day'),0,1e8,'household event day')
            if rule.get('room') not in rooms: raise ValueError('Household event needs a known room')
            if field=='moves':
                if set(rule)-{'id','day','actor','room'}: raise ValueError('Unsupported movement field')
                engine.agent(rule['actor'])
            else:
                if set(rule)-{'id','day','room','participants','topic','max_turns','exit_room'}:
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
        if len(set(ids))!=len(ids): raise ValueError('Duplicate household rule id')


def initialize(engine, settings):
    validate(engine,settings)
    if engine.state['config'].get('household',settings)!=settings:
        raise ValueError('Cannot silently replace household policy')
    engine.state['config']['household']=deepcopy(settings)
    engine.state.setdefault('household',{'locations':deepcopy(settings.get('locations',{}))})
    runtime=engine.state['runtime']
    runtime.setdefault('household_moves',{r['id']:r['day'] for r in settings.get('moves',[]) if r['day']>=engine.day})
    runtime.setdefault('conversations',{r['id']:{'spec':deepcopy(r),'status':'scheduled','next_day':r['day'],
        'turns':[],'active':[],'cursor':0,'reservations':{}} for r in settings.get('conversations',[]) if r['day']>=engine.day})


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
        'visible_people':[{'id':p,'name':engine.state['entities'][p]['name']} for p in engine.state['agents']
            if p!=owner and present(engine,p,room)],
        'available_now':available(engine,owner)}


def listeners(engine, speaker):
    room=location(engine,speaker)
    if room is None: return []
    audible=[room,*engine.state['config']['household']['rooms'][room].get('audible_to',[])]
    return [p for p in engine.state['agents'] if p!=speaker and any(present(engine,p,r) for r in audible) and available(engine,p)]


def deliver(controller, event_id, description, observations, action_id=None):
    engine=controller.engine
    if not controller.scripted:
        observations={p:engine.appraise(p,o,api=controller.api,model=controller.model) for p,o in observations.items()}
    engine.schedule(event_id,engine.day,description,observations,
        requires={'alive':list(observations),**({'action':action_id} if action_id else {})})
    engine.advance(engine.day)
    for owner in observations: controller._after_received(owner,event_id)


def move(controller, owner, room, event_id):
    engine=controller.engine
    if not engine.agent(owner)['alive'] or engine.agent(owner)['birth_day']>engine.day: return
    old=location(engine,owner)
    if old==room: return
    name=engine.state['entities'][owner]['name']
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
    deliver(controller,event_id,'A person changes rooms.',observations)


def close(session, reason):
    session.update(status='closed',next_day=None,closed_reason=reason)


def queue_turn(controller, key):
    engine=controller.engine
    session=engine.state['runtime']['conversations'][key]
    spec=session['spec']
    active=[p for p in session['active'] if present(engine,p,spec['room']) and available(engine,p)]
    if len(active)<2: return close(session,'fewer than two available participants')
    if len(session['turns'])>=spec.get('max_turns',6): return close(session,'turn limit')
    speaker=active[session['cursor']%len(active)]
    delay=engine.state['config']['household'].get('routines',{}).get(speaker,{}).get('response_minutes',[1,1])
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
            people=[host,*listeners(engine,host)]
            deliver(controller,'@conversation:'+key+':opening','A public conversation topic is introduced.',
                {p:{'text':'A conversation begins on this topic: '+spec['topic'],
                    'source':'direct','kind':'direct'} for p in people})
        return
    previous=list(session['active'])
    active=[p for p in previous if present(engine,p,spec['room']) and available(engine,p)]
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
    menu=[{'id':'listen','label':'Listen quietly without speaking.','speech_allowed':False,'plan_allowed':not infant},
        {'id':'signal' if infant else 'speak','label':'Make a nonverbal signal.' if infant else 'Say something or ask a question; you may introduce a different topic.',
         'speech_allowed':not infant,'plan_allowed':not infant},
        {'id':'leave','label':'Stop participating in this conversation.','speech_allowed':False,'plan_allowed':not infant}]
    if 'exit_room' in spec and not infant:
        menu.append({'id':'leave-room','label':'Leave for '+engine.state['config']['household']['rooms'][spec['exit_room']]['label']+'.',
                     'speech_allowed':False})
    # No shared transcript: each person sees their own received memories only.
    situation=('You are in a conversation. The public opening topic was: '+spec['topic']+
        ' Choose your next turn using only what you have personally perceived. Other people may overhear normal room speech. '
        'Listening or leaving must have empty speech. Speech is a claim, not proof that its content happened.')
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
    name=engine.state['entities'][speaker]['name']
    speech=decision['speech'] if choice=='speak' else ''
    behavior=({'listen':'listened quietly.','leave':'stopped participating.','leave-room':'stood up to leave the room.',
        'signal':'made a nonverbal signal.'}.get(choice) or 'said: '+speech)
    observations={speaker:{'text':'I '+behavior,'source':'self','kind':'direct'}}
    recipients=listeners(engine,speaker) if choice in ('speak','signal') else [p for p in active if p!=speaker]
    for p in recipients:
        same=location(engine,p)==location(engine,speaker)
        observations[p]={'text':name+' '+behavior,'source':speaker,'kind':'direct' if same else 'testimony',
                         'encountered':[speaker] if same else [],'provenance':event_id}
    observations[speaker]['encountered']=[p for p in active if p!=speaker]
    deliver(controller,event_id,'A conversation turn is observed; spoken claims are not world facts.',observations,action_id)
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
