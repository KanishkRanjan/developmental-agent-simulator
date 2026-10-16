"""Explicit time/resource constraints, habits, biographies and world transitions.

Scenario choices provide canonical consequences; model speech cannot authorize
world facts, money, births, introductions, illness or death.
"""
from copy import deepcopy
from math import floor


def configure(engine,settings):
    from engine import number
    if not isinstance(settings,dict) or set(settings)-{'hours_per_day','habit_half_life_days','habit_gain','habit_max','calendar_mode','grounded_plans'}:
        raise ValueError('Unsupported planning policy')
    if 'grounded_plans' in settings and not isinstance(settings['grounded_plans'],bool):
        raise ValueError('grounded_plans must be boolean')
    if settings.get('calendar_mode','daily_budget') not in ('daily_budget','elapsed'):
        raise ValueError('Unknown activity calendar mode')
    for key,default,low,high in [('hours_per_day',12,.1,24),('habit_half_life_days',30,.01,36525),
            ('habit_gain',.1,0,1),('habit_max',1,.01,10)]:
        number(settings.get(key,default),low,high,key)
    prior=engine.state['config'].get('planning')
    if prior is not None and prior!=settings: raise ValueError('Cannot silently replace planning policy')
    engine.state['config']['planning']=deepcopy(settings)


def capacity(engine,owner):
    agent=engine.agent(owner)
    used=agent.get('time_use',{}).get(str(floor(engine.day)),0)
    return max(0,engine.state['config'].get('planning',{}).get('hours_per_day',12)-used)


def affordable(engine,owner,option):
    if engine.state['config'].get('planning',{}).get('calendar_mode')=='elapsed':
        from calendar_time import can_reserve
        if not can_reserve(engine,owner,option.get('duration_hours',0)): return False
        contact=option.get('contact')
        if contact and not can_reserve(engine,contact,option.get('contact_duration_hours',option.get('duration_hours',0))): return False
    if engine.state['config'].get('planning',{}).get('calendar_mode')!='elapsed' and option.get('duration_hours',0)>capacity(engine,owner): return False
    resources=engine.agent(owner).get('resources',{})
    if any(resources.get(key,0)<value for key,value in option.get('costs',{}).items()): return False
    required = option.get('requires', {})
    if any(not engine.agent(a)['alive'] for a in required.get('alive', [])): return False
    if any(any(engine.state['entities'][key]['facts'].get(k)!=v for k,v in values.items())
           for key,values in required.get('facts',{}).items()): return False
    for branch in ('effects_success','effects_failure'):
        effects = option.get(branch, {})
        if any(birth['id'] in engine.state['entities'] for birth in effects.get('births',[])): return False
        for resource,delta in effects.get('resources',{}).get(owner,{}).items():
            if resources.get(resource,0)-option.get('costs',{}).get(resource,0)+delta<0: return False
    goal=option.get('goal_id')
    return goal is None or engine.agent(owner)['goals'].get(goal,{}).get('status')=='active'


def planning_context(engine,owner):
    agent=engine.agent(owner); settings=engine.state['config'].get('planning',{})
    habits=[]
    for key,record in agent.get('habits',{}).items():
        strength=record['strength']*2**(-(engine.day-record['day'])/settings.get('habit_half_life_days',30))
        if strength>.01:
            habits.append({'action_id':key.split(':')[-1],'cues':record['cues'],'familiarity':strength,
                           'evidence':record['evidence'][-3:]})
    return {'available_hours_today':capacity(engine,owner),'resources':deepcopy(agent.get('resources',{})),
            'habits':sorted(habits,key=lambda h:h['familiarity'],reverse=True)[:8],
            'policy':'scenario_capacity_and_decaying_action_familiarity',
            'overdue_goals':[key for key,g in agent['goals'].items() if g['status']=='active' and g.get('deadline') is not None and g['deadline']<engine.day]}


