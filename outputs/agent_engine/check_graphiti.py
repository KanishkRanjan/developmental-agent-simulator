"""Live local Graphiti integration checks, not measured psychological accuracy."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest.mock import patch
from engine import Engine,FACET_NAMES
import cognition,graphiti_bridge
from graph_tools import inspect


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
    before=deepcopy(e.state)
    quick=inspect(e,'a','employment','quick');panorama=inspect(e,'a','employment','panorama');assert quick['memories'] and panorama['events'] and e.state==before
    checks.append('quick and historical-interpretation researcher inspection are read-only')
    def select(system,context,api,model,max_tokens=600):
        if context.get('task')=='expand_retrieval_query':return {'queries':['employment']}
        return {'memory_ids':[context['memory_candidates'][0]['event']]}
    with patch('engine.request_json',side_effect=select):cognition.semantic_recall(e,'a','work difficulties',api='stub',model='stub')
    assert e.agent('a')['retrieval_focus']['graph_retrieval']['status']=='ready'
    assert e.agent('a')['memory_meta']['work']['last_recall_day'] is None
    checks.append('runtime semantic recall uses Graphiti but gist-only recall cannot rehearse original detail')
    with patch('graphiti_bridge.candidates',side_effect=OSError('fixture graph outage')),patch('engine.request_json',side_effect=select):
        cognition.semantic_recall(e,'a','another job difficulty',api='stub',model='stub')
    assert e.agent('a')['retrieval_focus']['graph_retrieval']['status']=='fallback_private_fts'
    checks.append('graph outage falls back only to private FTS and records the downgrade')
    with patch('graph_tools.validated_json',return_value={'queries':['job losses','friends employment']}):
        before=deepcopy(e.state);deep=inspect(e,'a','employment','deep',model='stub');assert len(deep['queries'])==3 and e.state==before
    checks.append('deep researcher search combines scoped subqueries without creating a recall event')
    # Corrupt IDs returned by an index never get content from another owner.
    response=graphiti_bridge.request
    def forged(path,data=None,timeout=10):
        r=response(path,data,timeout)
        if path=='/search':r['event_ids'].insert(0,'private-b')
        return r
    with patch('graphiti_bridge.request',side_effect=forged):rows,_=graphiti_bridge.candidates(e,'a','employment',6)
    assert all(m['event']!='private-b' for m in rows)
    checks.append('engine rechecks candidate membership even when an index returns a foreign event id')
    from urllib.error import HTTPError
    calls=[]
    def starting(path,data=None,timeout=10):
        if path=='/enqueue' and not calls:
            calls.append(path);raise HTTPError('http://127.0.0.1:18082/enqueue',503,'starting',{},None)
        return response(path,data,timeout)
    with patch('graphiti_bridge.request',side_effect=starting):rows,ready=graphiti_bridge.candidates(e,'a','employment',6)
    assert rows and ready['status']=='ready' and len(calls)==1
    checks.append('temporary startup 503 waits within the indexing deadline rather than degrading immediately')
    result={'passed':True,'scope':'actual local Graphiti/Neo4j/BGE plus stubbed selection for runtime assertions; no measured human improvement',
            'health':health,'checks':checks}
    Path(__file__).with_name('graphiti-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
