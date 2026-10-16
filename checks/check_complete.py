"""Remaining-path regressions: private search, references, time, histories, expression."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devsim.engine import Engine,FACET_NAMES
from devsim.lifetime import Lifetime
from devsim import cognition, biography, references, expression, society, life_policy

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
def world():
    e=Engine(seed=21)
    for key,name in [('a','A'),('b','Sam'),('c','Sam')]:
        e.entity(key,name,{'birth_day':-25*365.25});e.materialize(key,dict.fromkeys(FACET_NAMES,50),birth_day=-25*365.25)
    e.agent('a')['resources']={'money':10};e.goal('a','project','Prepare a small project step.')
    return e


def reject(call):
    try:call()
    except (ValueError,RuntimeError):return
    raise AssertionError('Invalid operation accepted')


def policy():
    return {'sampling':'event_driven','planning':{'hours_per_day':8,'calendar_mode':'elapsed'},
        'opportunities':[{'id':'activity','actor':'a','rate_per_year':365,'min_age':0,'max_age':100,
            'situation':'Work on a small project step.','goal_id':'project','options':[{'id':'work','label':'Do two hours of work.',
            'duration_hours':2,'costs':{'money':1},'success_probability':1,'success_text':'I finished a small useful step.',
            'failure_text':'The step remained unfinished.','valence_success':.2,'valence_failure':-.2,'progress_gain':.2}]}]}


def reflect_stub(system,context,api,model,max_tokens=600):
    if context.get('task')=='reflect_received_evidence':
        return {'summary':'I considered a next step.','topics':['work'],'revisions':[],'narrative':None,
            'plans':[],'probes':[],'new_goals':[{'description':'Draft one short paragraph.','priority':.6,
            'evidence':[context['new_evidence']['event']]}]}
    return {'action':'Work on the step.','action_id':'work','speech':'','goal_id':None,'plan':[],'memory_ids':[]}


def main():
    checks=[]
    # Full-corpus search finds distant low-salience paraphrases omitted by the
    # old importance shortlist, without indexing another agent's private text.
    e=world();cognition.configure(e,{'indexed_retrieval':True,'semantic_candidates':4,'detail_threshold':.9})
    for i in range(40):
        e.schedule('m'+str(i),0,'A receives an episode.',{'a':{'text':'Unrelated original detail '+str(i),
            'source':'direct','meaning':'An ordinary experience.','importance':0 if i==0 else .9}});e.advance(0)
        e.agent('a')['memory_meta']['m'+str(i)].update(summary='I was dismissed from employment.' if i==0 else 'I attended an ordinary meeting.',topics=['employment'] if i==0 else ['meeting'])
    e.advance(1000)
    captured=[]
    def search_stub(system,context,api,model,max_tokens=600):
        captured.append(deepcopy(context))
        if context.get('task')=='expand_retrieval_query':return {'queries':['dismissed employment redundancy']}
        assert any(m['event']=='m0' for m in context['memory_candidates'])
        return {'memory_ids':['m0']}
    with patch('devsim.engine.request_json',side_effect=search_stub): cognition.semantic_recall(e,'a','I lost my job.',api='stub',model='stub')
    assert e.agent('a')['retrieval_focus']['ids']==['m0']
    assert 'Unrelated original detail' not in json.dumps(captured)
    assert e.agent('a')['memory_meta']['m0']['last_recall_day'] is None
    checks+=['query expansion searches full available corpus beyond salience shortlist','index excludes inaccessible original detail','gist semantic selection cannot restore detail']
    # Named ambiguity is listener-local and is not resolved using hidden world data.
    r=world();r.relate('a','b','coworker');r.relate('a','c','neighbor')
    obs={'text':'Sam talked about a friend named Nova.','source':'b','kind':'testimony'}
    mentions=references.normalize(r,'a',obs,[{'span':'Sam','candidate_ids':['b']},{'span':'Nova','candidate_ids':[]}])
    assert mentions[0]['candidate_ids']==['b','c'] and mentions[0]['resolved_id'] is None
    obs['mentions']=mentions;r.schedule('account',0,'A hears an account.',{'a':obs});r.advance(0)
    rid=mentions[0]['reference_id'];assert r.agent('a')['unresolved_references'][rid]['resolved_id'] is None
    assert len(r.state['entities'])==3 and not r.agent('a')['relationships']['b']['firsthand']
    r.schedule('identify',1,'A receives an identification.',{'a':{'text':'This is Sam from work.','source':'direct',
        'encountered':['b'],'resolved_references':{rid:'b'}}});r.advance(1)
    assert r.agent('a')['unresolved_references'][rid]['binding']=='b'
    assert r.agent('a')['relationships']['b']['firsthand'] and not r.agent('a')['relationships']['c']['firsthand']
    reject(lambda:references.normalize(r,'a',obs,[{'span':'Sam','candidate_ids':['not-known']}]))
    checks+=['ambiguous names retain all known candidates without global identity leakage','unknown mentions do not spawn people or fabricate acquaintance',
             'received identification binds a reference and only actual encounter creates firsthand edge']
    # Free-value biography intervals cannot contradict world locks or prior eras.
    h=world();h.advance(100)
    p={'mode':'generative','fields':['education','occupation'],'id':'bio-v1'}
    good={'current_facts':{'education':'Vocational study','occupation':'Carpenter'},'timeline':[
        {'field':'education','value':'Vocational study','start_day':-1000,'end_day':100},
        {'field':'occupation','value':'Carpenter','start_day':-100,'end_day':100}],'overview':'A synthetic constrained background.'}
    with patch('devsim.engine.request_json',return_value=good): biography.expand(h,'a',p,api='stub',model='stub')
    assert h.context('a','Next?')['background_facts']['occupation']=='Carpenter'
    assert not h.agent('a')['memory_meta']
    before=deepcopy(h.state);bad=deepcopy(good);bad['timeline'][0]['start_day']=-1e6
    with patch('devsim.engine.request_json',return_value=bad): reject(lambda:biography.expand(h,'a',{**p,'id':'bio-v2'},api='stub',model='stub'))
    assert h.state==before
    bad=deepcopy(good);bad['timeline'].append({'field':'occupation','value':'Pilot','start_day':0,'end_day':10})
    with patch('devsim.engine.request_json',return_value=bad): reject(lambda:biography.expand(h,'a',{**p,'id':'bio-v3'},api='stub',model='stub'))
    assert h.state==before
    checks+=['open biography values reach own context without invented observations','history rejects pre-birth and conflicting overlapping eras transactionally']
    # Culture and a separate supplied construct affect expression, not core scores.
    x=world();x.agent('a')['culture']={'expression_rules':[{'cues':['family'],'tendency':'Use indirect disagreement in family conversations.'}]}
    x.agent('a')['additional_traits']={'honesty_humility':{'percentile':90,'source':'explicit synthetic fixture'}}
    traits=deepcopy(x.agent('a')['facets']); expression.configure(x,{'std_by_domain':{'N':2,'E':2}})
    perception={'meaning':'A demanding moment.','dimensions':dict.fromkeys(__import__('devsim.situation',fromlist=['_']).DIMENSIONS,0),'controllability':.5,'active_rule_ids':[]}
    from devsim import situation
    first=expression.vary(x,'a','state1',situation.transition(x.agent('a'),x.day,perception,1))
    assert first==expression.vary(x,'a','state1',situation.transition(x.agent('a'),x.day,perception,1))
    assert any(abs(v)>0 for v in first['offsets'].values()) and x.agent('a')['facets']==traits
    assert 'indirect' in json.dumps(x.context('a','At home',cues=['family']))
    assert '90' not in json.dumps(expression.language(x.agent('a'),['family']))
    reject(lambda:expression.factor([[1,2,0,0,0],[2,1,0,0,0],[0,0,1,0,0],[0,0,0,1,0],[0,0,0,0,1]]))
    checks+=['correlated temporary variation is seeded and does not change baseline traits','explicit cultural rules and separate constructs use language without invented Big Five mapping','invalid covariance rejected']
    # Activity starts and completion are distinct, with resumable pending intents.
    with TemporaryDirectory() as directory:
        checkpoint=Path(directory)/'world.json';q=policy();whole=world();split=world()
        c=Lifetime(split,q,scripted=True);start=split.state['runtime']['next_opportunities']['activity'];finish=start+2/24
        c.run(start,checkpoint)
        assert split.state['actions'][0]['status']=='intended' and split.agent('a')['goals']['project']['progress']==0
        assert split.state['runtime']['pending_activities']
        split=Engine.load(checkpoint);Lifetime(split,q,scripted=True).run(finish+1e-6)
        Lifetime(whole,q,scripted=True).run(finish+1e-6)
        assert whole.state==split.state and whole.state['actions'][0]['status']=='resolved'
        assert whole.state['actions'][0]['day']<next(e['day'] for e in whole.state['events'] if e['id']==whole.state['actions'][0]['outcome_event'])
        assert abs(sum(whole.agent('a')['time_use'].values())-2)<1e-7
        checks+=['elapsed activities preserve intended state until completion','pending activity and later outcome resume identically','time is reserved in actual intervals rather than instantaneous outcomes']
        # An intervening death cancels an activity rather than awarding future success.
        d=world();q2=policy();q2['world_events']=[{'id':'death','day':start+1/24,'description':'A dies.',
            'observations':{},'effects':{'deaths':['a']}}]
        Lifetime(d,q2,scripted=True).run(finish+1e-6)
        assert d.state['actions'][0]['status']=='cancelled' and d.agent('a')['goals']['project']['progress']==0
        checks.append('intervening death cancels unfinished action without future success or memory')
        # New intentions receive canonical actionable opportunities and survive resume.
        g=world();g.schedule('experience',0,'A considers a task.',{'a':{'text':'I want to draft a paragraph.','source':'self','kind':'internal'}});g.advance(0)
        template=deepcopy(q['opportunities'][0]);template.update(id='goal-template',actor='$actor',goal_id='$goal')
        q3={'sampling':'event_driven','opportunities':[],'goal_opportunity':template,
            'planning':{'calendar_mode':'elapsed','hours_per_day':8},'cognition':{'autonomous_goals':True,'reflection':True,'rumination_per_year':0}}
        controller=Lifetime(g,q3)
        with patch('devsim.engine.request_json',side_effect=reflect_stub): controller._after_received('a','experience')
        assert len(g.agent('a')['goals'])==2 and len(g.state['runtime']['dynamic_opportunities'])==2
        g.state['runtime']['current_day']=g.day;g.save(checkpoint);restored=Engine.load(checkpoint)
        Lifetime(restored,q3);assert restored.state==g.state
        checks.append('self-set evidence-linked goals become canonical scheduled opportunities without claiming achievements')
    # Transfer money conserves the selected resource; decay is analytic/read-only.
    t=world();t.schedule('trade',0,'A pays B.',{});t.advance(0)
    life_policy.apply_effects(t,{'transfers':[{'from':'a','to':'b','resource':'money','amount':3}]},'trade')
    assert t.agent('a')['resources']['money']==7 and t.agent('b')['resources']['money']==3
    before=deepcopy(t.state);reject(lambda:life_policy.apply_effects(t,{'transfers':[{'from':'a','to':'b','resource':'money','amount':8}]},'trade'))
    assert t.state==before
    society.configure(t,{'closeness_half_life_days':10});t.relate('a','b','friend',closeness=.8)
    t.agent('a')['relationships']['b']['last_interaction_day']=0;t.advance(10)
    before=deepcopy(t.state);assert abs(t.context('a','B')['relationships']['b']['closeness']-.4)<1e-9 and t.state==before
    checks+=['conserved transfer ledger and overdraw rollback','relationship decay uses elapsed time and context remains pure']
    # SQLite snapshots reconstruct the same immutable observation cache and
    # expose normalized owner-scoped provenance for controller audits only.
    from devsim.graph_store import audit_private_graph
    with TemporaryDirectory() as directory:
        path=Path(directory)/'world.sqlite';r.save(path);restored=Engine.load(path)
        assert restored.state==r.state and restored.world.observations==r.world.observations
        graph=audit_private_graph(path,'a')
        assert graph['nodes'] and all(':a:' in n['id'] for n in graph['nodes'])
        assert not audit_private_graph(path,'not-an-owner')['nodes']
        checks+=['SQLite graph checkpoint restores identical state and immutable observations','normalized graph audits are owner-scoped and preserve provenance']
        # Failure at completion retains the committed intention and can retry
        # without redoing the proposal or spending costs twice.
        pending=world();q=policy();controller=Lifetime(pending,q)
        due=pending.state['runtime']['next_opportunities']['activity']
        def transport_stub(system,context,api,model,max_tokens=600):
            if 'new_observation' in context:
                return {'meaning':'I completed a small step.','valence':.2,'arousal':.2,'importance':.5,'confidence':.7}
            return {'action':'Work on the step.','action_id':'work','speech':'','goal_id':None,'plan':[],'memory_ids':[]}
        with patch('devsim.engine.request_json',side_effect=transport_stub): controller.run(due+1/24,path)
        before=deepcopy(pending.state)
        with patch.object(Engine,'appraise',side_effect=RuntimeError('fixture transport failed')):
            reject(lambda:controller.run(due+2/24+1e-6,path))
        assert pending.state==before and pending.state['actions'][0]['status']=='intended'
        pending=Engine.load(path)
        with patch('devsim.engine.request_json',side_effect=transport_stub): Lifetime(pending,q).run(due+2/24+1e-6,path)
        assert len(pending.state['actions'])==1 and pending.agent('a')['resources']['money']==9
        checks.append('completion failure retries saved intention without duplicate decisions or charges')
        # Competing exogenous hazards remain reproducible over checkpoints.
        hazard_policy={'sampling':'event_driven','opportunities':[],'world_hazards':[{
            'id':'change','actor':'a','rate_per_year':20,'description':'A world change occurs.','observations':{},
            'effects':{'facts':{'a':{'role':'participant'}}},'once':True}]}
        whole=world();split=world();Lifetime(whole,hazard_policy,scripted=True).run(365)
        Lifetime(split,hazard_policy,scripted=True).run(30,path);split=Engine.load(path)
        Lifetime(split,hazard_policy,scripted=True).run(365)
        assert split.state==whole.state and whole.state['entities']['a']['facts']['role']=='participant'
        checks.append('age-window world hazards persist and resume without resampling')
    # Optional appraisal references/cues stay in the listener's received scope.
    a=world();cognition.configure(a,{'reference_resolution':True,'detail_threshold':.9})
    a.schedule('old',0,'A has a prior experience.',{'a':{'text':'I was uncertain about a colleague.','source':'direct','meaning':'I felt uncertain.'}});a.advance(0)
    a.agent('a')['memory_meta']['old']['summary']='I was uncertain about a colleague.'
    a.relate('a','b','coworker');a.advance(1000)
    def appraise_stub(system,context,api,model,max_tokens=600):
        return {'meaning':'An account reminded me of uncertainty.','valence':-.1,'arousal':.2,'importance':.5,'confidence':.5,
            'mentions':[{'span':'Sam','candidate_ids':['b']}],'reminded_memory_ids':['old']}
    # Supply an explicit semantic focus to make the retained gist available in
    # this paraphrased incoming context; this is a fixture, not learned accuracy.
    a.agent('a')['retrieval_focus']={'day':a.day,'situation':'Sam described a colleague.','ids':['old']}
    with patch('devsim.engine.request_json',side_effect=appraise_stub):
        observed=a.appraise('a',{'text':'Sam described a colleague.','source':'b','kind':'testimony'})
    a.schedule('reminder',a.day,'A hears the account.',{'a':observed});a.advance(a.day)
    assert a.agent('a')['recall_log'][-1]['memory']=='old' and not a.agent('a')['recall_log'][-1]['rehearsed']
    assert not a.agent('a')['relationships']['b']['firsthand']
    checks.append('model-inferred heard reminders trigger gist-safe recall without fabricated meetings')
    # A repeated ambiguous name preserves an earlier explicit binding history.
    repeated={'text':'Sam spoke again.','source':'b','kind':'testimony'}
    repeated['mentions']=references.normalize(r,'a',repeated,[{'span':'Sam','candidate_ids':[]}])
    r.schedule('repeat-name',r.day,'A hears the same name again.',{'a':repeated});r.advance(r.day)
    assert r.agent('a')['unresolved_references'][rid]['binding_evidence']=='identify'
    assert r.agent('a')['unresolved_references'][rid]['versions']
    checks.append('repeated ambiguous mentions preserve explicit binding provenance and versions')
    # Never tokenize against or fall back to a different served model.
    from io import BytesIO
    from devsim.engine import request_json
    data=BytesIO(json.dumps({'data':[{'id':'other','meta':{'n_ctx':8192}}]}).encode())
    with patch('devsim.engine.urlopen',return_value=data) as transport:
        reject(lambda:request_json('system',{'identity':{'id':'a'}},'http://fixture','missing'))
        assert transport.call_count==1
    checks.append('missing selected model fails before tokenization or inference with no fallback')
    result={'passed':True,'scope':'synthetic engineering checks; no calibrated human or demographic prediction','checks':checks}
    RESULTS_DIR.joinpath('complete-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