def record_activity(engine,owner,option,evidence,cues):
    agent=engine.agent(owner)
    if evidence not in agent['memory_meta'] or not any(a['owner']==owner and a['status']=='resolved' and a.get('outcome_event')==evidence for a in engine.state['actions']):
        raise ValueError('Activity requires a received resolved outcome')
    if evidence in agent.get('activity_evidence',[]): raise ValueError('Duplicate activity accounting')
    elapsed=engine.state['config'].get('planning',{}).get('calendar_mode')=='elapsed'
    if not elapsed and not affordable(engine,owner,{k:v for k,v in option.items() if k!='goal_id'}):
        raise ValueError('Activity exceeds time or resource capacity')
    if elapsed:
        from calendar_time import finish
        if any(agent.get('resources',{}).get(k,0)<v for k,v in option.get('costs',{}).items()):
            raise ValueError('Activity resources no longer available')
        finish(engine,owner,evidence)
    settings=engine.state['config'].get('planning',{})
    if not elapsed:
        agent.setdefault('time_use',{}).setdefault(str(floor(engine.day)),0)
        agent['time_use'][str(floor(engine.day))]+=option.get('duration_hours',0)
    for resource,cost in option.get('costs',{}).items():
        agent.setdefault('resources',{})[resource]-=cost
    key=':'.join([*sorted(cues),option['id']])
    old=agent.setdefault('habits',{}).get(key,{'strength':0,'day':engine.day,'evidence':[],'days':[]})
    strength=old['strength']*2**(-(engine.day-old['day'])/settings.get('habit_half_life_days',30))
    if floor(engine.day) not in old.get('days',[]): strength+=settings.get('habit_gain',.1)
    agent['habits'][key]={'strength':min(settings.get('habit_max',1),strength),'day':engine.day,
        'cues':list(cues),'evidence':old['evidence']+[evidence],'days':old.get('days',[])+[floor(engine.day)]}
    agent.setdefault('activity_evidence',[]).append(evidence)


def expand_background(engine,key,policy,*,api,model):
    """Need-driven constrained generation from controller-authored alternatives.

    Only world commitments are inputs; listeners' accounts are excluded. Free
    model prose is a synthetic summary, never a historical event assertion.
    Canonical milestones add shared history commitments, not private memories.
    """
    from engine import validated_json, number
    if key not in engine.state['entities']: raise ValueError('Background requires committed identity')
    if policy.get('mode') == 'generative':
        from biography import expand
        return expand(engine,key,policy,api=api,model=model)
    if policy.get('mode','alternatives') != 'alternatives':
        raise ValueError('Unknown background generation mode')
    entity=engine.state['entities'][key]
    slots=policy.get('slots',{})
    if not isinstance(slots,dict) or not slots or set(slots)&{'birth_day','biological_parents','caregivers','alive','name'}:
        raise ValueError('Background slots cannot change protected identity/family facts')
    if any(not isinstance(v,list) or not v for v in slots.values()): raise ValueError('Background slots need alternatives')
    version=policy.get('id','background-v1')
    if version in entity.get('background_versions',{}): return
    milestones=policy.get('milestones',[])
    if len({m['id'] for m in milestones})!=len(milestones): raise ValueError('Duplicate milestone ids')
    committed_birth=entity['facts'].get('birth_day',engine.state['agents'].get(key,{}).get('birth_day',-1e8))
    for milestone in milestones:
        number(milestone['day'],committed_birth,engine.day,'background milestone day')
        if set(milestone)-{'id','day','description','participants','requires_facts'}: raise ValueError('Unsupported milestone field')
        if not milestone.get('description') or key not in milestone.get('participants',[]) or any(p not in engine.state['entities'] for p in milestone['participants']):
            raise ValueError('Milestone requires known participants including subject')
        for participant in milestone['participants']:
            birth=engine.state['entities'][participant]['facts'].get('birth_day',-1e8)
            if milestone['day']<birth: raise ValueError('Milestone precedes participant birth')
    # Existing shared events involving the subject constrain, but do not expose
    # other participants' private observations or subjective interpretations.
    shared=[{'id':e['id'],'day':e['day'],'description':e['description']} for e in engine.state['events']
            if e['status']=='applied' and (key in e['observations'] or key in e['facts'])]
    existing=entity.get('background_versions',{})
    context={'task':'expand_constrained_background','identity':{'id':key,'name':entity['name']},
        'simulated_day':engine.day,'committed_facts':deepcopy(entity['facts']),
        'shared_event_constraints':shared,'previous_background':deepcopy(existing),
        'slots':deepcopy(slots),'milestone_alternatives':deepcopy(milestones)}
    def validate(result):
        choices=result.get('choices')
        if not isinstance(choices,dict) or set(choices)!=set(slots): raise ValueError('Choose exactly the offered biography slots')
        for field,index in choices.items():
            if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(slots[field]): raise ValueError('Invalid background alternative')
            if field in entity['facts'] and entity['facts'][field]!=slots[field][index]: raise ValueError('Background contradicts committed fact')
        ids=result.get('milestone_ids')
        if not isinstance(ids,list) or not all(isinstance(i,str) for i in ids) or len(set(ids))!=len(ids) or any(i not in {m['id'] for m in milestones} for i in ids):
            raise ValueError('milestone_ids must contain only ids from milestone_alternatives; allowed ids: ' +
                             str([m['id'] for m in milestones]) + '. Use [] when none are offered; shared_event_constraints are not selectable milestones.')
        facts={**entity['facts'],**{field:slots[field][index] for field,index in choices.items()}}
        for milestone in milestones:
            if milestone['id'] in ids and any(facts.get(k)!=v for k,v in milestone.get('requires_facts',{}).items()):
                raise ValueError('Milestone contradicts biography commitments')
            prior = engine.state.get('background_history', {}).get(milestone['id'])
            if milestone['id'] in ids and prior is not None and prior != milestone:
                raise ValueError('Background contradicts a shared historical commitment')
        if not isinstance(result.get('summary'),str) or len(result['summary'])>2400: raise ValueError('Invalid background summary')
    result=validated_json('Choose a coherent synthetic background from the offered canonical alternatives. '
        'Honor committed facts and shared events. Do not use testimony as world truth or invent extra people/events. '
        'Return JSON choices (slot to zero-based alternative index), milestone_ids (only ids from '
        'milestone_alternatives, [] if empty; never copy shared_event_constraints ids), summary (short synthetic overview).',
        context,validate,api,model,700)
    engine.entity(key,entity['name'],{field:slots[field][index] for field,index in result['choices'].items()})
    for milestone in milestones:
        if milestone['id'] in result['milestone_ids']:
            engine.state.setdefault('background_history', {})[milestone['id']] = deepcopy(milestone)
    entity.setdefault('background_versions',{})[version]={'day':engine.day,'summary':result['summary'],
        'choices':deepcopy(result['choices']),'milestones':[deepcopy(m) for m in milestones if m['id'] in result['milestone_ids']],
        'policy':'controller_alternatives_synthetic_generation','invented_private_memories':False}


