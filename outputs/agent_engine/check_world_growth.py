"""Lazy activation and bounded state-dependent event checks; synthetic only."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from engine import Engine, FACET_NAMES
from lifetime import Lifetime


def world():
    e=Engine(seed=2)
    e.entity('child','Child')
    e.materialize('child',dict.fromkeys(FACET_NAMES,50))
    e.entity('caregiver','Caregiver',{'birth_day':-25*365.25})
    e.caregiver('child','caregiver')
    return e


def main():
    p={'sampling':'event_driven','opportunities':[{'id':'support','actor':'child','min_age':0,'max_age':18,
        'rate_per_year':4,'situation':'A project is difficult. What now?',
        'options':[{'id':'ask','label':'Ask caregiver for help.','contact':'caregiver',
                    'contact_text':'I helped the child with a task.','success_probability':1,
                    'success_text':'My caregiver helped me work on the task.','failure_text':'I was still stuck.',
                    'valence_success':.4,'valence_failure':-.3}]}]}
    e=world()
    controller=Lifetime(e,p)
    due=next(iter(e.state['runtime']['next_opportunities'].values()))
    before=deepcopy(e.state)
    def stub(system,context,api,model,max_tokens=600):
        if 'new_observation' in context:
            return {'meaning':'We worked on the task.','valence':.2,'arousal':.2,'importance':.4,'confidence':.6}
        return {'action':'Ask caregiver for help.','action_id':'ask','speech':'','goal_id':None,'plan':[],'memory_ids':[]}
    with TemporaryDirectory() as directory:
        checkpoint=Path(directory)/'world.json'
        with patch('engine.request_json',side_effect=stub), patch.object(Engine,'appraise',side_effect=RuntimeError('fixture unavailable')):
            try:
                controller.run(due,checkpoint)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Failure was swallowed')
        assert e.state==before and 'caregiver' not in e.state['agents'], 'Failed event leaked a newly activated agent'
        with patch('engine.request_json',side_effect=stub):
            Lifetime(e,p).run(due,checkpoint)
        assert 'caregiver' in e.state['agents']
        assert len(e.agent('caregiver')['memory_meta'])==1, 'Activation invented a historical memory'
        assert e.agent('child')['relationships']['caregiver']['firsthand']
        assert Engine.load(checkpoint).state==e.state
        # State-dependent opportunities use a constant upper envelope and reproducible thinning.
        modified=deepcopy(p)
        rule=modified['opportunities'][0]
        rule.update(rate_per_year=1,rate_cap_per_year=8,
                    rate_modifiers=[{'feature':'resolved_actions','coefficient':2,'scale':2}])
        whole,split=world(),world()
        controller=Lifetime(whole,modified,scripted=True)
        assert controller.current_rate(rule)==1
        controller.run(3*365.25)
        assert controller.current_rate(rule)>1 and controller.current_rate(rule)<=8
        assert any(t.get('status')=='thinned' for t in whole.state['runtime']['trace'])
        Lifetime(split,modified,scripted=True).run(1.5*365.25,checkpoint)
        split=Engine.load(checkpoint)
        Lifetime(split,modified,scripted=True).run(3*365.25)
        assert split.state==whole.state, 'Thinning changed with checkpoint placement'
        assert len(whole.state['actions'])>0
        # Mention alone is still not an activation request or a firsthand encounter.
        mention=world()
        mention.schedule('gossip',0,'A name is mentioned.',{'child':{'text':'Someone mentioned my caregiver.',
                         'source':'other','kind':'testimony','references':['caregiver']}})
        mention.advance(0)
        mention.context('child','caregiver')
        assert 'caregiver' not in mention.state['agents']
        assert not mention.agent('child')['relationships']['caregiver']['firsthand']
        future=world()
        future.state['entities']['caregiver']['facts']['birth_day']=20*365.25
        Lifetime(future,p,scripted=True).run(365.25)
        assert not future.state['actions'] and 'caregiver' not in future.state['agents'], 'Unborn contact was offered or activated'
    result={'passed':True,'scope':'synthetic engineering checks; no calibrated event-rate claim',
        'checks':['chosen interaction activates only committed identity','failed activation event rolls back',
                  'no invented historical memories','direct encounter required for firsthand edge',
                  'bounded action-history-dependent rates','thinning rejects candidate events',
                  'state-dependent scheduler checkpoint equivalence','mention and inspection do not activate agents',
                  'unborn lightweight contacts are not offered or activated']}
    Path(__file__).with_name('world-growth-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
