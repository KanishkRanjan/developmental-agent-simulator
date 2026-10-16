import json,sys
from pathlib import Path
sys.path.insert(0,str(Path('outputs/agent_engine').resolve()))
from initialize_life import initialize
from lifetime import Lifetime
base=Path('outputs/agent_engine/integrated-live-example');base.mkdir(exist_ok=True)
e=initialize(inherited=True)
for mid,day,text,meaning in [
 ('seed-school',16*365.25,'Bea gave no response when I shared a draft.','I worried silence meant my work was unwanted.'),
 ('seed-explanation',17*365.25,'Bea explained being busy that day and asked to read my next draft.','Silence may have other explanations.'),
 ('seed-recent',18*365.25,'I am preparing material and want to make time for friendships too.','Work and relationships both matter to me.')]:
 e.schedule(mid,day,'Explicit synthetic prior experience.',{'alex':{'text':text,'source':'direct','meaning':meaning,'importance':.8,'confidence':.6,'references':['bea']}})
 e.advance(day)
 e.agent('alex')['memory_meta'][mid].update(summary=meaning,topics=['work','relationships','evaluation'])
e.goal('alex','work','Prepare useful project material.',priority=.8)
e.goal('alex','friendship','Make room for friendship.',priority=.7)
e.agent('alex')['resources']={'money':20}
p={'description':'Short integrated engineering fixture at age 18. Seeded prior episodes and omitted early years; not predictive validation.',
 'sampling':'event_driven','cognition':{'semantic_recall':True,'reflection':True,'rumination_per_year':365,'semantic_candidates':12},
 'planning':{'hours_per_day':4},'background_expansion':{'alex':{'id':'education-v1','slots':{'education':['secondary-school','vocational-school']},'milestones':[]}},
 'situational_personality':{'recovery_half_life_days':1},
 'opportunities':[{'id':'competing-priorities','actor':'alex','min_age':18,'max_age':19,'rate_per_year':365,
  'situation':'Bea asks whether you want to meet, and you also have project work to do. What should you do?', 'cues':['work','social'],
  'options':[{'id':'work','label':'Spend two hours preparing project material.','goal_id':'work','duration_hours':2,
    'costs':{'money':1},'success_probability':1,'success_text':'I prepared a useful section of project material.',
    'failure_text':'My work remained unfinished.','valence_success':.3,'valence_failure':-.2,'progress_gain':.5,
    'effects_success':{'resources':{'alex':{'money':2}}}},
   {'id':'meet','label':'Spend two hours catching up with Bea.','goal_id':'friendship','duration_hours':2,'contact':'bea',
    'contact_text':'Alex and I caught up and talked about making time for each other.', 'success_probability':1,
    'success_text':'Bea and I spent time together and talked about balancing work and friendship.',
    'failure_text':'We could not find time to talk.','valence_success':.4,'valence_failure':-.1,'progress_gain':.5,
    'contact_responses':[{'id':'talk','label':'Talk with Alex about balancing friendship and work.','success_multiplier':1,
      'success_text':'Bea and I talked. Bea said that an earlier silence was due to being busy, not rejection of my work.',
      'failure_text':'Bea and I could not talk.','contact_text':'I explained to Alex that being busy had caused my earlier silence.'},
     {'id':'defer','label':'Explain that you cannot talk now and suggest another time.','success_multiplier':0,
      'success_text':'We arranged another time.','failure_text':'Bea said talking was not possible now and suggested another day.',
      'contact_text':'I told Alex I could not talk now and suggested another day.'}]}]}],
 'world_events':[{'id':'paid-task','day':e.day+.1,'description':'Alex receives payment for a completed task.',
   'observations':{'alex':{'text':'I received five units of payment for an earlier completed task.','source':'direct','importance':.5}},
   'effects':{'resources':{'alex':{'money':5}},'facts':{'alex':{'employment':'project-worker'}}}}]}
# Calculate the first scheduled decision, then retain exactly this policy/seed.
c=Lifetime(e,p); due=e.state['runtime']['next_opportunities']['competing-priorities']; until=due+.01
# First decision plus preceding world/background events, without a long benchmark.
e.save(base/'initial.json');(base/'policy.json').write_text(json.dumps(p,indent=2)+'\n')
(base/'target.json').write_text(json.dumps({'until_day':until,'first_action_day':due,'scope':p['description']},indent=2)+'\n')
print(until)
