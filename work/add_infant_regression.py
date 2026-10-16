from pathlib import Path
p=Path('outputs/agent_engine/check_situation.py');s=p.read_text()
marker="    result = {'passed': True, 'scope': 'engineering only; stubbed API',"
extra="""    # Infant capability limits apply upstream of the action selector. Model
    # prose cannot introduce school/work/puzzle triggers through generated CAPS.
    import expression, situation
    child = Engine()
    child.entity('baby','Baby');child.materialize('baby',before,birth_day=0)
    expression.configure(child,{'age_appropriate_actions':True})
    raw = {'rules':[{'id':f'b{i}', 'trigger_id':key, 'reaction_id':'orient',
                     'state_modifiers':{'E':1}} for i,key in enumerate(situation.INFANT_TRIGGERS)]}
    with patch('engine.request_json',return_value=raw) as generator:
        rules = child.generate_signatures('baby')
        assert generator.call_args.args[1]['developmental_capabilities']['band']=='infant'
        assert all(r['trigger_context'] in [v[1] for v in situation.INFANT_TRIGGERS.values()] for r in rules)
        child.generate_signatures('baby');assert generator.call_count==1
    bad=deepcopy(raw);bad['rules'][0]['trigger_id']='solve-riddle'
    reject(lambda:situation.infant_rules(bad))
    bad=deepcopy(raw);bad['rules'][0]['narrative_shift']='Run a company'
    reject(lambda:situation.infant_rules(bad))
    saved_child=deepcopy(child.state)
    with patch('engine.request_json',return_value=bad):
        child.agent('baby')['caps_provenance']['capability_band']='legacy-unknown'
        retry_state=deepcopy(child.state)
        reject(lambda:child.generate_signatures('baby'))
        assert child.state==retry_state
    child.state=saved_child
    with TemporaryDirectory() as directory:
        file=Path(directory)/'child.json';child.save(file);child=Engine.load(file)
        for age,band in [(2,'early-childhood'),(5,'child')]:
            child.advance(age*365.25)
            with patch('engine.request_json',side_effect=stub) as generator:
                child.generate_signatures('baby');child.generate_signatures('baby')
                assert generator.call_count==1
            assert child.agent('baby')['caps_provenance']['capability_band']==band
        assert len(child.agent('baby')['caps_versions'])==2
        assert child.agent('baby')['facets']==before
"""
s=s.replace(marker,extra+marker)
s=s.replace("'failed construal rolls back entire event']}","'failed construal rolls back entire event',\n                         'infant signatures use bounded sensory trigger and nonverbal reaction catalogs',\n                         'invalid infant competence is rejected before state mutation',\n                         'capability transitions refresh at ages two and five after checkpoint restore']}")
p.write_text(s)
