from pathlib import Path
import sys,json
sys.path.insert(0,'outputs/agent_engine')
from engine import Engine,FACET_NAMES
b=Path('outputs/agent_engine/graphiti-live');b.mkdir()
e=Engine(seed=93)
for key,name in [('alex','Alex'),('bea','Bea')]:
 e.entity(key,name,{'birth_day':-25*365.25});e.materialize(key,dict.fromkeys(FACET_NAMES,50),birth_day=-25*365.25)
e.goal('alex','presentation','Prepare a short presentation.')
e.schedule('dismissal',0,'Alex receives an employment outcome.',{'alex':{'text':'My employer ended my contract. I felt embarrassed telling Bea.',
 'source':'direct','meaning':'I lost a job and worried about being judged.','importance':.8}})
e.schedule('encouragement',0,'Both receive an actual conversation.',{
 'alex':{'text':'Bea listened when I mentioned the job loss and encouraged a small next step.','source':'direct','encountered':['bea'],'meaning':'I felt supported after explaining a difficulty.'},
 'bea':{'text':'Alex told me about losing a job and I listened.','source':'direct','encountered':['alex']}})
e.schedule('bea-private',0,'Bea privately considers an unrelated event.',{'bea':{'text':'I privately made a plan involving a violet observatory.','source':'direct'}})
e.advance(1)
p={'description':'Seeded adult Graphiti wiring fixture; omitted childhood, neutral synthetic traits, one eligible offered activity and guaranteed success for outcome coverage.',
   'sampling':'event_driven','planning':{'calendar_mode':'elapsed','grounded_plans':True,'hours_per_day':8},
   'cognition':{'graphiti_retrieval':True,'indexed_retrieval':True,'semantic_recall':True,'reflection':True},
   'opportunities':[{'id':'presentation','actor':'alex','goal_id':'presentation','min_age':18,'max_age':80,'rate_per_year':365,
    'situation':'Prepare a small presentation after an employment setback; consider what prior experiences mean for seeking support.',
    'options':[{'id':'draft','label':'Draft one paragraph for the short presentation.','duration_hours':.5,'success_probability':1,
      'progress_gain':.5,'success_text':'I drafted one useful paragraph for my presentation.','failure_text':'The paragraph is still unfinished.',
      'valence_success':.2,'valence_failure':-.2}]}]}
e.save(b/'initial.json');(b/'policy.json').write_text(json.dumps(p,indent=2)+'\n')