def validate_effects(engine,effects, *, replay=False):
    from engine import number
    if not isinstance(effects,dict) or set(effects)-{'facts','resources','relationships','births','deaths','transfers'}:
        raise ValueError('Unsupported world consequences')
    if 'transfers' in effects:
        from society import validate_transfers
        validate_transfers(engine,effects['transfers'],check_balances=False)
    for owner,changes in effects.get('resources',{}).items():
        engine.agent(owner)
        if not isinstance(changes,dict): raise ValueError('Resource deltas require an object')
        for key,value in changes.items():
            if not isinstance(key,str) or not key: raise ValueError('Invalid resource name')
            number(value,-1e9,1e9,'resource delta')
    for key,facts in effects.get('facts',{}).items():
        if key not in engine.state['entities'] or not isinstance(facts,dict) or set(facts)&{'birth_day','biological_parents','caregivers'}:
            raise ValueError('World effects cannot rewrite protected identities')
    for pair in effects.get('relationships',[]):
        if set(pair)!={'a','b','role'} or pair['a']==pair['b'] or not isinstance(pair['role'],str) or not pair['role']:
            raise ValueError('Invalid shared relationship transition')
        engine.agent(pair['a']); engine.agent(pair['b'])
    for birth in effects.get('births',[]):
        if replay and any(birth == recorded for update in engine.state['updates']
                          if update['kind']=='world_consequences'
                          for recorded in update['effects'].get('births', [])):
            continue
        if set(birth)-{'id','name','biological_parents','caregivers','new_caregivers','facts'} or not birth.get('id') or birth['id'] in engine.state['entities'] or not birth.get('name'):
            raise ValueError('Birth needs a fresh committed identity')
        if not isinstance(birth.get('facts',{}),dict) or set(birth.get('facts',{}))&{'birth_day','biological_parents','caregivers','name'}:
            raise ValueError('Birth initial facts cannot replace identity/family fields')
        new = birth.get('new_caregivers', [])
        if not isinstance(new,list) or len(new)>8:
            raise ValueError('New family context is bounded to eight necessary caregivers')
        new_ids = set()
        for person in new:
            if set(person)!={'id','name','age_years'} or not isinstance(person['id'],str) or not person['id'] or person['id'] in new_ids or person['id'] in engine.state['entities'] or person['id']==birth['id'] or not isinstance(person['name'],str) or not person['name']:
                raise ValueError('New caregivers need distinct identities and names')
            number(person['age_years'],18,100,'scenario caregiver age')
            new_ids.add(person['id'])
        parents=birth.get('biological_parents',[])
        if not isinstance(parents,list) or len(parents)>2 or not all(isinstance(p,str) for p in parents) or len(set(parents))!=len(parents):
            raise ValueError('Invalid biological parents')
        for parent in parents:
            if parent not in new_ids: engine.agent(parent)
        if any(c not in engine.state['entities'] and c not in new_ids for c in birth.get('caregivers',[])):
            raise ValueError('Birth caregiver must already be committed')
        if any(p not in set(parents)|set(birth.get('caregivers',[])) for p in new_ids):
            raise ValueError('Do not expand unrelated people while generating a family')
    for owner in effects.get('deaths',[]): engine.agent(owner)


