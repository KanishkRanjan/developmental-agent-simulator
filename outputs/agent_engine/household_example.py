"""Fresh bounded family-dialogue fixture, using the existing local 27B API."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from engine import Engine,FACET_NAMES
from lifetime import Lifetime


def build(graphiti=False):
    e=Engine(seed=184)
    for owner,name,age in [('alex','Alex',16),('maya','Maya',41),('bea','Bea',14),('noor','Noor',43)]:
        e.entity(owner,name,{'birth_day':-age*365.25})
        traits=dict.fromkeys(FACET_NAMES,50)
        traits.update({'E3':35,'N1':65} if owner=='alex' else {'A3':75,'C3':65} if owner=='maya' else {})
        e.materialize(owner,traits,birth_day=-age*365.25)
    e.caregiver('alex','maya');e.caregiver('bea','maya')
    e.schedule('alex-early',0,'Alex has a seeded private experience.',{'alex':{'text':'I struggled with a school project and feel hesitant to ask for help.',
        'source':'self','kind':'internal','importance':.8,'valence':-.3}})
    e.schedule('noor-private',0,'Noor has an unrelated private thought.',{'noor':{'text':'PRIVATE_VIOLET_OBSERVATORY: I am thinking about a telescope.',
        'source':'self','kind':'internal','importance':.7}})
    e.advance(0)
    p={'description':'Synthetic short household wiring fixture; childhood was not simulated.',
        'sampling':'event_driven','opportunities':[],
        'planning':{'calendar_mode':'elapsed','hours_per_day':8},
        'expression':{'age_appropriate_actions':True},
        'cognition':{'semantic_recall':True,'graphiti_retrieval':graphiti,'indexed_retrieval':True},
        'household':{'rooms':{'living':{'label':'the household living room'},'bedroom':{'label':'a closed bedroom'}},
            'locations':{'alex':'living','maya':'living','bea':'living','noor':'bedroom'},
            'routines':{p:{'available_hours':[[7,22]],'response_minutes':[.5,1.5]} for p in e.state['agents']},
            'conversations':[{'id':'homework','day':.75,'room':'living','participants':['alex','maya'],
                'topic':'Discuss how school projects are going and what support would be useful. Each person can express their own needs.',
                'max_turns':4,'exit_room':'bedroom'}]}}
    return e,p


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--scripted',action='store_true')
    parser.add_argument('--graphiti',action='store_true')
    parser.add_argument('--api',default='http://127.0.0.1:18081')
    args=parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()): parser.error('Use a fresh output directory')
    args.out.mkdir(parents=True,exist_ok=True)
    if args.graphiti:
        subprocess.run([sys.executable,str(Path(__file__).parent/'graphiti-local/start.py')],check=True)
    e,p=build(args.graphiti)
    e.save(args.out/'initial.json');(args.out/'policy.json').write_text(json.dumps(p,indent=2)+'\n')
    if args.scripted:
        Lifetime(e,p,scripted=True).run(.8,args.out/'world.json')
        e.save(args.out/'world.sqlite')
    else:
        subprocess.run([sys.executable,str(Path(__file__).with_name('run_live.py')),'--world',str(args.out/'initial.json'),
            '--policy',str(args.out/'policy.json'),'--until-day','.8','--out',str(args.out/'run'),'--api',args.api],check=True)
        e=Engine.load(args.out/'run/world.json');e.save(args.out/'run/world.sqlite')
    print(json.dumps(e.state['runtime']['conversations'],indent=2))


if __name__=='__main__':main()
