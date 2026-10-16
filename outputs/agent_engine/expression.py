"""Configurable correlated temporary variation and explicit culture expression.

No fitted state covariance, cross-instrument mapping or national stereotype is
implied. Additional constructs require separate supplied scores/provenance.
"""
from copy import deepcopy
from hashlib import sha256
from math import exp,log,sqrt
from random import Random

DOMAINS='NEOAC'


def factor(matrix):
    from engine import number
    if not isinstance(matrix,list) or len(matrix)!=5 or any(not isinstance(row,list) or len(row)!=5 for row in matrix):
        raise ValueError('State correlation must be a five by five matrix in NEOAC order')
    lower=[[0.0]*5 for _ in range(5)]
    for i in range(5):
        for j in range(5):
            number(matrix[i][j],-1,1,'state correlation')
            if abs(matrix[i][j]-matrix[j][i])>1e-9 or (i==j and abs(matrix[i][j]-1)>1e-9):
                raise ValueError('State correlation must be symmetric with unit diagonal')
        for j in range(i+1):
            residual=matrix[i][j]-sum(lower[i][k]*lower[j][k] for k in range(j))
            if i==j:
                if residual < -1e-9: raise ValueError('State correlation is not positive semidefinite')
                lower[i][j]=sqrt(max(0,residual))
            elif lower[j][j]>1e-12: lower[i][j]=residual/lower[j][j]
            elif abs(residual)>1e-9: raise ValueError('Singular state correlation is inconsistent')
    return lower


def configure(engine,settings):
    from engine import number
    if not isinstance(settings,dict) or set(settings)-{'correlation','std_by_domain','half_life_days','per_agent','age_appropriate_actions'}:
        raise ValueError('Invalid temporary expression settings')
    if 'age_appropriate_actions' in settings and not isinstance(settings['age_appropriate_actions'],bool):
        raise ValueError('Age capability flag must be boolean')
    factor(settings.get('correlation',[[int(i==j) for j in range(5)] for i in range(5)]))
    for std in [settings.get('std_by_domain',{}),*settings.get('per_agent',{}).values()]:
        if not isinstance(std,dict) or set(std)-set(DOMAINS): raise ValueError('Unknown variation domain')
        for value in std.values(): number(value,0,10,'temporary state standard deviation')
    number(settings.get('half_life_days',1),1e-6,36525,'variation half life')
    prior=engine.state['config'].get('expression')
    if prior is not None and prior!=settings: raise ValueError('Cannot silently replace state expression policy')
    engine.state['config']['expression']=deepcopy(settings)


def vary(engine,owner,event_id,record):
    settings=engine.state['config'].get('expression')
    if settings is None: return record
    agent=engine.agent(owner)
    old=agent.get('situational_state',{})
    previous=old.get('stochastic_component',{})
    elapsed=max(0,engine.day-old.get('day',engine.day))
    phi=exp(-log(2)*elapsed/settings.get('half_life_days',1)) if previous else 0
    old_weight=exp(-log(2)*elapsed/old.get('recovery_half_life_days',1))
    seed=sha256(f'{engine.state["seed"]}:{owner}:{event_id}:state-variation'.encode()).digest()
    rng=Random(int.from_bytes(seed,'big'))
    normal=[rng.gauss(0,1) for _ in DOMAINS]
    lower=factor(settings.get('correlation',[[int(i==j) for j in range(5)] for i in range(5)]))
    std={**settings.get('std_by_domain',{}),**settings.get('per_agent',{}).get(owner,{})}
    noise={d:phi*previous.get(d,0)+sqrt(max(0,1-phi*phi))*std.get(d,0)*sum(lower[i][j]*normal[j] for j in range(i+1)) for i,d in enumerate(DOMAINS)}
    for key,offset in record['offsets'].items():
        total=offset-previous.get(key[0],0)*old_weight+noise[key[0]]
        total=max(-20,min(20,total))
        record['offsets'][key]=max(0,min(100,agent['facets'][key]+total))-agent['facets'][key]
    record.update(stochastic_component=noise,variation_policy='seeded_correlated_temporary_policy_unfitted')
    return record


def language(agent,cues):
    norms=agent.get('culture',{}).get('expression_rules',[])
    if not isinstance(norms,list): raise ValueError('Culture expression_rules must be a list')
    result=[]
    for rule in norms:
        if not isinstance(rule,dict) or set(rule)!={'cues','tendency'} or not isinstance(rule['cues'],list) or not all(isinstance(c,str) for c in rule['cues']) or not isinstance(rule['tendency'],str):
            raise ValueError('Cultural expression rules need cues and a language tendency')
        if set(rule['cues'])<=set(cues): result.append(rule['tendency'])
    extra=agent.get('additional_traits',{})
    if 'honesty_humility' in extra:
        from engine import number
        record=extra['honesty_humility'];score=number(record['percentile'],0,100,'separate Honesty-Humility percentile')
        if not isinstance(record.get('source'),str) or not record['source']: raise ValueError('Additional construct needs explicit provenance')
        if score>=80: result.append('Tends to avoid manipulation, unfair personal advantage and status entitlement.')
        elif score<=20: result.append('May pursue personal advantage, recognition or entitlement even when fairness conflicts.')
        else: result.append('Shows a moderate, context-sensitive tendency concerning sincerity, fairness and entitlement.')
    return {'tendencies':result,'policy':'explicit_cultural_rules_and_separate_supplied_constructs'}
