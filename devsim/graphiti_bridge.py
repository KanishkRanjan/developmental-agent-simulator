"""Standard-library engine client for a private local Graphiti view index."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from . import LOCAL_STATE_DIR


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def snapshot_key(payload):return 'private_'+sha256(canonical(payload).encode()).hexdigest()
def config():
    path=Path(os.environ.get('AGENT_GRAPHITI_CONFIG',str(LOCAL_STATE_DIR/'graphiti-data/service.json')))
    value=json.loads(path.read_text())
    if not isinstance(value.get('port'),int) or not 1024<=value['port']<=65535:raise ValueError('Invalid local Graphiti port')
    return value


def request(path,data=None,timeout=10):
    c=config();body=None if data is None else canonical(data).encode()
    with urlopen(Request(f'http://127.0.0.1:{c["port"]}'+path,data=body,
        headers={'Content-Type':'application/json','Authorization':'Bearer '+c['token']}),timeout=timeout) as response:
        return json.load(response)


_VECTORS={}
def vectors(texts):
    """Normalized BGE vectors from the local service, cached in-process by text (texts clipped to 4000 characters).

    shortcut: the cache grows with distinct memory texts and is never evicted; bound it if runs reach 1e5+ texts.
    """
    texts=[t[:4000] for t in texts]
    missing=[t for t in dict.fromkeys(texts) if t not in _VECTORS]
    for i in range(0,len(missing),512):
        chunk=missing[i:i+512]
        found=request('/embed',{'texts':chunk},timeout=120)['vectors']
        if len(found)!=len(chunk):raise ValueError('Embedding service returned the wrong number of vectors')
        _VECTORS.update(zip(chunk,found))
    return [_VECTORS[t] for t in texts]


def snapshot(engine,owner):
    from .cognition import views
    agent=engine.agent(owner)
    scope=engine.state['config'].get('graphiti_namespace')
    if not scope:raise ValueError('Graphiti namespace must be assigned at policy initialization')
    available=views(engine,owner,'',len(agent['memory_meta']))
    records=[]
    for m in available:
        records.append({k:m[k] for k in ['event','day','text','meaning','source','kind','topics','representation']})
        # Lost detail cannot leave hidden participant links in the active view.
        meta=agent['memory_meta'][m['event']]  # a sleep gist keeps its participant links
        records[-1]['reference_ids']=sorted(meta.get('encountered',[])) if m['original_detail_available'] or meta.get('tier')=='gist' else []
    return {'scope':scope,'owner':owner,'view_day':engine.day,'records':sorted(records,key=lambda r:r['event'])}


def publish(engine):
    """Durable local outbox only; saving a checkpoint never waits on a server.

    ponytail: immutable view graphs trade storage for simple rollback isolation;
    long live runs need explicit cache compaction. Embeddings are reused.
    Different rollback/branch/view contents yield different immutable graph
    namespaces. A partially indexed speculative view cannot contaminate a later
    saved view. Old graph views are caches, not historical simulation truth.
    """
    if not engine.state['config'].get('cognition',{}).get('graphiti_retrieval'):return
    c=config();store=Path(c['outbox']);store.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(store,timeout=10) as db:
        db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,payload TEXT NOT NULL,status TEXT NOT NULL,error TEXT,attempts INTEGER NOT NULL DEFAULT 0,updated REAL NOT NULL,used REAL)')
        if 'used' in [c[1] for c in db.execute('PRAGMA table_info(jobs)')]:
            # A newer checkpoint supersedes views queued only by earlier checkpoints (never searched): they are caches,
            # re-derived on demand. Without this, one save per event queued ~7 jobs per event and the queue never drained.
            db.execute("DELETE FROM jobs WHERE status='queued' AND used IS NULL")
        for owner,agent in engine.state['agents'].items():
            if not agent['alive'] or not agent['memory_meta']:continue
            payload=snapshot(engine,owner)
            db.execute("INSERT OR IGNORE INTO jobs(id,payload,status,updated) VALUES(?,?,'queued',?)",(snapshot_key(payload),canonical(payload),time.time()))


def candidates(engine,owner,query,limit=24,wait_seconds=45):
    from .cognition import views
    # Namespace and candidate text always come from this engine/owner, never a
    # model-provided group id or a graph-generated narrative.
    payload=snapshot(engine,owner)
    if not payload['records']:return [],{'backend':'graphiti','status':'empty_private_view'}
    end=time.monotonic()+wait_seconds
    while True:
        try:
            key=request('/enqueue',payload)['snapshot'];break
        except HTTPError as exc:
            if exc.code!=503 or time.monotonic()>=end:raise
            time.sleep(.2)
    if key!=snapshot_key(payload):raise RuntimeError('Graph index returned the wrong snapshot')
    while True:
        status=request('/status/'+key)
        if status['status']=='done':break
        if status['status']=='failed':raise RuntimeError('Graph indexing failed: '+str(status['error']))
        if time.monotonic()>=end:raise TimeoutError('Private Graphiti snapshot indexing is not complete')
        time.sleep(.1)
    result=request('/search',{'snapshot':key,'query':query,'limit':limit},timeout=60)
    if result['snapshot']!=key:raise RuntimeError('Graph search crossed snapshot boundary')
    current={m['event']:m for m in views(engine,owner,'',len(engine.agent(owner)['memory_meta']))}
    ids=list(dict.fromkeys(mid for mid in result['event_ids'] if mid in current))[:limit]
    return [current[mid] for mid in ids],{'backend':result['backend'],'status':'ready','snapshot':key,'chains':result['chains']}


def compact(keep_per_owner=2,lease_seconds=3600,dry_run=False,scope=None):
    """Ask the local service to delete superseded private view caches (see graphiti_service.Index.compact)."""
    return request('/compact',{'keep_per_owner':keep_per_owner,'lease_seconds':lease_seconds,'dry_run':dry_run,'scope':scope},timeout=600)


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Inspect or compact the local Graphiti view cache.')
    parser.add_argument('command',choices=['stats','compact'])
    parser.add_argument('--keep-per-owner',type=int,default=2)
    parser.add_argument('--lease-seconds',type=float,default=3600)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--scope',help='Only this simulation namespace (a checkpoint\'s config.graphiti_namespace)')
    args=parser.parse_args()
    result=request('/stats') if args.command=='stats' else compact(args.keep_per_owner,args.lease_seconds,args.dry_run,args.scope)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
