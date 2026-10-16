"""Schema-constrained open-value biography generation from world commitments.

Model prose is not world truth. Structured temporal fields are committed as
synthetic initialization; received testimony is never supplied as constraints.
"""
from copy import deepcopy

PROTECTED={'birth_day','biological_parents','caregivers','alive','name','aliases'}


def expand(engine,owner,policy,*,api,model):
    from .engine import validated_json,number
    entity=engine.state['entities'][owner]
    version=policy.get('id','generative-v1')
    if version in entity.get('generated_biography',{}): return
    fields=policy.get('fields',['education','occupation','residence','interests'])
    if not isinstance(fields,list) or not 1<=len(fields)<=12 or not all(isinstance(f,str) and f and f not in PROTECTED for f in fields) or len(set(fields))!=len(fields):
        raise ValueError('Biography needs one to twelve unprotected field names')
    birth=entity['facts'].get('birth_day',engine.state['agents'].get(owner,{}).get('birth_day'))
    if birth is None: raise ValueError('Commit an age before generating a temporal biography')
    locks=[{'event':e['id'],'day':e['day'],'facts':{f:v for f,v in e['facts'].get(owner,{}).items() if f in fields}}
        for e in engine.state['events'] if e['status']=='applied' and any(f in e['facts'].get(owner,{}) for f in fields)]
    # Effects are also world commitments and must constrain later lazy expansion.
    for update in engine.state['updates']:
        if update['kind']=='world_consequences':
            facts={f:v for f,v in update['effects'].get('facts',{}).get(owner,{}).items() if f in fields}
            if facts: locks.append({'event':update['id'],'day':update['day'],'facts':facts})
    prior=[epoch for record in entity.get('generated_biography',{}).values() for epoch in record['timeline']]
    context={'task':'generate_biography','identity':{'id':owner,'name':entity['name']},'simulated_day':engine.day,
        'birth_day':birth,'allowed_fields':fields,'current_commitments':deepcopy(entity['facts']),
        'world_fact_locks':locks,'prior_timeline':deepcopy(prior)}
    def validate(result):
        current=result.get('current_facts');timeline=result.get('timeline')
        if not isinstance(current,dict) or set(current)!=set(fields): raise ValueError('Choose exactly the allowed current biography fields')
        def value(v):
            if not isinstance(v,str) or not v.strip() or len(v)>300: raise ValueError('Biography values need bounded text')
        for f,v in current.items():
            value(v)
            if f in entity['facts'] and entity['facts'][f]!=v: raise ValueError('Generated biography contradicts current committed '+f)
        if not isinstance(timeline,list) or not 1<=len(timeline)<=32: raise ValueError('Return one to thirty-two structured history intervals')
        for epoch in timeline:
            if not isinstance(epoch,dict) or set(epoch)!={'field','value','start_day','end_day'} or epoch['field'] not in fields:
                raise ValueError('History interval has unsupported fields')
            value(epoch['value']);number(epoch['start_day'],birth,engine.day,'history start');number(epoch['end_day'],epoch['start_day'],engine.day,'history end')
            if epoch['start_day']==epoch['end_day']: raise ValueError('Biography intervals must have positive duration')
            if epoch['end_day']==engine.day and epoch['value']!=current[epoch['field']]:
                raise ValueError('Latest interval contradicts current field value')
            for lock in locks:
                if epoch['start_day']<=lock['day']<epoch['end_day'] and epoch['field'] in lock['facts'] and lock['facts'][epoch['field']]!=epoch['value']:
                    raise ValueError('Biography conflicts with an applied world event')
        all_epochs=[*prior,*timeline]
        for i,epoch in enumerate(all_epochs):
            for other in all_epochs[:i]:
                if epoch['field']==other['field'] and max(epoch['start_day'],other['start_day'])<min(epoch['end_day'],other['end_day']) and epoch['value']!=other['value']:
                    raise ValueError('Conflicting overlapping biography intervals')
        if not isinstance(result.get('overview'),str) or len(result['overview'])>2400: raise ValueError('Invalid synthetic overview')
    result=validated_json('Generate a coherent fictional personal background constrained by this controller record. '
        'Return JSON current_facts (exactly allowed_fields, free text values), timeline (1..32 objects containing '
        'field, value, start_day, end_day using absolute simulated DAYS, end_day exclusive), and overview (short prose). '
        'Honor birth_day, current_commitments, world_fact_locks and prior_timeline. Cover earlier life where useful, '
        'without conflicting overlaps. Do not create new people, claim verification of testimony, add memories or alter '
        'family identity. Current values must agree with intervals ending at simulated_day. Prose is synthetic context, '
        'not additional facts. Short sparse consistent histories are preferable to invented precision.',context,validate,api,model,1700)
    engine.entity(owner,entity['name'],result['current_facts'])
    entity.setdefault('generated_biography',{})[version]={**deepcopy(result),'day':engine.day,
        'policy':'open_values_structured_synthetic_initialization','invented_private_observations':False}
