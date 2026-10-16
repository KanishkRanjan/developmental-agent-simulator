from pathlib import Path
import json,sys
sys.path.insert(0,'outputs/agent_engine')
from engine import Engine
b=Path('outputs/agent_engine/goal-plans-success-live');b.mkdir()
e=Engine.load('outputs/agent_engine/goal-plans-live/initial.json')
e.agent('maya')['goals']={};e.goal('maya','draft-review','Draft and then review one short paragraph.')
e.entity('maya','Maya',{'paragraph_drafted':False})
options=[]
for key,label,required,progress,text in [('draft','Draft one short paragraph.',False,.5,'I drafted a short paragraph.'),('review','Review the drafted paragraph.',True,.5,'I reviewed the paragraph I previously drafted.')]:
 o={'id':key,'label':label,'duration_hours':.5,'success_probability':1,'progress_gain':progress,
    'success_text':text,'failure_text':'The step remains unfinished.','valence_success':.2,'valence_failure':-.1,
    'requires':{'facts':{'maya':{'paragraph_drafted':required}}}}
 if key=='draft':o['effects_success']={'facts':{'maya':{'paragraph_drafted':True}}}
 options.append(o)
p={'description':'Controlled engineering fixture: one eligible action per stage, successful outcomes guaranteed to exercise step completion; no personality-choice or realism claim.',
   'sampling':'event_driven','planning':{'calendar_mode':'elapsed','grounded_plans':True,'hours_per_day':8},
   'cognition':{'reflection':True,'semantic_recall':True,'indexed_retrieval':True},
   'expression':{'age_appropriate_actions':True},
   'opportunities':[{'id':'paragraph','actor':'maya','goal_id':'draft-review','min_age':18,'max_age':100,'rate_per_year':365,
   'situation':'Take the next available step toward drafting and reviewing a short paragraph.','options':options}]}
e.save(b/'initial.json');(b/'policy.json').write_text(json.dumps(p,indent=2)+'\n')
