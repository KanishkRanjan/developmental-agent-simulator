from pathlib import Path
from copy import deepcopy
import json,os,signal,subprocess,sys,time
sys.path.insert(0,'outputs/agent_engine')
from engine import Engine,FACET_NAMES
import cognition,graphiti_bridge
root=Path.cwd();pid=int((root/'work/graphiti-data/service.pid').read_text())
command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
assert str(root/'outputs/agent_engine/graphiti_service.py') in command
os.kill(pid,signal.SIGTERM);time.sleep(.5)
b=root/'outputs/agent_engine/graphiti-restart-probe-final';b.mkdir()
e=Engine(seed=322);e.entity('probe','Probe');e.materialize('probe',dict.fromkeys(FACET_NAMES,50))
cognition.configure(e,{'graphiti_retrieval':True,'indexed_retrieval':True})
e.schedule('repair',0,'A repair was received.',{'probe':{'text':'I repaired a telescope in the observatory.','source':'direct','meaning':'A successful repair.'}});e.advance(0)
before=deepcopy(e.state);e.save(b/'world.json');assert Engine.load(b/'world.json').state==before
key=graphiti_bridge.snapshot_key(graphiti_bridge.snapshot(e,'probe'))
import sqlite3
with sqlite3.connect(graphiti_bridge.config()['outbox']) as db:assert db.execute('SELECT status FROM jobs WHERE id=?',(key,)).fetchone()[0]=='queued'
subprocess.run(['work/profile-env/bin/python','outputs/agent_engine/graphiti-local/start.py'],check=True)
rows,info=graphiti_bridge.candidates(Engine.load(b/'world.json'),'probe','fixing astronomical equipment',4)
assert [r['event'] for r in rows]==['repair'] and info['status']=='ready'
status=graphiti_bridge.request('/status/'+key);assert status['status']=='done'
result={'passed':True,'checkpoint_preserved':True,'queued_while_service_stopped':True,'queued_snapshot_recovered_after_restart':True,
        'status':status,'backend':info['backend'],'scope':'durable background indexing across an intentional idle service stop/start, not a mid-write crash injection'}
(b/'integrity-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
