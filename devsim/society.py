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
