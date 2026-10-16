"""Elapsed simulated activity intervals with day-capacity accounting."""
from math import floor
from copy import deepcopy


def portions(start,end):
    while start<end:
        boundary=min(end,floor(start)+1)
        yield str(floor(start)),(boundary-start)*24
        start=boundary


def can_reserve(engine,owner,hours):
    from .household import available
    if not available(engine,owner,hours): return False
    if hours==0: return True
    end=engine.day+hours/24
    agent=engine.state['agents'].get(owner,{})
    if any(engine.day<b['end_day'] and b['start_day']<end for b in agent.get('calendar',[]) if b['status'] in ('reserved','completed')):
        return False
    budget=engine.state['config'].get('planning',{}).get('hours_per_day',12)
    return all(agent.get('time_use',{}).get(day,0)+amount<=budget+1e-8 for day,amount in portions(engine.day,end))


def reserve(engine,owner,hours,activity_id):
    from .engine import number
    number(hours,0,24,'activity duration')
    if not can_reserve(engine,owner,hours): raise ValueError('Activity overlaps an existing commitment or exceeds day capacity')
    agent=engine.agent(owner)
    if any(b['activity']==activity_id for b in agent.get('calendar',[])): raise ValueError('Duplicate activity reservation')
    end=engine.day+hours/24
    record={'activity':activity_id,'start_day':engine.day,'end_day':end,'status':'reserved'}
    agent.setdefault('calendar',[]).append(record)
    for day,amount in portions(engine.day,end):
        agent.setdefault('time_use',{})[day]=agent.setdefault('time_use',{}).get(day,0)+amount
    return deepcopy(record)


def finish(engine,owner,activity_id,*,cancel=False):
    agent=engine.agent(owner)
    record=next(b for b in agent['calendar'] if b['activity']==activity_id)
    if record['status']!='reserved': raise ValueError('Activity is not pending')
    if cancel:
        for day,amount in portions(max(record['start_day'],engine.day),record['end_day']):
            agent['time_use'][day]=max(0,agent['time_use'].get(day,0)-amount)
        record['end_day']=min(record['end_day'],engine.day)
    record['status']='cancelled' if cancel else 'completed'
