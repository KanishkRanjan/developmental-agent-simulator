"""Bounded model views and rendered-token guards; no inference needed."""
from copy import deepcopy
from io import StringIO
from http.client import RemoteDisconnected
import json
from pathlib import Path
from unittest.mock import patch

from devsim.context_view import compact
from devsim.engine import Engine, FACET_NAMES, request_json

RESULTS_DIR = Path(__file__).resolve().parent / 'results'


def response(value):
    return StringIO(json.dumps(value))


def main():
    source={'situation':'A current task.','personality':{'tendencies':['Consider consequences.']},
            'available_actions':[{'id':'ask','label':'Ask a question.'}],
            'memories':[{'event':str(i),'text':'An old event. '*150} for i in range(20)],
            'beliefs':{str(i):{'text':'Tentative belief. '*50} for i in range(10)}}
    before=deepcopy(source)
    view=compact(deepcopy(source),4096)
    assert len(json.dumps(view).encode())<=4096
    assert view['available_actions']==source['available_actions']
    assert view['personality']==source['personality'] and source==before
    assert view['context_view']['omitted']['memories']>0
    omissions=deepcopy(view['context_view'])
    compact(view,4096)
    assert view['context_view']==omissions
    recall={'situation':'Choose.','task':'semantic_recall','memories':[],
            'memory_candidates':[{'event':f'm{i}','meaning':'A long appraised meaning. '*40} for i in range(24)]}
    trimmed=compact(deepcopy(recall),16000)
    assert len(json.dumps(trimmed).encode())<=16000 and 3<=len(trimmed['memory_candidates'])<24
    assert [c['event'] for c in trimmed['memory_candidates']]==[f'm{i}' for i in range(len(trimmed['memory_candidates']))]
    assert trimmed['context_view']['omitted']['memory_candidates']==24-len(trimmed['memory_candidates'])
    models={'data':[{'id':'local','meta':{'n_ctx':8192}}]}
    with patch('devsim.engine.urlopen',side_effect=[response(models),response({'prompt':'Rendered prompt.'}),
        response({'tokens':[1]*100}),response({'choices':[{'message':{'content':'{"ok":true}'}}]})]) as transport:
        assert request_json('A system message.',view,'http://local','local')=={'ok':True}
        assert transport.call_count==4
    with patch('devsim.engine.urlopen',side_effect=[response(models),response({'prompt':'Large rendered prompt.'}),
        response({'tokens':[1]*8000})]) as transport:
        try:
            request_json('A system message.',{'situation':'x'*10000},'http://local','local')
        except RuntimeError:
            pass
        else:
            raise AssertionError('Oversized rendered prompt accepted')
        assert transport.call_count==3, 'Overflow reached inference instead of stopping before it'
    trimmed=deepcopy(source)
    with patch('devsim.engine.urlopen',side_effect=[response(models),response({'prompt':'Large prompt.'}),response({'tokens':[1]*16000}),
        response({'prompt':'Reduced prompt.'}),response({'tokens':[1]*100}),
        response({'choices':[{'message':{'content':'{"ok":true}'}}]})]) as transport:
        assert request_json('A system message.',trimmed,'http://local','local')=={'ok':True}
        assert transport.call_count==6 and len(trimmed['memories'])<len(source['memories'])
    e=Engine()
    e.entity('a','A')
    e.materialize('a',dict.fromkeys(FACET_NAMES,50))
    original=deepcopy(e.state)
    def budgeted(system,context,api,model,max_tokens=600):
        context['memories'].clear()  # Emulate a reduced transport view.
        context['context_view']['omitted']['memories']=1
        return {'action':'Pause.','speech':'','goal_id':None,'plan':[],'memory_ids':[]}
    with patch('devsim.engine.request_json',side_effect=budgeted):
        proposal=e.propose('a','What next?')
    e.commit_action('budgeted-action',proposal)
    assert len(e.state['actions'])==1, 'A smaller prompt view was incorrectly treated as an intervening experience'
    original=deepcopy(e.state)
    malformed={'meaning':'An ordinary event.','valence':0,'arosal':.2,'importance':.3,'confidence':.5}
    correct={**malformed,'arousal':.2}
    correct.pop('arosal')
    with patch('devsim.engine.request_json',side_effect=[malformed,correct]) as model:
        appraised=e.appraise('a',{'text':'An ordinary event.','source':'direct'})
        assert appraised['arousal']==.2 and model.call_count==2
        assert 'arousal' in model.call_args_list[1].args[1]['output_repair']['validation_error']
    assert e.state==original
    with patch('devsim.engine.urlopen',side_effect=RemoteDisconnected('fixture closed connection')) as transport, \
            patch('devsim.engine.RETRY_DELAYS',(0,0)):
        try:
            request_json('A system message.',view,'http://local','local')
        except RuntimeError as error:
            assert isinstance(error.__cause__,RemoteDisconnected)
        else:
            raise AssertionError('Closed transport was not reported as a model request failure')
        assert transport.call_count==3, 'a dropped connection is retried twice before failing'
    # One dropped connection, then success: the retry recovers instead of ending the run.
    with patch('devsim.engine.urlopen',side_effect=[RemoteDisconnected('blip'),response(models),response({'prompt':'P.'}),
            response({'tokens':[1]*100}),response({'choices':[{'message':{'content':'{"ok":true}'}}]})]), \
            patch('devsim.engine.RETRY_DELAYS',(0,0)):
        assert request_json('A system message.',deepcopy(view),'http://local','local')=={'ok':True}
    with patch('devsim.engine.request_json',return_value=malformed) as model:
        try:
            e.appraise('a',{'text':'An ordinary event.','source':'direct'})
        except ValueError:
            pass
        else:
            raise AssertionError('Permanently malformed output accepted')
        assert model.call_count==3 and e.state==original
    result={'passed':True,'scope':'engineering only; stubbed transport',
            'checks':['bounded optional context without modifying original state',
                      'current personality and offered actions retained', 'omissions explicit and stable',
                      'optional history reduced using actual rendered-token count',
                      'smaller transport view preserves proposal staleness checks',
                      'actual template and tokenizer used for window check','output-token reserve included',
                      'overflow stops before inference','malformed fields repaired before mutation',
                      'permanently malformed responses stop after two repairs without changing state',
                      'closed connections are retried twice, then become explicit model-request failures; a single blip recovers',
                      'many long retrieval candidates are trimmed lowest-ranked first instead of failing the call']}
    RESULTS_DIR.joinpath('context-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
