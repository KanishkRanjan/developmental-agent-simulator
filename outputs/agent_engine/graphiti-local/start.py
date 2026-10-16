"""Start this project's subscription-free graph index; --setup installs pins."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.request import Request,urlopen


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--setup',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parents[3];folder=root/'work/graphiti-data';folder.mkdir(parents=True,exist_ok=True)
    python=root/'work/graphiti-env/bin/python';source=root/'outputs/agent_engine'
    if args.setup:
        subprocess.run(['uv','venv','--python','3.12',str(python.parent.parent)],check=True)
        subprocess.run(['uv','pip','install','--python',str(python),'-r',str(Path(__file__).with_name('requirements.lock.txt'))],check=True)
        command="from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-small-en-v1.5',revision='5c38ec7c405ec4b44b94cc5a9bb96e735b38267a',local_dir="+repr(str(folder/'embedding-model'))+",allow_patterns=['*.json','*.txt','*.safetensors','1_Pooling/*'])"
        subprocess.run([str(python),'-c',command],check=True)
    if not python.exists():raise SystemExit('Run with --setup first')
    path=folder/'service.json'
    if not path.exists():
        with urlopen('http://127.0.0.1:18081/v1/models',timeout=8) as response:models=json.load(response)
        matching=[m['id'] for m in models['data'] if 'hauhaucs' in m['id'].lower() and 26e9<=m.get('meta',{}).get('n_params',0)<=29e9]
        if len(matching)!=1:raise SystemExit('Expected the authorized local HauhauCS 27B model')
        config={'port':18082,'token':secrets.token_urlsafe(32),'neo4j_uri':'bolt://127.0.0.1:17687',
                'embedding_path':str(folder/'embedding-model'),'outbox':str(folder/'outbox.sqlite'),
                'llm_url':'http://127.0.0.1:18081','llm_model':matching[0]}
        path.write_text(json.dumps(config,indent=2)+'\n');path.chmod(0o600)
    config=json.loads(path.read_text())
    def ready():
        try:
            with urlopen(Request('http://127.0.0.1:'+str(config['port'])+'/health',headers={'Authorization':'Bearer '+config['token']}),timeout=1) as response:return json.load(response).get('ready',False)
        except OSError:return False
    if ready():print('Local Graphiti index is ready on loopback port',config['port']);return
    subprocess.run(['docker','compose','-p','developmental-graphiti','-f',str(Path(__file__).with_name('compose.yaml')),'up','-d'],check=True)
    # Detached local service; logs/config/queue stay in work/, checkpoints stay in outputs/.
    with (folder/'service.log').open('a') as log:
        child=subprocess.Popen([str(python),str(source/'graphiti_service.py'),'--config',str(path)],cwd=root,
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    (folder/'service.pid').write_text(str(child.pid)+'\n')
    for _ in range(45):
        if ready():print('Local Graphiti index ready on loopback port',config['port']);return
        if child.poll() is not None:raise SystemExit('Graph service failed; inspect work/graphiti-data/service.log')
        time.sleep(1)
    raise SystemExit('Graph service is still starting; inspect work/graphiti-data/service.log before retrying')


if __name__=='__main__':main()
