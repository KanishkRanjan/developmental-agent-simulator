"""Listener-scoped mentions and disambiguation; a name never creates a person."""
from copy import deepcopy
from hashlib import sha256


def known(engine,owner,observation=None):
    agent=engine.agent(owner)
    ids=set(agent['relationships'])|set(agent['references'])
    if observation:
        ids.update(observation.get('encountered',[]));ids.update(observation.get('references',[]))
    return {key:{'id':key,'name':engine.state['entities'][key]['name'],
                 'aliases':engine.state['entities'][key]['facts'].get('aliases',[])}
            for key in sorted(ids) if key in engine.state['entities'] and key!=owner}


def normalize(engine,owner,observation,mentions):
    candidates=known(engine,owner,observation)
    if not isinstance(mentions,list) or len(mentions)>12: raise ValueError('At most twelve explicit mentions are allowed')
    result=[]
    for mention in mentions:
        if not isinstance(mention,dict) or not isinstance(mention.get('span'),str) or not mention['span'] or mention['span'] not in observation['text']:
            raise ValueError('Mention span must occur exactly in received text')
        span=mention['span']; supplied=mention.get('candidate_ids',[])
        if not isinstance(supplied,list) or not all(isinstance(k,str) and k in candidates for k in supplied):
            raise ValueError('Mention cannot expose unknown identity candidates')
        matches=[key for key,item in candidates.items() if span.casefold() in [item['name'].casefold(),*[a.casefold() for a in item['aliases']]]]
        # An ambiguous name cannot be forced into one candidate by model preference.
        ids=sorted(set(matches or supplied))
        digest=sha256(f'{owner}:{observation["source"]}:{span.casefold()}'.encode()).hexdigest()[:20]
        speaker=[key for key,item in candidates.items() if observation['source'] in (key,item['name'])]
        result.append({'reference_id':'mention-'+digest,'span':span,'candidate_ids':ids,
            'resolved_id':ids[0] if len(ids)==1 else None,
            'resolution':'named_known_identity' if len(matches)==1 else 'inferred' if len(ids)==1 else 'unresolved',
            'speaker_id':speaker[0] if len(speaker)==1 else None})
    return result


def validate(engine,owner,observation):
    if 'mentions' in observation:
        expected=normalize(engine,owner,observation,[{'span':m['span'],'candidate_ids':m['candidate_ids']} for m in observation['mentions']])
        if expected!=observation['mentions']: raise ValueError('Received mention tags do not match the listener scope')
    for reference,target in observation.get('resolved_references',{}).items():
        record=engine.agent(owner).get('unresolved_references',{}).get(reference)
        if record is None or target not in engine.state['entities']:
            raise ValueError('Binding requires a received unresolved reference and committed target')
        if record['candidate_ids'] and target not in record['candidate_ids']:
            raise ValueError('Binding contradicts known identity candidates')
        if target not in observation.get('encountered',[])+observation.get('references',[]):
            raise ValueError('Binding needs explicit received identification, not a silent lookup')


def record(engine,owner,observation,event_id,day):
    agent=engine.agent(owner)
    for mention in observation.get('mentions',[]):
        rid=mention['reference_id']; existing=agent.setdefault('unresolved_references',{}).get(rid)
        if existing and existing.get('binding') is not None:
            # Established explicit identification survives a later ambiguous mention.
            mention={**mention,'resolved_id':existing['binding']}
        agent['unresolved_references'][rid]={**deepcopy(mention),
            'evidence':list(dict.fromkeys((existing or {}).get('evidence',[])+[event_id])),
            **({key:deepcopy(existing[key]) for key in ('binding','binding_evidence','versions') if key in existing} if existing else {})}
        key=mention['resolved_id'] or rid
        agent['references'].setdefault(key,[]).append(event_id)
    for rid,target in observation.get('resolved_references',{}).items():
        ref=agent['unresolved_references'][rid]
        ref.setdefault('versions',[]).append({'resolved_id':ref['resolved_id'],'day':day})
        ref.update(resolved_id=target,binding=target,binding_evidence=event_id)
        agent['references'].setdefault(target,[]).append(event_id)
