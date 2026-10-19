"""Optional declared social/economic policies, not fitted population science."""
from copy import deepcopy
from math import exp,log


def configure(engine,settings):
    from .engine import number
    if not isinstance(settings,dict) or set(settings)-{'closeness_half_life_days'}:
        raise ValueError('Unknown society policy')
    number(settings.get('closeness_half_life_days',365.25),.01,1e8,'closeness half life')
    prior=engine.state['config'].get('society')
    if prior is not None and prior!=settings: raise ValueError('Cannot silently replace society policy')
    engine.state['config']['society']=deepcopy(settings)


LEARNING={'closeness_gain':.05,'familiarity_gain':.005,'trust_gain':.03}  # design defaults [D], not fitted


def configure_learning(engine,settings):
    """Rule-based relationship change from interactions (no model). Off unless the policy names it."""
    from .engine import number
    if not isinstance(settings,dict) or set(settings)-set(LEARNING):
        raise ValueError(f'relationship_learning takes {sorted(LEARNING)}')
    merged={**LEARNING,**settings}
    for key,value in merged.items():
        number(value,0,1,key)
    prior=engine.state['config'].get('relationship_learning')
    if prior is not None and prior!=merged: raise ValueError('Cannot silently replace relationship learning policy')
    engine.state['config']['relationship_learning']=merged


def learn(engine,owner,event,obs,result=None):
    """How a received interaction with a known person shifts the relationship, by a bounded rule.

    v5 run: with reflection off nothing ever changed trust or closeness, so after 62 days every tie was still at its
    starting value although the characters had formed clear opinions of each other. Each attended contact adds a
    little familiarity; how it felt (the owner's own appraisal valence) moves closeness and trust toward 1 when
    pleasant and toward 0 when not. GIST counts half and an unattended event nothing. Reflection, when on, owns this.
    """
    other=obs['source']
    agent=engine.agent(owner)
    if other==owner or other not in agent['relationships'] or obs.get('kind')=='internal':
        return
    cfg=engine.state['config']['relationship_learning']
    weight=1.0 if result is None else {'FULL':1.0,'GIST':.5,'NONE':0.0}[result.tier]
    if not weight:
        return
    valence=max(-1.0,min(1.0,obs.get('valence',0.0)))
    record=agent['relationships'][other]
    near=relationship(engine,record,event['day'])['closeness']
    toward=lambda x:max(valence,0)*(1-x)+min(valence,0)*x
    record.update(closeness=min(1.0,max(0.0,near+weight*(cfg['closeness_gain']*toward(near)+cfg['familiarity_gain']*(1-near)))),
                  trust=min(1.0,max(0.0,record['trust']+weight*cfg['trust_gain']*toward(record['trust']))),
                  last_interaction_day=event['day'])


def relationship(engine,record,day=None):
    result=deepcopy(record)
    settings=engine.state['config'].get('society')
    if settings is not None and 'last_interaction_day' in record:
        elapsed=max(0,(engine.day if day is None else day)-record['last_interaction_day'])
        result['closeness']=record['closeness']*exp(-log(2)*elapsed/settings.get('closeness_half_life_days',365.25))
    return result


def validate_transfers(engine,transfers,*,check_balances=True):
    from .engine import number
    if not isinstance(transfers,list) or len(transfers)>32: raise ValueError('Invalid transfer list')
    balances={owner:dict(a.get('resources',{})) for owner,a in engine.state['agents'].items()}
    for transfer in transfers:
        if not isinstance(transfer,dict) or set(transfer)!={'from','to','resource','amount'}:
            raise ValueError('Transfer needs source, recipient, resource and amount')
        source,target=transfer['from'],transfer['to']
        if source==target or source not in balances or target not in balances: raise ValueError('Transfer needs distinct materialized agents')
        resource=transfer['resource']
        if not isinstance(resource,str) or not resource: raise ValueError('Transfer resource is required')
        number(transfer['amount'],0,1e9,'transfer amount')
        if check_balances and balances[source].get(resource,0)<transfer['amount']: raise ValueError('Transfer overdraws source balance')
        balances[source][resource]=balances[source].get(resource,0)-transfer['amount']
        balances[target][resource]=balances[target].get(resource,0)+transfer['amount']
    return balances
