"""Loopback-only Graphiti index with durable, idempotent background snapshots.

Run with graphiti-local/start.py. Canonical simulation truth stays in Engine;
these are immutable private *view* caches, not omniscient extracted facts.
"""
import argparse
import asyncio
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from uuid import uuid5,NAMESPACE_URL

os.environ['GRAPHITI_TELEMETRY_ENABLED']='false'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['EMBEDDING_DIM']='384'
os.environ['TOKENIZERS_PARALLELISM']='false'

from graphiti_core import Graphiti
from graphiti_core.nodes import EntityNode,EpisodicNode,EpisodeType
from graphiti_core.edges import EntityEdge,EpisodicEdge
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.search.search_config import SearchConfig,EdgeSearchConfig,EdgeSearchMethod,EdgeReranker


def stable(*parts):return str(uuid5(NAMESPACE_URL,json.dumps(parts,ensure_ascii=False)))
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def group(payload):return 'private_'+sha256(canonical(payload).encode()).hexdigest()
def stamp(day):return datetime(2000,1,1,tzinfo=timezone.utc)+timedelta(days=day)


class LocalEmbeddings(EmbedderClient):
    def __init__(self,folder,store):
        from sentence_transformers import SentenceTransformer
        self.model=SentenceTransformer(str(folder),device='cpu',local_files_only=True,trust_remote_code=False)
        self.store=store
    async def create(self,input_data):
        text=input_data if isinstance(input_data,str) else input_data[0]
        key=sha256(text.encode()).hexdigest()
        with sqlite3.connect(self.store) as db:
            row=db.execute('SELECT vector FROM embeddings WHERE id=?',(key,)).fetchone()
        if row:return json.loads(row[0])
        vector=self.model.encode(text,normalize_embeddings=True).tolist()
        with sqlite3.connect(self.store) as db:db.execute('INSERT OR IGNORE INTO embeddings VALUES(?,?)',(key,canonical(vector)))
        return vector


class NoExternalReranker(CrossEncoderClient):
    async def rank(self,query,passages):
        raise RuntimeError('External reranking disabled: use Graphiti RRF and the engine local-model selector')


