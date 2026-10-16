"""Independent caregiver decisions, shared outcomes and privacy; stubbed API."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from engine import Engine
from initialize_life import initialize
from lifetime import Lifetime


def main():
    p=json.loads(Path(__file__).with_name('development-demo.json').read_text())
    p.pop('situational_personality')
    p.pop('consolidation_batch_size')
    p['opportunities']=[p['opportunities'][0]]
    rule=p['opportunities'][0]
    rule.update(min_age=0,rate_per_year=4,options=[rule['options'][0]])
    rule['options'][0]['success_probability']=1
    e=initialize()
    e.schedule('private',0,'Alex has a private thought.',{'alex':{'text':'PRIVATE_CHILD_SECRET: I am worried about a different project.',
                        'source':'self','kind':'internal','valence':-.4}})
    e.advance(0)
    c=Lifetime(e,p)
    due=next(iter(e.state['runtime']['next_opportunities'].values()))
    original=deepcopy(e.state)
    def stub(system,context,api,model,max_tokens=600):
        if 'new_observation' in context:
            out={'meaning':'I perceived the interaction.','valence':-.1,'arousal':.2,'importance':.5,'confidence':.6}
            if 'caregiving' in context['new_observation']:
                out['caregiving']={'caregiver':'maya','responsiveness':.2,'acceptance':.8}
            return out
        if context['identity']['id']=='maya':
            assert 'PRIVATE_CHILD_SECRET' not in json.dumps(context)
            assert any(r['dependent']=='alex' for r in context['identity']['known_caregiving_roles'])
            assert 'Could you help me?' in context['situation']
            return {'action':'Explain that I am unavailable.','action_id':'unavailable','speech':'I cannot help right now, but you can try another way.',
                    'goal_id':None,'plan':[],'memory_ids':[]}
        return {'action':'Ask Maya for help.','action_id':'ask-caregiver','speech':'Could you help me?',
                'goal_id':None,'plan':[],'memory_ids':[]}
    with TemporaryDirectory() as directory:
        checkpoint=Path(directory)/'world.json'
        def failed(system,context,api,model,max_tokens=600):
            if context['identity']['id']=='maya':
                raise RuntimeError('fixture unavailable contact provider')
            return stub(system,context,api,model,max_tokens)
        with patch('engine.request_json',side_effect=failed):
            try:
                c.run(due,checkpoint)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Contact failure swallowed')
        assert e.state==original and Engine.load(checkpoint).state==original
        with patch('engine.request_json',side_effect=stub):
            Lifetime(e,p).run(due,checkpoint)
        assert len(e.state['actions'])==2 and {a['owner'] for a in e.state['actions']}=={'alex','maya'}
        assert all(a['status']=='resolved' for a in e.state['actions'])
        assert len({a['outcome_event'] for a in e.state['actions']})==1
        observed=e.state['events'][-1]
        assert 'unavailable' in observed['observations']['alex']['text']
        assert 'PRIVATE_CHILD_SECRET' not in json.dumps(observed['observations']['maya'])
        assert not e.state['runtime']['trace'][-2]['success']
        assert len(e.agent('alex')['caregiving_experiences'])==1
        assert not e.agent('maya').get('caregiving_experiences')
        assert Engine.load(checkpoint).context('alex','Next?')==e.context('alex','Next?')
    result={'passed':True,'scope':'synthetic stubbed interaction engineering only',
        'checks':['caregiver chooses independently from own context','private child thought not shared with caregiver',
                  'committed caregiving role is available without private child history',
                  'caregiver receives only transmitted request','declining response changes outcome probability and observed behavior',
                  'one shared outcome resolves both intentions','child learns from response, not task success alone',
                  'contact API failure rolls back both actors','checkpoint restores interaction state']}
    Path(__file__).with_name('interaction-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
