"""Executable plan integration: intentions never count as received outcomes."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from engine import Engine,FACET_NAMES
from lifetime import Lifetime
import goal_plans


def fixture():
    e=Engine(seed=12);e.entity('a','A',{'birth_day':-25*365.25})
    e.materialize('a',dict.fromkeys(FACET_NAMES,50),birth_day=-25*365.25);e.goal('a','g','Prepare a small draft.')
    policy={'sampling':'event_driven','planning':{'calendar_mode':'elapsed','grounded_plans':True,'hours_per_day':8},
        'opportunities':[{'id':'drafting','actor':'a','goal_id':'g','rate_per_year':365,'min_age':18,'max_age':80,
            'situation':'Prepare a small draft.','options':[{'id':'draft','label':'Draft a paragraph.','duration_hours':1,
            'success_probability':1,'progress_gain':.25,'success_text':'I drafted a paragraph.',
            'failure_text':'The paragraph is unfinished.','valence_success':.2,'valence_failure':-.2}]}]}
    return e,policy


def reject(call):
    try:call()
    except ValueError:return
    raise AssertionError('Invalid plan accepted')


def main():
    checks=[];e,p=fixture();controller=Lifetime(e,p,scripted=True)
    due=e.state['runtime']['next_opportunities']['drafting']
    with TemporaryDirectory() as tmp:
        path=Path(tmp)/'world.json';controller.run(due,path)
        g=e.agent('a')['goals']['g'];assert g['progress']==0 and g['execution_plan']['steps'][0]['status']=='pending'
        assert e.state['actions'][0]['status']=='intended'
        checks.append('a plan and a committed intention award no progress')
        resumed=Engine.load(path);Lifetime(resumed,p,scripted=True).run(due+1/24,path)
        g=resumed.agent('a')['goals']['g'];step=g['execution_plan']['steps'][0]
        assert g['progress']==.25 and step['status']=='completed' and step['completed_event'] in resumed.agent('a')['memory_meta']
        assert step['attempts'][0]['success'] and not resumed.state['runtime']['pending_activities']
        checks.append('checkpointed binding completes only after received elapsed outcome')
        snapshot=deepcopy(resumed.state)
        binding=e.state['runtime']['pending_activities'][next(iter(e.state['runtime']['pending_activities']))]['plan_binding']
        goal_plans.record(resumed,'a',binding,step['completed_event'],True)
        assert resumed.state==snapshot
        checks.append('duplicate outcome cannot award a second step completion')
        options=p['opportunities'][0]['options']
        good={'steps':[{'description':'Draft a paragraph.','action_id':'draft'}]}
        # Replanning versions must not let old pending outcomes finish a new step.
        goal_plans.request_replan(g)
        with patch('engine.request_json',return_value=good):goal_plans.prepare(resumed,'a','g',options,api='stub',model='stub')
        assert g['execution_plan']['version']==2 and len(g['execution_plan_versions'])==1
        assert goal_plans.current_step(resumed,'a',binding) is None
        checks.append('replans archive prior steps and reject stale version bindings')
        before=deepcopy(resumed.state);goal_plans.request_replan(g);before=deepcopy(resumed.state)
        with patch('engine.request_json',return_value={'steps':[{'description':'Claim wealth.','action_id':'invented'}]}):
            reject(lambda:goal_plans.prepare(resumed,'a','g',options,api='stub',model='stub'))
        assert resumed.state==before
        checks.append('invented action bindings are rejected without partial plan mutation')
        with patch('engine.request_json',return_value={'steps':[]}):goal_plans.prepare(resumed,'a','g',options,api='stub',model='stub')
        assert not g['execution_plan']['steps'] and g['progress']==.25
        checks.append('no suitable action leaves the goal unachieved without inventing a task')
    # Failure of completion rolls back the event, retaining the saved intention.
    e,p=fixture();c=Lifetime(e,p,scripted=True);due=e.state['runtime']['next_opportunities']['drafting'];c.run(due)
    activity=next(iter(e.state['runtime']['pending_activities'].values()));before=deepcopy(e.state)
    with patch('goal_plans.record',side_effect=RuntimeError('fixture interruption')):
        try:c.run(activity['day'])
        except RuntimeError:pass
        else:raise AssertionError('Completion failure did not propagate')
    assert e.state==before
    Lifetime(e,p,scripted=True).run(activity['day']);assert e.agent('a')['goals']['g']['progress']==.25
    checks.append('completion failure rolls back and retries exactly once with saved binding')
    # An offered alternative need not be the plan's next step and may not skip it.
    e,p=fixture();Lifetime(e,p,scripted=True);options=p['opportunities'][0]['options']+[{'id':'review','label':'Review the draft.'}]
    with patch('engine.request_json',return_value={'steps':[{'description':'First draft.','action_id':'draft'},
            {'description':'Then review.','action_id':'review'}]}):goal_plans.prepare(e,'a','g',options,api='stub',model='stub')
    assert goal_plans.bind(e,'a','g','review') is None
    assert goal_plans.bind(e,'a','g','draft')['step_index']==0
    checks.append('later steps cannot bypass unfinished prerequisites')
    e,p=fixture();p['opportunities'][0]['options'][0]['success_probability']=0
    c=Lifetime(e,p,scripted=True);due=e.state['runtime']['next_opportunities']['drafting'];c.run(due+1/24)
    g=e.agent('a')['goals']['g'];assert g['progress']==0 and g['execution_plan']['needs_replan']
    assert g['execution_plan']['steps'][0]['status']=='pending'
    checks.append('failed received attempt preserves unfinished steps and requests replanning')
    e,p=fixture()
    alternative=deepcopy(p['opportunities'][0]['options'][0]);alternative.update(id='review',label='Review a draft.')
    p['opportunities'][0]['options'].append(alternative)
    c=Lifetime(e,p,scripted=True);due=e.state['runtime']['next_opportunities']['drafting']
    with patch('random.Random.randrange',return_value=1):c.run(due+1/24)
    assert e.state['actions'][0]['decision']['action_id']=='review'
    assert e.agent('a')['goals']['g']['progress']==0
    assert e.agent('a')['goals']['g']['execution_plan']['steps'][0]['status']=='pending'
    checks.append('controller resolves an off-plan alternative without skipping steps or awarding goal progress')
    result={'passed':True,'scope':'software plan execution with canonical scenario actions; no validated life-planning claim','checks':checks}
    Path(__file__).with_name('goal-plans-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
