"""Live local Graphiti integration checks, not measured psychological accuracy."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest.mock import patch
from devsim.engine import Engine,FACET_NAMES
from devsim import cognition, graphiti_bridge
from devsim.graph_tools import inspect

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def fixture():
    e=Engine(seed=811)
    for key in ['a','b']:
        e.entity(key,key.upper(),{'birth_day':-25*365.25});e.materialize(key,dict.fromkeys(FACET_NAMES,50),birth_day=-25*365.25)
    cognition.configure(e,{'graphiti_retrieval':True,'indexed_retrieval':True,'detail_threshold':.8,'semantic_candidates':6})
    e.schedule('work',0,'A receives an employment episode.',{'a':{'text':'My employer ended my contract. SECRET-CODE-COPPER.',
        'source':'direct','meaning':'I lost my job.','importance':.8}})
    e.schedule('friend',0,'A hears about a shared difficulty.',{'a':{'text':'B described having trouble finding employment.',
        'source':'b','kind':'direct','meaning':'I heard an account about a difficult job search.','encountered':['b']}})
    e.schedule('private-b',0,'B privately receives an episode.',{'b':{'text':'VELVET-OTTER-PRIVATE bank vault secret.',
        'source':'direct','meaning':'A private matter.'}})
    e.advance(0);e.agent('a')['memory_meta']['work']['topics']=['employment'];e.agent('a')['memory_meta']['friend']['topics']=['employment','friendship']
    return e


def main():
    checks=[];health=graphiti_bridge.request('/health');assert health['ready'] and health['local_embeddings']
    e=fixture();before=deepcopy(e.state);body=graphiti_bridge.snapshot(e,'a')
    assert 'VELVET-OTTER' not in json.dumps(body) and len(body['records'])==2
    checks.append('private snapshot contains only this agent received representations')
    rows,info=graphiti_bridge.candidates(e,'a','I am unemployed after being laid off.',6)
    assert rows and any(m['event']=='work' for m in rows) and all(m['event']!='private-b' for m in rows)
    assert info['backend']=='graphiti_neo4j_local_bge_rrf' and e.state==before
    checks.append('actual Graphiti BM25 vector and BFS retrieval returns private event ids without state mutation')
    key=info['snapshot'];first=graphiti_bridge.request('/status/'+key)
    assert graphiti_bridge.request('/enqueue',body)['snapshot']==key
    assert graphiti_bridge.request('/status/'+key)['attempts']==first['attempts']
    checks.append('duplicate snapshots reuse completed deterministic ingestion without duplicate work')
    assert any(c['relation']=='TOPIC' for c in info['chains'])
    assert graphiti_bridge.snapshot(e,'b')['owner']=='b'
    _,other=graphiti_bridge.candidates(e,'b','bank vault',6);assert other['snapshot']!=key
    checks.append('graph topics and received-reference links remain namespaced by owner and immutable view')
    e.agent('a')['memory_meta']['work']['summary']='I lost my job.'
    e.agent('a')['memory_meta']['friend']['summary']='A friend described a job search.'
    e.advance(10000);body=graphiti_bridge.snapshot(e,'a')
    assert 'SECRET-CODE-COPPER' not in json.dumps(body) and all(r['representation']=='subjective_gist' for r in body['records'])
    rows,new=graphiti_bridge.candidates(e,'a','employment trouble',6)
    assert new['snapshot']!=key and all('SECRET-CODE' not in json.dumps(m) for m in rows)
    checks.append('aging changes the indexed snapshot and old graph detail cannot reappear through gist retrieval')
    with TemporaryDirectory() as directory:
        saved=Path(directory)/'world.json';before=deepcopy(e.state);e.save(saved);e.save(saved)
        assert Engine.load(saved).state==before and e.state==before
        with sqlite3.connect(graphiti_bridge.config()['outbox']) as db:
            assert db.execute('SELECT count(*) FROM jobs WHERE id=?',(new['snapshot'],)).fetchone()[0]==1
        checks.append('checkpoint publication uses a durable idempotent outbox and leaves canonical state unchanged')
        # A later checkpoint supersedes views queued only by earlier checkpoints; searched views stay queued.
        stale=['private_stale_publish','private_waiting_search']
        with sqlite3.connect(graphiti_bridge.config()['outbox']) as db:
            db.execute("INSERT INTO jobs(id,payload,status,updated,used) VALUES(?,'{}','queued',0,NULL),(?,'{}','queued',0,?)",
                       (stale[0],stale[1],1.0))
        try:
            e.save(saved)
            with sqlite3.connect(graphiti_bridge.config()['outbox']) as db:
                left={k for (k,) in db.execute('SELECT id FROM jobs WHERE id IN (?,?)',stale)}
            assert left=={'private_waiting_search'}
        finally:
            with sqlite3.connect(graphiti_bridge.config()['outbox']) as db:db.execute('DELETE FROM jobs WHERE id IN (?,?)',stale)
        checks.append('a new checkpoint drops views queued only by earlier checkpoints (stale caches) but keeps views a search is waiting on')
    before=deepcopy(e.state)
    quick=inspect(e,'a','employment','quick');panorama=inspect(e,'a','employment','panorama');assert quick['memories'] and panorama['events'] and e.state==before
    checks.append('quick and historical-interpretation researcher inspection are read-only')
    def select(system,context,api,model,max_tokens=600):
        if context.get('task')=='expand_retrieval_query':return {'queries':['employment']}
        return {'memory_ids':[context['memory_candidates'][0]['event']]}
    with patch('devsim.engine.request_json',side_effect=select):cognition.semantic_recall(e,'a','work difficulties',api='stub',model='stub')
    assert e.agent('a')['retrieval_focus']['graph_retrieval']['status']=='ready'
    assert e.agent('a')['memory_meta']['work']['last_recall_day'] is None
    checks.append('runtime semantic recall uses Graphiti but gist-only recall cannot rehearse original detail')
    with patch('devsim.graphiti_bridge.candidates',side_effect=OSError('fixture graph outage')),patch('devsim.engine.request_json',side_effect=select):
        cognition.semantic_recall(e,'a','another job difficulty',api='stub',model='stub')
    assert e.agent('a')['retrieval_focus']['graph_retrieval']['status']=='fallback_private_fts'
    checks.append('graph outage falls back only to private FTS and records the downgrade')
    with patch('devsim.graph_tools.validated_json',return_value={'queries':['job losses','friends employment']}):
        before=deepcopy(e.state);deep=inspect(e,'a','employment','deep',model='stub');assert len(deep['queries'])==3 and e.state==before
    checks.append('deep researcher search combines scoped subqueries without creating a recall event')
    # Corrupt IDs returned by an index never get content from another owner.
    response=graphiti_bridge.request
    def forged(path,data=None,timeout=10):
        r=response(path,data,timeout)
        if path=='/search':r['event_ids'].insert(0,'private-b')
        return r
    with patch('devsim.graphiti_bridge.request',side_effect=forged):rows,_=graphiti_bridge.candidates(e,'a','employment',6)
    assert all(m['event']!='private-b' for m in rows)
    checks.append('engine rechecks candidate membership even when an index returns a foreign event id')
    from urllib.error import HTTPError
    calls=[]
    def starting(path,data=None,timeout=10):
        if path=='/enqueue' and not calls:
            calls.append(path);raise HTTPError('http://127.0.0.1:18082/enqueue',503,'starting',{},None)
        return response(path,data,timeout)
    with patch('devsim.graphiti_bridge.request',side_effect=starting):rows,ready=graphiti_bridge.candidates(e,'a','employment',6)
    assert rows and ready['status']=='ready' and len(calls)==1
    checks.append('temporary startup 503 waits within the indexing deadline rather than degrading immediately')
    c=fixture();scope=c.state['config']['graphiti_namespace'];views=[];keys=[];answers=[]
    for day in (1,2,3):
        c.advance(day);views.append(deepcopy(c))
        rows,info=graphiti_bridge.candidates(c,'a','employment',6);keys.append(info['snapshot']);answers.append([r['event'] for r in rows])
    stats=graphiti_bridge.request('/stats')
    dry=graphiti_bridge.compact(1,0,True,scope)
    assert set(dry['deleted'])==set(keys[:2]) and dry['nodes']>0 and graphiti_bridge.request('/stats')==stats
    assert graphiti_bridge.compact(1,3600,False,scope)['deleted_snapshots']==0
    done=graphiti_bridge.compact(1,0,False,scope);after=graphiti_bridge.request('/stats')
    assert set(done['deleted'])==set(keys[:2]) and after['nodes']==stats['nodes']-done['nodes']
    assert after['relationships']==stats['relationships']-done['relationships']
    with sqlite3.connect(graphiti_bridge.config()['outbox']) as db:
        assert not db.execute('SELECT count(*) FROM jobs WHERE id IN (?,?)',keys[:2]).fetchone()[0]
    latest=graphiti_bridge.request('/status/'+keys[2])
    rows,info=graphiti_bridge.candidates(c,'a','employment',6)
    assert info['snapshot']==keys[2] and graphiti_bridge.request('/status/'+keys[2])['attempts']==latest['attempts']
    rows,info=graphiti_bridge.candidates(views[0],'a','employment',6)
    assert info['snapshot']==keys[0] and [r['event'] for r in rows]==answers[0]
    checks+=['compaction dry runs change nothing and recently used views are protected by their lease',
             'compaction removes superseded views from Neo4j and the outbox; the newest view stays searchable without reindexing',
             'a compacted view is re-derived from its checkpoint on demand with identical results']
    quiet=fixture();quiet_scope=quiet.state['config']['graphiti_namespace']
    quiet_keys=[]
    for day in (1,2,3):
        quiet.advance(day);graphiti_bridge.publish(quiet)
        quiet_keys+=[graphiti_bridge.snapshot_key(graphiti_bridge.snapshot(quiet,o)) for o in ('a','b')]
    import time,urllib.error
    def state(key):  # automatic compaction may already have removed a superseded view
        try:return graphiti_bridge.request('/status/'+key)['status']
        except urllib.error.HTTPError:return 'removed'
    deadline=time.monotonic()+120
    while any(state(k) not in ('done','removed') for k in quiet_keys):  # queued jobs are never compacted
        assert time.monotonic()<deadline,'published views were not indexed in time';time.sleep(.5)
    graphiti_bridge.compact(1,3600,False,quiet_scope)
    with sqlite3.connect(graphiti_bridge.config()['outbox']) as db:
        remaining={r[0] for r in db.execute('SELECT id FROM jobs WHERE id IN (%s)'%','.join('?'*len(quiet_keys)),quiet_keys)}
    assert remaining==set(quiet_keys[-2:]),remaining
    graphiti_bridge.compact(1,0,False,quiet_scope)
    checks.append('views only published by checkpoint saves carry no lease; superseded ones are compactable at once')
    busy=fixture();busy_scope=busy.state['config']['graphiti_namespace'];fakes=[]
    with sqlite3.connect(graphiti_bridge.config()['outbox']) as db:
        for day in (1,2):
            payload={**graphiti_bridge.snapshot(busy,'a'),'view_day':day};key=graphiti_bridge.snapshot_key(payload);fakes.append(key)
            db.execute("INSERT INTO jobs(id,payload,status,updated,used) VALUES(?,?,'running',0,0)",(key,graphiti_bridge.canonical(payload)))
    try:assert graphiti_bridge.compact(1,0,False,busy_scope)['deleted_snapshots']==0
    finally:
        with sqlite3.connect(graphiti_bridge.config()['outbox']) as db:db.execute('DELETE FROM jobs WHERE id IN (?,?)',fakes)
    checks.append('compaction never removes a queued or running indexing job')
    # /embed: normalized cached BGE vectors for engine meaning-based cueing.
    shout,yell,code=graphiti_bridge.vectors(['Rohan shouted at me in the cafeteria.','My father yelled at me when I was small.',
                                             'The buffer flush at the frame boundary stops the drift.'])
    cos=lambda a,b:sum(x*y for x,y in zip(a,b))
    assert abs(cos(shout,shout)-1)<1e-4 and cos(shout,yell)>.6>cos(shout,code)
    assert graphiti_bridge.request('/embed',{'texts':['Rohan shouted at me in the cafeteria.']})['vectors'][0]==shout
    for bad in ({'texts':[]},{'texts':['x']*513},{'texts':['']},{'texts':'not a list'}):
        try:graphiti_bridge.request('/embed',bad);raise AssertionError('bad embed request accepted')
        except HTTPError as exc:assert exc.code==400
    checks.append('/embed returns normalized cached BGE vectors (shouted~yelled above 0.6, unrelated below) and rejects malformed batches')
    result={'passed':True,'scope':'actual local Graphiti/Neo4j/BGE plus stubbed selection for runtime assertions; no measured human improvement',
            'health':health,'checks':checks}
    RESULTS_DIR.joinpath('graphiti-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
