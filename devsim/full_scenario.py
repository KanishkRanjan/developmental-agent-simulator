"""Runnable lifespan policy covering the accepted engine layers.

All rates and outcomes below are illustrative scenario choices. No instrument
mapping, clinical mechanism, child norm or measured effect is invented.
"""
from copy import deepcopy
from math import floor
from .engine import Engine


def opportunities(actor,caregiver,peer):
    def care_rule(key,min_age,max_age,situation,request):
        return {'id':key,'actor':actor,'min_age':min_age,'max_age':max_age,'rate_per_year':2,
            'situation':situation,'cues':['family','challenge'],'options':[
            {'id':'seek-support','label':request,'contact':caregiver,'duration_hours':.25,
             'success_probability':.85,'valence_success':.3,'valence_failure':-.2,'importance':.7,
             'success_text':'I received responsive attention and comfort.','failure_text':'My need remained unresolved.',
             'contact_text':'I responded to a need for attention.','caregiving':{'responsiveness':.8,'acceptance':.8},
             'contact_responses':[
                {'id':'attend','label':'Offer attention and comfort.','duration_hours':.25,
                 'success_text':'I received attentive care and felt more settled.','failure_text':'I received attention but remained unsettled.',
                 'contact_text':'I attended to a need for comfort.','caregiving':{'responsiveness':.9,'acceptance':.9}},
                {'id':'delay','label':'Signal that you cannot attend immediately.','duration_hours':.05,'activity_duration_hours':.05,
                 'success_multiplier':0,'success_text':'Attention was delayed.','failure_text':'Attention was delayed and I remained unsettled.',
                 'contact_text':'I could not attend immediately.','caregiving':{'responsiveness':.2,'acceptance':.5}}]},
            {'id':'settle','label':'Try settling or exploring quietly.','duration_hours':.25,'success_probability':.5,
             'success_text':'I settled after a quiet interval.','failure_text':'I remained unsettled.',
             'valence_success':.2,'valence_failure':-.1}]}
    rules=[care_rule('infancy',0,2,'You feel discomfort in a familiar caregiving setting. Use a nonverbal response.',
                    'Signal discomfort or seek familiar attention.'),
           care_rule('early-childhood',2,5,'You encounter a small frustrating activity near a caregiver.',
                     'Ask for attention or help with the small activity.'),
           care_rule('school-learning',5,12,'You are finding a school activity difficult and a caregiver may help.',
                     'Ask your caregiver to work through the difficult part.')]
    contact=peer or caregiver
    rules.append({'id':'adolescent-project','actor':actor,'min_age':12,'max_age':18,'rate_per_year':2,
        'situation':'You have an idea for a project and a familiar person is available to discuss it.','cues':['social','school'],
        'options':[{'id':'share','label':'Discuss the idea with the familiar person.','contact':contact,'duration_hours':1,
            'success_probability':.7,'success_text':'We developed a useful part of the idea.','failure_text':'The idea needed more work.',
            'contact_text':'We discussed a project idea.','valence_success':.3,'valence_failure':-.2,
            'contact_responses':[{'id':'discuss','label':'Listen and discuss the idea.','success_text':'We discussed the idea constructively.',
                'failure_text':'We listened but could not solve the difficulty.','contact_text':'I listened and discussed the project.'},
             {'id':'decline','label':'Explain that you cannot discuss it now.','duration_hours':.05,'activity_duration_hours':.05,
                'success_multiplier':0,'success_text':'We arranged another time.','failure_text':'A discussion was not possible now.',
                'contact_text':'I could not discuss the idea now.'}]},
           {'id':'draft','label':'Develop a small draft alone.','duration_hours':1,'success_probability':.6,
            'success_text':'I developed a useful small draft.','failure_text':'The draft remained incomplete.','valence_success':.3,'valence_failure':-.2}]})
    rules.append({'id':'adult-project','actor':actor,'min_age':18,'max_age':100,'rate_per_year':1.5,
        'goal_id':'small-community-task','new_goal':{'description':'Prepare a small useful contribution to a community project.','priority':.7},
        'situation':'You have an opportunity to work on your small community contribution.','cues':['work','challenge'],
        'options':[{'id':'prepare','label':'Spend one hour preparing a small usable part.','duration_hours':1,
            'success_probability':.65,'success_text':'I prepared a small usable part of my contribution.','failure_text':'My preparation needed more work.',
            'valence_success':.3,'valence_failure':-.2,'progress_gain':.25,
            'requires':{'facts':{actor:{'health_status':'well'}}}},
           {'id':'consult','label':'Discuss a small next step with a familiar person.','contact':contact,'duration_hours':1,
            'contact_text':'We discussed a small community contribution.','success_probability':.75,
            'success_text':'We identified a practical next step.','failure_text':'We did not settle on a next step.',
            'valence_success':.3,'valence_failure':-.2,'progress_gain':.25,
            'requires':{'facts':{actor:{'health_status':'well'}}}}]})
    for rule in rules: rule['id']=actor+':'+rule['id']
    return rules


def hazards(actor):
    return [
        {'id':actor+':illness','actor':actor,'min_age':0,'max_age':120,'rate_per_year':.15,
         'description':'A temporary illness begins.','requires':{'facts':{actor:{'health_status':'well'}}},
         'observations':{actor:{'text':'I feel temporarily unwell.','source':'direct','importance':.5}},
         'effects':{'facts':{actor:{'health_status':'temporarily-ill'}}}},
        {'id':actor+':recovery','actor':actor,'min_age':0,'max_age':120,'rate_per_year':4,
         'description':'A temporary illness resolves.','requires':{'facts':{actor:{'health_status':'temporarily-ill'}}},
         'observations':{actor:{'text':'I feel recovered from the temporary illness.','source':'direct'}},
         'effects':{'facts':{actor:{'health_status':'well'}}}},
        {'id':actor+':later-life-death','actor':actor,'min_age':75,'max_age':120,'rate_per_year':.08,'once':True,
         'description':'A person dies.','observations':{},'effects':{'deaths':[actor]}}]


