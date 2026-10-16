"""One-command launch of the complete accepted-mechanism research scaffold."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from hashlib import sha256

from full_scenario import build
from engine import Engine
from lifetime import Lifetime


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--years',type=float,default=22)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--caregivers',type=int,choices=(1,2),default=1)
    parser.add_argument('--scripted',action='store_true')
    parser.add_argument('--household',action='store_true',help='Enable explicit rooms, waking windows and scheduled multi-turn family conversations')
    parser.add_argument('--no-graphiti',action='store_true',help='Use the earlier private FTS retrieval without the local graph service')
    parser.add_argument('--api',default='http://127.0.0.1:18081')
    args=parser.parse_args()
    if not 0<args.years<=120: parser.error('--years must be positive and at most 120')
    if args.out.exists() and any(args.out.iterdir()):parser.error('Use a fresh output directory')
    args.out.mkdir(parents=True,exist_ok=True)
    sources=list(Path(__file__).parent.glob('*.py'))
    (args.out/'source-hashes.json').write_text(json.dumps({str(p.resolve()):sha256(p.read_bytes()).hexdigest() for p in sources},indent=2)+'\n')
    graphiti=not args.scripted and not args.no_graphiti
    if graphiti:
        subprocess.run([sys.executable,str(Path(__file__).parent/'graphiti-local/start.py')],check=True)
    engine,policy=build(args.seed,args.caregivers,graphiti=graphiti,household=args.household)
    engine.save(args.out/'initial.json');(args.out/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    (args.out/'launch.json').write_text(json.dumps({'years':args.years,'seed':args.seed,'caregivers':args.caregivers,
        'provider':'scripted_engineering_fixture' if args.scripted else 'local_27b_api','graphiti_enabled':graphiti,
        'household_enabled':args.household},indent=2)+'\n')
    if args.scripted:
        Lifetime(engine,policy,scripted=True).run(args.years*365.25,args.out/'world.json')
        engine.save(args.out/'world.sqlite')
        result={'status':'completed','provider':'scripted_engineering_fixture','final_day':engine.day,
            'actions_by_status':{status:sum(a['status']==status for a in engine.state['actions']) for status in ('resolved','intended','cancelled')},
            'agents':len(engine.state['agents']),'scope':'software integration only; model-only paths skipped'}
        (args.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    else:
        subprocess.run([sys.executable,str(Path(__file__).with_name('run_live.py')),'--world',str(args.out/'initial.json'),
            '--policy',str(args.out/'policy.json'),'--until-day',str(args.years*365.25),'--out',str(args.out/'run'),
            '--api',args.api],check=True)
        Engine.load(args.out/'run/world.json').save(args.out/'run/world.sqlite')


if __name__=='__main__':main()