def apply_effects(engine,effects,event_id):
    """Called inside the controller's event transaction after resolution."""
    backup = deepcopy(engine.state)
    try:
        _apply_effects(engine,effects,event_id)
    except Exception:
        engine.state = backup
        raise


def _apply_effects(engine,effects,event_id):
    validate_effects(engine,effects)
    uid=event_id+':world-effects'
    if any(u['id']==uid for u in engine.state['updates']): raise ValueError('World effects already applied')
    event=next((e for e in engine.state['events'] if e['id']==event_id and e['status']=='applied'),None)
    if event is None: raise ValueError('World effects require an applied event')
    for owner,changes in effects.get('resources',{}).items():
        resources=engine.agent(owner).get('resources',{})
        if any(resources.get(k,0)+v<0 for k,v in changes.items()): raise ValueError('World consequence overdraws a resource')
    for owner,changes in effects.get('resources',{}).items():
        resources=engine.agent(owner).setdefault('resources',{})
        for key,delta in changes.items(): resources[key]=resources.get(key,0)+delta
    if 'transfers' in effects:
        from society import validate_transfers
        balances=validate_transfers(engine,effects['transfers'])
        for owner,values in balances.items():
            if values or 'resources' in engine.agent(owner): engine.agent(owner)['resources']=values
    for key,facts in effects.get('facts',{}).items(): engine.state['entities'][key]['facts'].update(deepcopy(facts))
    for pair in effects.get('relationships',[]):
        # A social role transition needs a received joint encounter, not gossip.
        for a,b in [(pair['a'],pair['b']),(pair['b'],pair['a'])]:
            if b not in event['observations'].get(a,{}).get('encountered',[]):
                raise ValueError('Shared relationship transition requires both participants receiving the encounter')
            old=engine.agent(a)['relationships'].get(b,{})
            engine.relate(a,b,pair['role'],firsthand=True,evidence=event_id,
                trust=old.get('trust',.5),closeness=old.get('closeness',0))
    for birth in effects.get('births',[]):
        # Necessary parent/caregiver context exists before the child is drawn;
        # no recursive parent-of-parent or fabricated childhood observations.
        for person in birth.get('new_caregivers',[]):
            engine.entity(person['id'],person['name'],{'birth_day':engine.day-person['age_years']*365.25})
            engine.materialize_for_interaction(person['id'])
        engine.entity(birth['id'],birth['name'],{'birth_day':engine.day,**deepcopy(birth.get('facts',{}))})
        engine.materialize_child(birth['id'],biological_parents=birth.get('biological_parents',[]),
            caregivers=birth.get('caregivers',[]),birth_day=engine.day)
    for owner in effects.get('deaths',[]): engine.agent(owner)['alive']=False
    engine.state['updates'].append({'id':uid,'kind':'world_consequences','day':engine.day,'effects':deepcopy(effects)})
