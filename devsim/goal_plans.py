"""Bind subjective plans to offered actions; only received outcomes finish steps.

This is an execution ledger, not a validated planner or proof that generic
scenario actions achieve arbitrary real-world ambitions. World effects and
progress amounts remain controller-authored scenario rules.
"""
from copy import deepcopy
from hashlib import sha256
import json


def enabled(engine):
    return engine.state['config'].get('planning',{}).get('grounded_plans',False)


def prepare(engine,owner,goal_id,options,*,api,model,scripted=False):
    if not enabled(engine) or goal_id is None: return
    from .engine import validated_json
    goal=engine.agent(owner)['goals'][goal_id]
    if goal['status']!='active': return
    # A catalog is controller-authored; model prose cannot add actions/effects.
    catalog=[{'id':o['id'],'label':o['label'],'duration_hours':o.get('duration_hours',0),
              'costs':deepcopy(o.get('costs',{}))} for o in options if o.get('goal_id',goal_id)==goal_id]
    if not catalog: return
    digest=sha256(json.dumps(catalog,sort_keys=True).encode()).hexdigest()
    old=goal.get('execution_plan')
    if old and old['catalog_hash']==digest and not old.get('needs_replan') and any(s['status']=='pending' for s in old['steps']): return
    if old and old['catalog_hash']==digest and not old['steps'] and not old.get('needs_replan') and old.get('received_episode_count')==len(engine.agent(owner)['memory_meta']): return
    context=engine.context(owner,'Choose actionable next steps toward this intention.')
    context.update(task='ground_goal_plan',planning_goal={'id':goal_id,'description':goal['description'],
        'proposed_steps':deepcopy(goal['plan']),'previous_execution':deepcopy(old)},action_catalog=catalog)
    def validate(result):
        steps=result.get('steps')
        if not isinstance(steps,list) or len(steps)>4: raise ValueError('Return steps: at most four ordered action bindings, or [] if none fit')
        for step in steps:
            if not isinstance(step,dict) or set(step)!={'description','action_id'}: raise ValueError('Plan steps need only description and action_id')
            if step['action_id'] not in {o['id'] for o in catalog}: raise ValueError('Plan action_id must be in action_catalog')
            if not isinstance(step['description'],str) or not 0<len(step['description'].strip())<=600: raise ValueError('Plan description needs bounded nonempty text')
    if scripted:
        result={'steps':[{'description':catalog[0]['label'],'action_id':catalog[0]['id']}]}
    else:
        result=validated_json('Bind a small intended plan to the offered action_catalog for this fictional agent. '
            'Return JSON {"steps": [{"description": "intended step", "action_id": "offered id"}]}. '
            'Use at most four ordered steps; later steps depend on earlier completion. Use steps: [] if no action fits. '
            'Do not invent actions, evidence, outcomes or capabilities. Respect developmental_capabilities. '
            'A binding expresses intention, not a claim that the action guarantees the goal.',context,validate,api,model,650)
    validate(result)
    version=old['version']+1 if old else 1
    if old: goal.setdefault('execution_plan_versions',[]).append(deepcopy(old))
    goal['execution_plan']={'version':version,'day':engine.day,'catalog_hash':digest,'needs_replan':False,
        'provider':'scripted_engineering_fixture' if scripted else 'local_model_api',
        'received_episode_count':len(engine.agent(owner)['memory_meta']),
        'steps':[{**deepcopy(step),'status':'pending','attempts':[]} for step in result['steps']]}


def bind(engine,owner,goal_id,action_id):
    if not enabled(engine) or goal_id is None: return None
    plan=engine.agent(owner)['goals'][goal_id].get('execution_plan')
    if not plan: return None
    current=next((i for i,s in enumerate(plan['steps']) if s['status']=='pending'),None)
    if current is None or plan['steps'][current]['action_id']!=action_id: return None
    return {'goal_id':goal_id,'version':plan['version'],'step_index':current,'action_id':action_id}


def current_step(engine,owner,binding):
    if binding is None: return None
    goal=engine.agent(owner)['goals'].get(binding['goal_id'],{})
    plan=goal.get('execution_plan',{})
    if plan.get('version')!=binding['version']: return None
    index=binding['step_index'];steps=plan['steps']
    if not 0<=index<len(steps) or any(s['status']!='completed' for s in steps[:index]): return None
    step=steps[index]
    return step if step['status']=='pending' and step['action_id']==binding['action_id'] else None


def record(engine,owner,binding,event_id,success):
    step=current_step(engine,owner,binding)
    if step is None: return
    # Only an actual resolved action and privately received outcome supply proof.
    agent=engine.agent(owner)
    if event_id not in agent['memory_meta'] or not any(a['owner']==owner and a['status']=='resolved' and
            a.get('outcome_event')==event_id and a['decision'].get('action_id')==binding['action_id'] for a in engine.state['actions']):
        raise ValueError('Plan progress requires a matching resolved action and received outcome')
    if any(a['event']==event_id for a in step['attempts']): raise ValueError('Duplicate plan outcome')
    step['attempts'].append({'event':event_id,'day':engine.day,'success':success})
    if success: step.update(status='completed',completed_event=event_id)
    else: agent['goals'][binding['goal_id']]['execution_plan']['needs_replan']=True


def request_replan(goal):
    if goal.get('execution_plan'): goal['execution_plan']['needs_replan']=True
