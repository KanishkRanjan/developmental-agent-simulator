"""SQLite checkpoint plus normalized provenance graph for controller audits.

This is local storage, not a multi-user authorization boundary. Graph audit
queries expose archived originals and are never the agent's retrieval API.
"""
import json
from pathlib import Path
import sqlite3
import tempfile


def save(path,state):
    path=Path(path)
    payload=json.dumps(state,allow_nan=False)
    handle=tempfile.NamedTemporaryFile(dir=path.parent,suffix='.sqlite.tmp',delete=False);temporary=Path(handle.name);handle.close()
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript('''CREATE TABLE checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                CREATE TABLE nodes(id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE edges(source TEXT NOT NULL, target TEXT NOT NULL, owner TEXT NOT NULL, kind TEXT NOT NULL);
                CREATE INDEX node_owner_kind ON nodes(owner,kind); CREATE INDEX edge_owner_source ON edges(owner,source);
                PRAGMA user_version=1;''')
            db.execute('INSERT INTO checkpoint VALUES(1,?)',(payload,))
            def node(key,owner,kind,data):
                db.execute('INSERT OR REPLACE INTO nodes VALUES(?,?,?,?)',(key,owner,kind,json.dumps(data,allow_nan=False)))
            def edge(source,target,owner,kind): db.execute('INSERT INTO edges VALUES(?,?,?,?)',(source,target,owner,kind))
            for key,entity in state['entities'].items(): node('person:'+key,'','person',{'id':key,'name':entity['name']})
            for owner,agent in state['agents'].items():
                for mid,meta in agent['memory_meta'].items():
                    key=f'episode:{owner}:{mid}'
                    event=next(e for e in state['events'] if e['id']==mid)
                    node(key,owner,'episode',{'event':mid,'day':event['day'],'observation':event['observations'][owner],'cognition':meta})
                    edge('person:'+owner,key,owner,'received')
                for other,relation in agent['relationships'].items():
                    key=f'relation:{owner}:{other}';node(key,owner,'relationship',relation)
                    edge('person:'+owner,key,owner,'has_relationship');edge(key,'person:'+other,owner,'target')
                for key,belief in agent['beliefs'].items():
                    bid=f'belief:{owner}:{key}';node(bid,owner,'belief',belief)
                    for mid in belief['evidence']: edge(bid,f'episode:{owner}:{mid}',owner,'evidence')
                for rid,reference in agent.get('unresolved_references',{}).items():
                    key=f'reference:{owner}:{rid}';node(key,owner,'reference',reference)
                    for mid in reference['evidence']: edge(key,f'episode:{owner}:{mid}',owner,'heard_in')
            db.commit()
        temporary.replace(path)
    finally:
        if temporary.exists(): temporary.unlink()


def load(path):
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA user_version').fetchone()[0]!=1: raise ValueError('Unsupported graph checkpoint version')
        return json.loads(db.execute('SELECT payload FROM checkpoint WHERE id=1').fetchone()[0])


def audit_private_graph(path,owner):
    """Owner-scoped controller audit. Does not grant agent access to originals."""
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as db:
        nodes=[{'id':key,'kind':kind,'data':json.loads(data)} for key,kind,data in db.execute('SELECT id,kind,payload FROM nodes WHERE owner=? ORDER BY id',(owner,))]
        edges=[{'source':s,'target':t,'kind':kind} for s,t,kind in db.execute('SELECT source,target,kind FROM edges WHERE owner=? ORDER BY source,target,kind',(owner,))]
    return {'owner':owner,'nodes':nodes,'edges':edges,'scope':'controller forensic audit; not agent recall'}
