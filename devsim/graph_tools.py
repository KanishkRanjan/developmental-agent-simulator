"""Read-only researcher tools inspired by MiroFish's quick/deep/panorama modes."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from .engine import Engine,validated_json
from .graphiti_bridge import candidates,snapshot,config


def inspect(engine,owner,query,mode='quick',*,api='http://127.0.0.1:18081',model=None,limit=12):
    if mode=='panorama':
        # This is the researcher's checkpoint view, not an agent recall event or
        # a reconstruction of what the person knew at an arbitrary past time.
        from .cognition import views
        available=views(engine,owner,'',len(engine.agent(owner)['memory_meta']))
        return {'mode':mode,'scope':'researcher checkpoint inspection; no recall or agent state mutation',
            'events':[{'event':m['event'],'day':m['day'],'current_representation':m['representation'],
                       'current_meaning':m['meaning'],'kind':m['kind'],'source':m['source'],
                       'prior_interpretations':deepcopy(engine.agent(owner)['memory_meta'][m['event']].get('versions',[]))} for m in sorted(available,key=lambda m:m['day'])]}
    queries=[query]
    if mode=='deep':
        context=engine.context(owner,query);context['task']='graph_insight_queries'
        def validate(r):
            if not isinstance(r.get('queries'),list) or not 1<=len(r['queries'])<=4 or not all(isinstance(q,str) and 0<len(q)<=200 for q in r['queries']):raise ValueError('Return queries: one to four bounded questions')
        result=validated_json('Decompose this researcher question into up to four targeted search questions. '
            'Use only supplied private context; questions do not assert facts or invent people. Return JSON queries (list of strings).',
            context,validate,api,model or config()['llm_model'],350)
        queries+=result['queries']
    scores={};records={};chains=[]
    for question in queries:
        rows,info=candidates(engine,owner,question,limit)
        chains.extend(info.get('chains',[]))
        for rank,row in enumerate(rows):
            mid=row['event'];records[mid]=row;scores[mid]=scores.get(mid,0)+1/(60+rank+1)
    ids=sorted(records,key=lambda k:(-scores[k],k))[:limit]
    safe=set(ids)
    return {'mode':mode,'scope':'researcher query over one current private view; graph connectivity is not causality',
        'queries':queries,'memories':[records[mid] for mid in ids],
        'relationship_chains':[c for c in chains if c['event'] in safe][:limit*3]}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('checkpoint',type=Path)
    parser.add_argument('--owner',required=True);parser.add_argument('--mode',choices=['quick','deep','panorama','chains'],default='quick')
    parser.add_argument('--query',default='What experiences and relationships are relevant now?');parser.add_argument('--out',type=Path)
    args=parser.parse_args();engine=Engine.load(args.checkpoint);engine.agent(args.owner)
    if 'cognition' not in engine.state['config']:raise SystemExit('This checkpoint has no cognition/view policy')
    engine.state['config'].setdefault('graphiti_namespace','analyst_'+sha256(args.checkpoint.read_bytes()).hexdigest())
    before=deepcopy(engine.state);result=inspect(engine,args.owner,args.query,args.mode);assert engine.state==before
    text=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.out:
        if args.out.exists():raise SystemExit('Choose a fresh output file')
        args.out.write_text(text)
    else:print(text,end='')


if __name__=='__main__':main()