class Index:
    def __init__(self,config):
        self.config=config;self.store=Path(config['outbox']);self.store.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.store) as db:
            db.executescript('''PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,payload TEXT NOT NULL,status TEXT NOT NULL,error TEXT,attempts INTEGER NOT NULL DEFAULT 0,updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS embeddings(id TEXT PRIMARY KEY,vector TEXT NOT NULL);''')
            db.execute("UPDATE jobs SET status='queued' WHERE status='running'")
        self.embedder=LocalEmbeddings(config['embedding_path'],self.store)
        llm=OpenAIGenericClient(config=LLMConfig(api_key='local-only',base_url=config['llm_url']+'/v1',model=config['llm_model'],small_model=config['llm_model']))
        self.graph=Graphiti(config['neo4j_uri'],'neo4j','unused',embedder=self.embedder,llm_client=llm,cross_encoder=NoExternalReranker(),max_coroutines=2)
        self.lock=asyncio.Lock();self.ready=False
    async def initialize(self):
        from neo4j.exceptions import ServiceUnavailable,SessionExpired
        for attempt in range(30):
            try:
                await self.graph.build_indices_and_constraints();self.ready=True;return
            except (ServiceUnavailable,SessionExpired):
                if attempt==29:raise
                await asyncio.sleep(1)
    def enqueue(self,payload):
        if not isinstance(payload,dict) or set(payload)!={'scope','owner','view_day','records'}:raise ValueError('Expected private snapshot scope, owner, records')
        if not isinstance(payload['scope'],str) or not 1<=len(payload['scope'])<=200 or not isinstance(payload['owner'],str) or not payload['owner']:raise ValueError('Invalid private scope')
        if isinstance(payload['view_day'],bool) or not isinstance(payload['view_day'],(int,float)) or not -700000<=payload['view_day']<=2000000:raise ValueError('Invalid simulated view date')
        if not isinstance(payload['records'],list) or len(payload['records'])>20000:raise ValueError('Snapshot too large')
        seen=set()
        for r in payload['records']:
            if not isinstance(r,dict) or set(r)!={'event','day','text','meaning','source','kind','topics','representation','reference_ids'}:raise ValueError('Invalid representation schema')
            if not isinstance(r['event'],str) or r['event'] in seen:raise ValueError('Duplicate or invalid private event')
            seen.add(r['event'])
            if any(not isinstance(r[k],str) or len(r[k])>32000 for k in ['text','meaning','source','kind','representation']):raise ValueError('Invalid representation text')
            if r['representation'] not in ('episodic_detail','subjective_gist'):raise ValueError('Invalid memory access form')
            if any(not isinstance(r[k],list) or len(r[k])>64 or not all(isinstance(v,str) and len(v)<=200 for v in r[k]) for k in ['topics','reference_ids']):raise ValueError('Invalid links')
            if isinstance(r['day'],bool) or not isinstance(r['day'],(float,int)) or not -700000<=r['day']<=2000000:raise ValueError('Unrepresentable simulated date')
        key=group(payload)
        with sqlite3.connect(self.store) as db:
            db.execute("INSERT OR IGNORE INTO jobs(id,payload,status,updated) VALUES(?,?,'queued',?)",(key,canonical(payload),time.time()))
            db.execute("UPDATE jobs SET status='queued',error=NULL,updated=? WHERE id=? AND status='failed'",(time.time(),key))
        return key
    def status(self,key):
        with sqlite3.connect(self.store) as db:row=db.execute('SELECT status,error,attempts FROM jobs WHERE id=?',(key,)).fetchone()
        if not row:raise ValueError('Unknown snapshot')
        return {'status':row[0],'error':row[1],'attempts':row[2]}
    async def worker(self):
        while True:
            with sqlite3.connect(self.store) as db:
                row=db.execute("SELECT id,payload FROM jobs WHERE status='queued' ORDER BY updated LIMIT 1").fetchone()
                if row:db.execute("UPDATE jobs SET status='running',attempts=attempts+1,updated=? WHERE id=?",(time.time(),row[0]))
            if not row:await asyncio.sleep(.1);continue
            try:
                async with self.lock:await self.ingest(row[0],json.loads(row[1]))
                status,error='done',None
            except Exception as exc:status,error='failed',f'{type(exc).__name__}: {exc}'[:1000]
            with sqlite3.connect(self.store) as db:db.execute('UPDATE jobs SET status=?,error=?,updated=? WHERE id=?',(status,error,time.time(),row[0]))
    async def ingest(self,key,payload):
        driver=self.graph.driver;owner=payload['owner'];root=stable(key,'owner',owner)
        async def save_node(node):
            if node.name_embedding is None:node.name_embedding=await self.embedder.create(node.name)
            await node.save(driver)
        await save_node(EntityNode(uuid=root,group_id=key,name='Self '+owner,summary='Private perspective, not global truth.'))
        for r in payload['records']:
            episode_id=stable(key,'episode',r['event']);node_id=stable(key,'memory',r['event'])
            text=r['text']+'\nSubjective meaning: '+r['meaning']
            meta={'event_id':r['event'],'owner':owner,'simulated_day':r['day'],'view_simulated_day':payload['view_day'],'representation':r['representation'],'kind':r['kind'],'source':r['source']}
            node=EntityNode(uuid=node_id,group_id=key,name='Memory '+r['event'],summary=text,attributes=meta)
            node.name_embedding=await self.embedder.create(text);await node.save(driver)
            episode=EpisodicNode(uuid=episode_id,group_id=key,name=r['event'],source=EpisodeType.json,
                source_description='Agent-available subjective view; not world truth',content=canonical(r),valid_at=stamp(payload['view_day']))
            await episode.save(driver)
            await EpisodicEdge(uuid=stable(key,'mention',r['event']),created_at=datetime.now(timezone.utc),group_id=key,source_node_uuid=episode_id,target_node_uuid=node_id).save(driver)
            links=[(root,node_id,'RECEIVED_ACCOUNT',text)]
            for kind,values in [('TOPIC',r['topics']),('KNOWN_REFERENCE',r['reference_ids'])]:
                for value in sorted(set(values)):
                    target=stable(key,kind,value)
                    await save_node(EntityNode(uuid=target,group_id=key,name=value,summary='Private '+kind.lower()))
                    links.append((node_id,target,kind,'This private memory concerns '+value+'. '+text))
            for index,(source,target,kind,fact) in enumerate(links):
                edge=EntityEdge(uuid=stable(key,'edge',r['event'],index),created_at=datetime.now(timezone.utc),group_id=key,source_node_uuid=source,target_node_uuid=target,
                    name=kind,fact=fact,episodes=[episode_id],valid_at=stamp(payload['view_day']),reference_time=stamp(payload['view_day']),attributes=meta)
                edge.fact_embedding=await self.embedder.create(fact);await edge.save(driver)
        # Wait for refresh, so a completed ingestion barrier means searchable.
        await driver.execute_query('CALL db.index.fulltext.awaitEventuallyConsistentIndexRefresh()')
    async def search(self,key,query,limit):
        if self.status(key)['status']!='done':raise ValueError('Snapshot indexing is not complete')
        if not isinstance(query,str) or len(query)>4000 or not query.strip():raise ValueError('Invalid graph query')
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=64:raise ValueError('Invalid graph limit')
        config=SearchConfig(edge_config=EdgeSearchConfig(search_methods=[EdgeSearchMethod.bm25,EdgeSearchMethod.cosine_similarity,EdgeSearchMethod.bfs],reranker=EdgeReranker.rrf,bfs_max_depth=2),limit=limit*3)
        async with self.lock:
            results=await self.graph.search_(query,config=config,group_ids=[key])
        events=[];chains=[]
        for edge in results.edges:
            if edge.group_id!=key:raise RuntimeError('Graph namespace mismatch')
            mid=edge.attributes.get('event_id')
            if mid and mid not in events:events.append(mid)
            chains.append({'event':mid,'relation':edge.name,'source':edge.source_node_uuid,'target':edge.target_node_uuid})
        return {'event_ids':events[:limit],'chains':chains[:limit*3],'backend':'graphiti_neo4j_local_bge_rrf','snapshot':key}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True);args=parser.parse_args()
    config=json.loads(args.config.read_text());index=Index(config);loop=asyncio.new_event_loop()
    def serve_loop():
        asyncio.set_event_loop(loop);loop.run_until_complete(index.initialize());loop.create_task(index.worker());loop.run_forever()
    thread=threading.Thread(target=serve_loop,daemon=True);thread.start()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            self.handle_request('GET')
        def do_POST(self):
            self.handle_request('POST')
        def handle_request(self,method):
            code=200
            try:
                if not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+config['token']):
                    self.reply(403,{'error':'Local service token required'});return
                if not index.ready: self.reply(503,{'error':'Graph index starting'});return
                if method=='GET' and self.path=='/health':result={'ready':True,'backend':'Graphiti 0.31.1 / Neo4j','local_embeddings':True}
                elif method=='GET' and self.path.startswith('/status/'):result=index.status(self.path.rsplit('/',1)[-1])
                elif method=='POST':
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=4_000_000:raise ValueError('Invalid request size')
                    body=json.loads(self.rfile.read(length))
                    if self.path=='/enqueue':result={'snapshot':index.enqueue(body)}
                    elif self.path=='/search':result=asyncio.run_coroutine_threadsafe(index.search(body['snapshot'],body['query'],body.get('limit',24)),loop).result(timeout=60)
                    else:raise ValueError('Unknown endpoint')
                else:raise ValueError('Unknown endpoint')
            except Exception as exc:code=400;result={'error':f'{type(exc).__name__}: {exc}'[:1200]}
            self.reply(code,result)
        def reply(self,code,result):
            body=json.dumps(result,allow_nan=False).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',config['port']),Handler)
    print('Local Graphiti bridge listening on loopback port',config['port'],flush=True)
    try:server.serve_forever()
    finally:server.server_close()


if __name__=='__main__':main()