def build(seed=42,caregivers=1,graphiti=False,household=False):
    if caregivers not in (1,2): raise ValueError('Example households support one or two known caregivers')
    engine=Engine(seed=seed);families={};parents=[]
    for child,child_name,names in [('alex','Alex',['Maya','Noor']),('bea','Bea',['Rowan','Kai'])]:
        ids=[]
        for index,name in enumerate(names[:caregivers]):
            key=name.lower();engine.entity(key,name,{'birth_day':-(25+index*2)*365.25,'health_status':'well'})
            engine.materialize(key,birth_day=-(25+index*2)*365.25)
            engine.agent(key)['resources']={'money':100}
            engine.agent(key)['culture']={'expression_rules':[{'cues':['family'],'tendency':'Consider caregiving duties while expressing your own needs.'}]}
            ids.append(key);parents.append(key)
        engine.entity(child,child_name,{'birth_day':0,'health_status':'well'})
        engine.materialize_child(child,biological_parents=ids,caregivers=ids,birth_day=0)
        engine.agent(child)['resources']={'money':10};families[child]=ids
    policy={'description':'Complete runnable accepted-mechanism scaffold; all rates, thresholds and outcomes are scenario choices, not fitted science.',
        'sampling':'event_driven','opportunities':[],'world_events':[],
        'cognition':{'graphiti_retrieval':graphiti,'semantic_recall':True,'indexed_retrieval':True,'reference_resolution':True,'reflection':True,
            'autonomous_goals':True,'semantic_candidates':24,'detail_threshold':.45,'fan_weight':.15,
            'rumination_per_year':4,'rumination_minimum_gap_days':1},
        'planning':{'calendar_mode':'elapsed','grounded_plans':True,'hours_per_day':12,'habit_half_life_days':30,'habit_gain':.1,'habit_max':1},
        'expression':{'std_by_domain':dict.fromkeys('NEOAC',1),'half_life_days':1,'age_appropriate_actions':True},
        'society':{'closeness_half_life_days':365.25},
        'background_expansion':{'default':{'mode':'generative','id':'personal-history-v1','min_age':18,
            'fields':['education','residence','interests']}},
        'situational_personality':{'recovery_half_life_days':1},'consolidation_batch_size':8,
        'development':{'maturation':{'N':[[0,0],[18,0],[40,-2],[65,-3]],'A':[[0,0],[18,0],[40,2],[65,3]],
            'C':[[0,0],[18,0],[40,2],[65,3]]},'crystallization':{'rate':.005,'minimum_days':3,'max_change_per_year':.5}}}
    for child,ids in families.items():policy['opportunities']+=opportunities(child,ids[0],'bea' if child=='alex' else 'alex')
    for parent in parents:
        engine.goal(parent,'personal-task','Finish a small personally useful task.',priority=.6)
    policy['goal_opportunity']={'id':'goal-step','actor':'$actor','goal_id':'$goal','min_age':2,'max_age':120,'rate_per_year':1.5,
        'situation':'You can take a small practical step toward your self-set intention: $goal_description','cues':['challenge'],
        'options':[{'id':'small-step','label':'Spend half an hour on a small practical step appropriate to your age.','duration_hours':.5,
            'success_probability':.6,'success_text':'I completed a small useful step on my intention.','failure_text':'The small step remained difficult.',
            'valence_success':.2,'valence_failure':-.1,'progress_gain':.25},
            {'id':'reflect','label':'Take half an hour to consider a different approach.','duration_hours':.5,
             'success_probability':.6,'success_text':'I identified a clearer next step.','failure_text':'I remained unsure of my next step.',
             'valence_success':.1,'valence_failure':-.1,'progress_gain':.1}]}
    policy['world_hazards']=[rule for actor in engine.state['agents'] for rule in hazards(actor)]
    policy['world_hazards'].append({'id':'alex:new-dependent','actor':'alex','min_age':25,'max_age':40,'rate_per_year':.1,'once':True,
        'description':'A newborn joins the household.','requires':{'facts':{'alex':{'health_status':'well'}}},
        'observations':{'alex':{'text':'A newborn has joined my household and depends on my care.','source':'direct','importance':.9}},
        'effects':{'births':[{'id':'alex-next','name':'Ari','biological_parents':[],'caregivers':['alex'],'facts':{'health_status':'well'}}],
                   'facts':{}}})
    policy['newborn_opportunities']=opportunities('$actor','$caregiver',None)
    policy['newborn_hazards']=hazards('$actor')
    if household:
        policy['household']={'rooms':{},'locations':{},'routines':{},'conversations':[]}
        setting=policy['household']
        for child,ids in families.items():
            room=child+'-home'
            setting['rooms'][room]={'label':child.title()+"'s household common room"}
            for owner in [child,*ids]:
                setting['locations'][owner]=room
                setting['routines'][owner]={'available_hours':[[7,22]],'response_minutes':[.5,2]}
            for age in (1,6,16,21):
                setting['conversations'].append({'id':child+':family:'+str(age),'day':floor(age*365.25)+.75,
                    'room':room,'participants':[child,*ids],'topic':
                    'A familiar household moment of attention and comfort.' if age<2 else 'Discuss a small difficulty and what each person needs.',
                    'max_turns':4})
    return engine,policy
