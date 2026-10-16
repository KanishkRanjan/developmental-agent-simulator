"""Automatic opportunity -> decision -> outcome -> development controller.

Usage: python lifetime.py WORLD --policy POLICY --until-day DAY --save OUTPUT
The default decision/appraisal provider is the local 27B API. --scripted is
an explicitly labeled, deterministic engineering demonstration, not an LLM.
Scenario rates and causal coefficients are user-visible assumptions.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from math import exp, log
from pathlib import Path
from random import Random

from .engine import Engine, FACET_NAMES, number
from . import development
from . import cognition
from . import life_policy
from . import goal_plans
from . import household
class Lifetime:
    def __init__(self, engine, policy, *, scripted=False, api='http://127.0.0.1:8081', model='local'):
        self.engine = engine
        self.policy = deepcopy(policy)
        self.policy['opportunities'].extend(deepcopy(engine.state.get('runtime', {}).get('dynamic_opportunities', [])))
        self.policy.setdefault('world_hazards',[]).extend(deepcopy(engine.state.get('runtime',{}).get('dynamic_hazards',[])))
        self.scripted = scripted
        self.api, self.model = api, model
        self.sampling = policy.get('sampling', 'legacy_discrete')
        if self.sampling not in ('event_driven', 'legacy_discrete'):
            raise ValueError('Unsupported opportunity sampling mode')
        if self.sampling == 'legacy_discrete':
            number(policy['step_days'], 0.01, 36525, 'step_days')
        self.fingerprint = sha256(json.dumps(policy, sort_keys=True, allow_nan=False).encode()).hexdigest()
        ids = set()
        for opportunity in self.policy['opportunities']:
            if opportunity['id'].startswith('@'):
                raise ValueError('Opportunity ids beginning @ are reserved')
            if opportunity['id'] in ids:
                raise ValueError('Opportunity ids must be unique')
            ids.add(opportunity['id'])
            engine.agent(opportunity['actor'])
            number(opportunity['rate_per_year'], 0, 10000, 'rate_per_year')
            if 'rate_modifiers' in opportunity:
                modifiers = opportunity['rate_modifiers']
                if self.sampling != 'event_driven' or not isinstance(modifiers, list) or len(modifiers) > 8:
                    raise ValueError('State-dependent rates require event-driven sampling and up to eight modifiers')
                number(opportunity['rate_cap_per_year'], opportunity['rate_per_year'], 10000, 'rate cap')
                for modifier in modifiers:
                    if not isinstance(modifier, dict) or set(modifier) - {'feature','coefficient','scale','window_days','action_option','facet'}:
                        raise ValueError('Unsupported rate modifier')
                    if modifier.get('feature') not in ('resolved_actions','goal_progress','facet'):
                        raise ValueError('Unknown rate feature')
                    number(modifier.get('coefficient'), -5, 5, 'rate coefficient')
                    number(modifier.get('scale', 1), 1e-6, 1e6, 'rate feature scale')
                    number(modifier.get('window_days', 365.25), 1e-6, 1e8, 'rate feature window')
                    if modifier['feature'] == 'facet' and modifier.get('facet') not in FACET_NAMES:
                        raise ValueError('Unknown rate facet')
            number(opportunity.get('min_age', 0), 0, 1e6, 'min_age')
            number(opportunity.get('max_age', 1000), opportunity.get('min_age', 0), 1e6, 'max_age')
            if not opportunity['options'] or len({a['id'] for a in opportunity['options']}) != len(opportunity['options']):
                raise ValueError('Opportunity needs distinct action options')
            if opportunity.get('goal_id') is not None and opportunity['goal_id'] not in engine.agent(opportunity['actor'])['goals'] and not opportunity.get('new_goal'):
                raise ValueError('Opportunity refers to unknown goal')
            for option in opportunity['options']:
                if 'room_contact' in option and (not isinstance(option['room_contact'],bool) or not option.get('contact') or 'household' not in policy):
                    raise ValueError('room_contact requires a boolean, contact and household policy')
                if 'conversation' in option:
                    talk=option['conversation']
                    if 'household' not in policy or not option.get('contact') or not isinstance(talk,dict) or \
                            set(talk)-{'topic','max_turns','questions'} or not isinstance(talk.get('topic'),str) or not talk['topic'].strip():
                        raise ValueError('An option conversation needs a household policy, a contact and a topic')
                    household.validate_interview({'participants':[opportunity['actor'],option['contact']],**talk,
                        **({'interviewer':opportunity['actor']} if 'questions' in talk else {})})
                if 'requires' in option:
                    if not isinstance(option['requires'],dict) or set(option['requires'])-{'alive','facts'}:
                        raise ValueError('Action eligibility supports alive/fact prerequisites')
                    engine._validate_event({'id':'validation-only','day':engine.day,'description':'',
                        'observations':{},'facts':{},'outcomes':{},'requires':option['requires']})
                number(option.get('duration_hours', 0), 0, 24, 'action duration hours')
                number(option.get('contact_duration_hours',option.get('duration_hours',0)),0,24,'contact duration')
                for cost in option.get('costs', {}).values():
                    number(cost, 0, 1e9, 'action resource cost')
                for field in ('effects_success', 'effects_failure'):
                    if field in option:
                        life_policy.validate_effects(engine, option[field], replay=True)
                if option.get('goal_id') is not None and option['goal_id'] not in engine.agent(opportunity['actor'])['goals']:
                    raise ValueError('Action option refers to an unknown competing goal')
                number(option['success_probability'], 0, 1, 'success_probability')
                for field in ('valence_success', 'valence_failure'):
                    number(option[field], -1, 1, field)
                number(option.get('arousal', 0.2), 0, 1, 'arousal')
                number(option.get('importance', 0.5), 0, 1, 'importance')
                number(option.get('progress_gain', 0), 0, 1, 'progress_gain')
                if option.get('contact') is not None:
                    if option['contact'] not in engine.state['entities']:
                        raise ValueError('Contact must have a committed identity')
                    contact_birth = engine.state['entities'][option['contact']]['facts'].get('birth_day')
                    if contact_birth is not None:
                        number(contact_birth, -1e8, 1e8, 'contact birth day')
                    if option['contact'] == opportunity['actor']:
                        raise ValueError('Contact must be another actor')
                if 'caregiving' in option:
                    if not isinstance(option['caregiving'], dict) or set(option['caregiving']) != {'responsiveness', 'acceptance'}:
                        raise ValueError('Caregiving option needs responsiveness and acceptance')
                    if option.get('contact') not in engine.state['entities'][opportunity['actor']]['facts'].get('caregivers', []):
                        raise ValueError('Caregiving option requires a committed caregiver contact')
                    for value in option['caregiving'].values():
                        number(value, 0, 1, 'caregiving')
                if 'contact_responses' in option:
                    replies = option['contact_responses']
                    if option.get('contact') is None or not isinstance(replies,list) or not replies or len({r['id'] for r in replies}) != len(replies):
                        raise ValueError('Contact responses need a contact and distinct action ids')
                    for reply in replies:
                        for field in ('duration_hours','activity_duration_hours'):
                            if field in reply: number(reply[field],0,24,'response duration')
                        for field in ('id','label','success_text','failure_text','contact_text'):
                            if not isinstance(reply.get(field),str) or not reply[field].strip():
                                raise ValueError('Contact response needs canonical behavior/outcome text')
                        number(reply.get('success_multiplier',1),0,2,'contact success multiplier')
                        if 'caregiving' in reply:
                            if 'caregiving' not in option or set(reply['caregiving']) != {'responsiveness','acceptance'}:
                                raise ValueError('Contact caregiving response needs both estimates and a caregiver option')
                            for value in reply['caregiving'].values():
                                number(value,0,1,'contact caregiving estimate')
                for facet, delta in option.get('development_success', {}).items():
                    if facet not in FACET_NAMES:
                        raise ValueError('Unknown developmental facet')
                    number(delta, -100, 100, facet)
        number(policy.get('max_trait_change_per_year', 1.0), 0, 100, 'trait rate')
        if 'situational_personality' in policy:
            settings = policy['situational_personality']
            if not isinstance(settings, dict) or set(settings) - {'recovery_half_life_days'}:
                raise ValueError('Invalid situational personality policy')
            number(settings.get('recovery_half_life_days', 1.0), 1e-6, 36525, 'situational recovery half life')
        developmental = policy.get('development')
        if developmental is not None:
            if not isinstance(developmental, dict) or set(developmental) - {'maturation', 'crystallization'}:
                raise ValueError('Invalid development policy')
            development.validate_trajectory(developmental.get('maturation', {}))
            crystal = developmental.get('crystallization', {})
            if not isinstance(crystal, dict) or set(crystal) - {'rate', 'minimum_days', 'max_change_per_year'}:
                raise ValueError('Invalid crystallization policy')
            number(crystal.get('rate', .005), 0, .1, 'crystallization rate')
            number(crystal.get('max_change_per_year', .5), 0, 10, 'crystallization bound')
            minimum = crystal.get('minimum_days', 3)
            if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 2:
                raise ValueError('Crystallization needs at least two independent days')
            for agent in engine.state['agents'].values():
                if 'developmental_model' in agent and agent['developmental_model']['maturation'] != developmental.get('maturation', {}):
                    raise ValueError('Existing agent has a different maturation policy')
        templates = policy.get('newborn_opportunities', [])
        if not isinstance(templates,list) or len({t['id'] for t in templates})!=len(templates):
            raise ValueError('Newborn opportunity templates require distinct ids')
        if templates and self.sampling!='event_driven':
            raise ValueError('Generational opportunities require event-driven sampling')
        for template in templates:
            if template.get('actor') != '$actor':
                raise ValueError('Newborn template actor must be $actor')
        world_rules = policy.get('world_events', [])
        hazards=self.policy['world_hazards']
        if not isinstance(hazards,list) or len({r['id'] for r in hazards})!=len(hazards):
            raise ValueError('World hazards need unique ids')
        for rule in hazards:
            engine.agent(rule['actor'])
            number(rule['rate_per_year'],0,10000,'world hazard rate')
            number(rule.get('min_age',0),0,1e6,'hazard min age')
            number(rule.get('max_age',1000),rule.get('min_age',0),1e6,'hazard max age')
            if 'once' in rule and not isinstance(rule['once'],bool): raise ValueError('Hazard once flag must be boolean')
        if not isinstance(world_rules, list) or len({r['id'] for r in world_rules}) != len(world_rules):
            raise ValueError('World event rules require unique ids')
        if (world_rules or hazards or 'cognition' in policy) and self.sampling != 'event_driven':
            raise ValueError('World events and autonomous cognition require event-driven sampling')
        if policy.get('planning',{}).get('calendar_mode')=='elapsed' and self.sampling!='event_driven':
            raise ValueError('Elapsed activities require event-driven sampling')
        if 'household' in policy:
            if self.sampling!='event_driven': raise ValueError('Household conversations require event-driven sampling')
            household.validate(engine,policy['household'])
        for rule in [*world_rules,*hazards]:
            number(rule.get('day',engine.day), 0, 1e8, 'world event day')
            event = {'id': rule['id'], 'day': rule.get('day',engine.day), 'description': rule['description'],
                     'observations': rule.get('observations', {}), 'facts': {}, 'outcomes': {},
                     'requires': rule.get('requires', {})}
            engine._validate_event(event)
            if event['requires'].get('action') or event['requires'].get('actions'):
                raise ValueError('Exogenous world rules cannot depend on future action ids')
            life_policy.validate_effects(engine, rule.get('effects', {}), replay=True)
        # Validate settings against a disposable config before creating runtime.
        from types import SimpleNamespace
        probe = SimpleNamespace(state={'config':deepcopy(engine.state['config'])})
        if 'cognition' in policy:
            cognition.configure(probe, policy['cognition'])
        if 'planning' in policy:
            life_policy.configure(probe, policy['planning'])
        if 'expression' in policy:
            from . import expression
            expression.configure(probe,policy['expression'])
        if 'society' in policy:
            from . import society
            society.configure(probe,policy['society'])
        saved = engine.state.get('runtime')
        if saved:
            if saved['policy_fingerprint'] != self.fingerprint or saved['scripted'] != scripted:
                raise ValueError('Resume requires the same policy and decision provider')
            if saved['current_day'] != engine.day:
                raise ValueError('Engine advanced outside this controller; resume from its saved checkpoint')
        else:
            if developmental is not None:
                for owner, agent in engine.state['agents'].items():
                    if agent['alive']:
                        engine.configure_development(owner, developmental.get('maturation', {}))
            engine.state['runtime'] = {'policy_fingerprint': self.fingerprint, 'scripted': scripted,
                'start_day': engine.day, 'current_day': engine.day,
                'next_tick': engine.day + policy['step_days'] if self.sampling == 'legacy_discrete' else None,
                'tick': 0, 'trace': [], 'trait_budget': {}}
            if self.sampling == 'event_driven':
                engine.state['runtime']['opportunity_counts'] = {o['id']: 0 for o in policy['opportunities']}
                engine.state['runtime']['next_opportunities'] = {
                    o['id']: self._next_opportunity(o, engine.day, 0) for o in policy['opportunities']}
        if 'cognition' in policy:
            cognition.configure(engine, policy['cognition'])
        if 'planning' in policy:
            life_policy.configure(engine, policy['planning'])
        if 'expression' in policy:
            expression.configure(engine,policy['expression'])
        if 'society' in policy:
            society.configure(engine,policy['society'])
        if self.sampling == 'event_driven':
            runtime = engine.state['runtime']
            if 'household' in policy:
                household.initialize(engine,policy['household'])
            runtime.setdefault('next_world_events', {r['id']: r['day'] for r in world_rules if r['day'] >= engine.day})
            runtime.setdefault('background_counts', {})
            runtime.setdefault('next_background', {})
            runtime.setdefault('pending_activities', {})
            runtime.setdefault('hazard_counts',{r['id']:0 for r in hazards})
            runtime.setdefault('next_hazards',{r['id']:self._next_opportunity(
                {**r,'id':'@hazard:'+r['id']},engine.day,0) for r in hazards})
            self._ensure_background()
            self._ensure_goal_opportunities()

    def _register_dynamic(self, opportunity):
        engine=self.engine;runtime=engine.state['runtime']
        if any(o['id']==opportunity['id'] for o in self.policy['opportunities']):
            raise ValueError('Generated opportunity id already exists')
        sandbox=Engine(engine.state['seed']);sandbox.state=deepcopy(engine.state);sandbox.state.pop('runtime',None)
        Lifetime(sandbox,{'sampling':'event_driven','opportunities':[opportunity],
            **({'planning':self.policy['planning']} if 'planning' in self.policy else {})},scripted=self.scripted)
        self.policy['opportunities'].append(opportunity)
        runtime.setdefault('dynamic_opportunities',[]).append(deepcopy(opportunity))
        runtime['opportunity_counts'][opportunity['id']]=0
        runtime['next_opportunities'][opportunity['id']]=self._next_opportunity(opportunity,engine.day,0)

    def _ensure_goal_opportunities(self):
        template=self.policy.get('goal_opportunity')
        if template is None: return
        if self.sampling!='event_driven' or template.get('actor')!='$actor' or template.get('goal_id')!='$goal':
            raise ValueError('Goal opportunity template requires event-driven $actor and $goal')
        for owner,agent in self.engine.state['agents'].items():
            for goal_id,goal in agent['goals'].items():
                key=f'{owner}:goal:{goal_id}'
                if goal['status']!='active' or not agent['alive'] or any(o['id']==key for o in self.policy['opportunities']): continue
                def substitute(value):
                    if isinstance(value,str): return value.replace('$goal_description',goal['description']).replace('$goal',goal_id).replace('$actor',owner)
                    if isinstance(value,list): return [substitute(v) for v in value]
                    if isinstance(value,dict): return {substitute(k):substitute(v) for k,v in value.items()}
                    return value
                opportunity=substitute(template);opportunity['id']=key
                self._register_dynamic(opportunity)

    def _ensure_background(self):
        runtime = self.engine.state['runtime']
        rate = self.policy.get('cognition', {}).get('rumination_per_year', 0)
        if not rate:
            return
        for owner, agent in self.engine.state['agents'].items():
            if owner not in runtime['next_background'] and agent['alive'] and agent['memory_meta']:
                runtime['background_counts'][owner] = 0
                runtime['next_background'][owner] = self.engine.day + self.rng('rumination', owner, 0).expovariate(rate / 365.25)

    def _register_births(self, effects):
        """Instantiate declared life opportunities for newborns, not silent lives.

        Templates refer to $actor and optional $caregiver. Missing caregiving
        context skips that template rather than manufacturing a parent.
        """
        engine = self.engine
        runtime = engine.state['runtime']
        templates = self.policy.get('newborn_opportunities', [])
        for birth in effects.get('births', []):
            owner = birth['id']
            if 'development' in self.policy:
                engine.configure_development(owner,self.policy['development'].get('maturation',{}))
            caregivers = engine.state['entities'][owner]['facts'].get('caregivers', [])
            def substitute(value):
                if isinstance(value,str):
                    return value.replace('$actor',owner).replace('$caregiver',caregivers[0] if caregivers else '$caregiver')
                if isinstance(value,list): return [substitute(v) for v in value]
                if isinstance(value,dict): return {substitute(k):substitute(v) for k,v in value.items()}
                return value
            for template in templates:
                if '$caregiver' in json.dumps(template) and not caregivers:
                    continue
                opportunity = substitute(template)
                if '$actor' not in template['id']:
                    opportunity['id'] = owner + ':' + template['id']
                self._register_dynamic(opportunity)
            for template in self.policy.get('newborn_hazards',[]):
                rule=substitute(template)
                if '$actor' not in template['id']: rule['id']=owner+':'+template['id']
                if rule.get('actor')!=owner: raise ValueError('Newborn hazard actor must be $actor')
                sandbox=Engine(engine.state['seed']);sandbox.state=deepcopy(engine.state);sandbox.state.pop('runtime',None)
                Lifetime(sandbox,{'sampling':'event_driven','opportunities':[],'world_hazards':[rule]},scripted=self.scripted)
                self.policy['world_hazards'].append(rule)
                runtime.setdefault('dynamic_hazards',[]).append(deepcopy(rule))
                runtime['hazard_counts'][rule['id']]=0
                runtime['next_hazards'][rule['id']]=self._next_opportunity({**rule,'id':'@hazard:'+rule['id']},engine.day,0)

    def rng(self, *keys):
        seed = sha256(json.dumps([self.engine.state['seed'], *keys]).encode()).digest()
        return Random(int.from_bytes(seed, 'big'))

    def run(self, until, checkpoint=None):
        engine = self.engine
        number(until, engine.day, 1e8, 'until')
        if self.sampling == 'event_driven':
            return self._run_events(until, checkpoint)
        runtime = engine.state['runtime']
        while runtime['next_tick'] <= until:
            # Roll back an entire tick on API/parsing failure, including earlier agents.
            backup = deepcopy(engine.state)
            try:
                engine.advance(runtime['next_tick'])
                for opportunity in self.policy['opportunities']:
                    self.process(opportunity, runtime['tick'])
                runtime['trace'].append({'tick': runtime['tick'], 'day': engine.day, 'status': 'completed',
                                         'provider': 'scripted_engineering_fixture' if self.scripted else 'local_model_api'})
                runtime['tick'] += 1
                runtime['next_tick'] += self.policy['step_days']
                runtime['current_day'] = engine.day
                if checkpoint:
                    engine.save(checkpoint)
            except Exception:
                # Reconstruct observation cache from the pre-tick snapshot without losing prior ticks.
                engine.state = backup
                engine.world = self._world_from_state(backup)
                if checkpoint:
                    engine.save(checkpoint)
                raise
        engine.advance(until)
        runtime['current_day'] = engine.day
        if checkpoint:
            engine.save(checkpoint)

    def _next_opportunity(self, opportunity, after, sequence):
        agent = self.engine.agent(opportunity['actor'])
        if not agent['alive'] or opportunity['rate_per_year'] == 0:
            return None
        start = max(after, agent['birth_day'] + opportunity.get('min_age', 0) * 365.25)
        stop = agent['birth_day'] + opportunity.get('max_age', 1000) * 365.25
        if start >= stop:
            return None
        rng = self.rng('waiting-time', opportunity['id'], sequence)
        proposal_rate = opportunity.get('rate_cap_per_year', opportunity['rate_per_year']) if 'rate_modifiers' in opportunity else opportunity['rate_per_year']
        if proposal_rate == 0:
            return None
        candidate = start + rng.expovariate(proposal_rate / 365.25)
        return candidate if candidate < stop else None

    def current_rate(self, opportunity):
        """Scenario log-rate policy, clipped to a declared thinning envelope."""
        base = opportunity['rate_per_year']
        if not base or 'rate_modifiers' not in opportunity:
            return base
        engine = self.engine
        agent = engine.agent(opportunity['actor'])
        predictor = 0.0
        for modifier in opportunity['rate_modifiers']:
            feature = modifier['feature']
            if feature == 'resolved_actions':
                value = sum(1 for action in engine.state['actions'] if action['owner'] == opportunity['actor'] and
                            action['status'] == 'resolved' and engine.day - action['day'] <= modifier.get('window_days',365.25) and
                            (modifier.get('action_option') is None or action['decision'].get('action_id') == modifier['action_option']))
            elif feature == 'goal_progress':
                value = agent['goals'].get(opportunity.get('goal_id'), {}).get('progress', 0)
            else:
                value = (agent['facets'][modifier['facet']] - 50) / 50
            predictor += modifier['coefficient'] * value / modifier.get('scale',1)
        return exp(min(log(opportunity['rate_cap_per_year']), max(-700, log(base) + predictor)))

    def _run_events(self, until, checkpoint):
        engine = self.engine
        while True:
            runtime = engine.state['runtime']
            queue = [(day, 'opportunity', key) for key, day in runtime['next_opportunities'].items() if day is not None and day <= until]
            queue += [(day, 'background', key) for key, day in runtime.get('next_background', {}).items() if day is not None and day <= until]
            queue += [(day, 'world', key) for key, day in runtime.get('next_world_events', {}).items() if day is not None and day <= until]
            queue += [(activity['day'],'completion',key) for key,activity in runtime.get('pending_activities',{}).items() if activity['day']<=until]
            queue += [(day,'hazard',key) for key,day in runtime.get('next_hazards',{}).items() if day is not None and day<=until]
            queue += [(day,'move',key) for key,day in runtime.get('household_moves',{}).items() if day is not None and day<=until]
            queue += [(t['day'],'trip',key) for key,t in runtime.get('trips',{}).items() if t['day']<=until]
            queue += [(g['next_day'],'group',key) for key,g in runtime.get('group_meetings',{}).items() if g['next_day']<=until]
            queue += [(i['next_day'],'invite',key) for key,i in runtime.get('invitations',{}).items()
                      if i['next_day'] is not None and i['next_day']<=until]
            queue += [(s['next_day'],'conversation',key) for key,s in runtime.get('conversations',{}).items()
                      if s['next_day'] is not None and s['next_day']<=until]
            if not queue:
                break
            # Commit simultaneous world transitions before cognitive/choice events.
            day, kind, key = min(queue,key=lambda item:(item[0],
                {'world':0,'hazard':0,'move':1,'trip':1,'background':2,'completion':3,'group':3,'invite':3,'conversation':4,
                 'opportunity':5}[item[1]],item[2],item[1]))
            backup = deepcopy(engine.state)
            try:
                engine.advance(day)
                if kind != 'opportunity':
                    self._process_background_or_world(kind, key)
                    runtime['current_day'] = engine.day
                    if checkpoint:
                        engine.save(checkpoint)
                    continue
                opportunity = next(o for o in self.policy['opportunities'] if o['id'] == key)
                self.process(opportunity, runtime['tick'], occurrence=True)
                runtime['opportunity_counts'][key] += 1
                agent = engine.agent(opportunity['actor'])
                completed = (opportunity.get('goal_id') is not None and
                             agent['goals'].get(opportunity['goal_id'], {}).get('status') in ('completed', 'abandoned'))
                runtime['next_opportunities'][key] = None if completed else self._next_opportunity(
                    opportunity, day, runtime['opportunity_counts'][key])
                runtime['trace'].append({'event_index': runtime['tick'], 'day': day,
                    'status': 'completed', 'sampling': 'bounded_thinning' if 'rate_modifiers' in opportunity else 'piecewise_constant_poisson',
                    'provider': 'scripted_engineering_fixture' if self.scripted else 'local_model_api'})
                runtime['tick'] += 1
                runtime['current_day'] = engine.day
                if checkpoint:
                    engine.save(checkpoint)
            except Exception:
                engine.state = backup
                engine.world = self._world_from_state(backup)
                self.policy['opportunities'] = [o for o in self.policy['opportunities']
                    if o['id'] in backup['runtime']['next_opportunities']]
                self.policy['world_hazards']=[r for r in self.policy['world_hazards'] if r['id'] in backup['runtime'].get('next_hazards',{})]
                if checkpoint:
                    engine.save(checkpoint)
                raise
        engine.advance(until)
        engine.state['runtime']['current_day'] = engine.day
        if checkpoint:
            engine.save(checkpoint)

    def _process_background_or_world(self, kind, key):
        engine = self.engine
        runtime = engine.state['runtime']
        if kind=='move':
            rule=next(r for r in self.policy['household'].get('moves',[]) if r['id']==key)
            household.move(self,rule['actor'],rule['room'],'@move:'+key)
            runtime['household_moves'][key]=None
            return
        if kind=='conversation':
            household.step(self,key)
            return
        if kind=='trip':
            household.trip(self,key)
            return
        if kind=='group':
            household.meet(self,key)
            return
        if kind=='invite':
            household.invite(self,key)
            return
        if kind=='completion':
            activity=runtime['pending_activities'][key]
            participants=list(activity['reservations'])
            valid=all(engine.agent(p)['alive'] for p in participants)
            selected=activity['selected']
            valid &= all(engine.agent(a)['alive'] for a in selected.get('requires',{}).get('alive',[]))
            valid &= all(all(engine.state['entities'][who]['facts'].get(k)==v for k,v in facts.items())
                         for who,facts in selected.get('requires',{}).get('facts',{}).items())
            valid &= all(engine.agent(activity['owner']).get('resources',{}).get(k,0)>=v for k,v in selected.get('costs',{}).items())
            if selected.get('room_contact'):
                valid &= household.present(engine,selected['contact'],household.location(engine,activity['owner']))
            if activity['goal_id'] is not None:
                valid &= engine.agent(activity['owner'])['goals'].get(activity['goal_id'],{}).get('status')=='active'
            if valid:
                self._resolve_activity(activity)
            else:
                from .calendar_time import finish
                for owner in participants:
                    finish(engine,owner,key,cancel=True)
                binding=activity.get('plan_binding')
                if binding:
                    goal_plans.request_replan(engine.agent(activity['owner'])['goals'][binding['goal_id']])
                for action in engine.state['actions']:
                    if action['id'] in (key+'-action',key+'-contact-action'):
                        action.update(status='cancelled',cancellation_day=engine.day)
                runtime['trace'].append({'kind':'cancelled_activity','id':key,'day':engine.day,
                                        'reason':'participant, prerequisite or resource unavailable at completion'})
            del runtime['pending_activities'][key]
            return
        if kind == 'background':
            count = runtime['background_counts'][key]
            mid = cognition.ruminate(engine, key, f'{key}:autonomous:{count}',
                self.policy['cognition'].get('rumination_minimum_gap_days', 1))
            runtime['background_counts'][key] += 1
            rate = self.policy['cognition'].get('rumination_per_year', 0)
            runtime['next_background'][key] = (engine.day + self.rng('rumination', key, count+1).expovariate(rate/365.25)
                if rate and engine.agent(key)['alive'] else None)
            runtime['trace'].append({'kind':'autonomous_recall','owner':key,'day':engine.day,'memory':mid})
            return
        hazard=kind=='hazard'
        rule = next(r for r in self.policy.get('world_hazards' if hazard else 'world_events',[]) if r['id'] == key)
        if hazard:
            rule=deepcopy(rule)
            rule['requires']={**rule.get('requires',{}),'alive':list(dict.fromkeys([rule['actor'],*rule.get('requires',{}).get('alive',[])]))}
        observations = deepcopy(rule.get('observations', {}))
        if hazard:
            observations={a:o for a,o in observations.items() if engine.agent(a)['alive']}
        # Check eligibility before asking any agent to appraise an impossible event.
        eligible = all(engine.agent(a)['alive'] for a in rule.get('requires', {}).get('alive', []))
        eligible &= all(engine.agent(a)['alive'] for a in observations)
        eligible &= all(all(engine.state['entities'][who]['facts'].get(k) == v for k,v in facts.items())
            for who,facts in rule.get('requires',{}).get('facts',{}).items())
        if eligible and not self.scripted:
            observations = {a:engine.appraise(a,o,api=self.api,model=self.model) for a,o in observations.items()}
        event_id = ('@hazard:'+key+':'+str(runtime['hazard_counts'][key])) if hazard else '@world:'+key
        engine.schedule(event_id,engine.day,rule['description'],observations,requires=rule.get('requires'))
        engine.advance(engine.day)
        if eligible:
            effects = rule.get('effects',{})
            life_policy.apply_effects(engine,effects,event_id)
            self._register_births(effects)
            for actor in observations:
                self._after_received(actor,event_id)
            self._ensure_background()
        if hazard:
            runtime['hazard_counts'][key]+=1
            runtime['next_hazards'][key]=(None if rule.get('once') and eligible else
                self._next_opportunity({**rule,'id':'@hazard:'+key},engine.day,runtime['hazard_counts'][key]))
        else:
            runtime['next_world_events'][key] = None
        runtime['trace'].append({'kind':'world_transition','id':key,'day':engine.day,'applied':eligible})

    def _after_received(self, owner, event_id):
        if not self.engine.agent(owner)['alive']:
            return
        if not self.scripted and self.policy.get('cognition',{}).get('reflection',False):
            cognition.reflect(self.engine,owner,event_id,api=self.api,model=self.model)
        self._ensure_goal_opportunities()

    def _before_decision(self, owner, situation):
        backgrounds=self.policy.get('background_expansion',{})
        background = backgrounds.get(owner,backgrounds.get('default'))
        age=(self.engine.day-self.engine.agent(owner)['birth_day'])/365.25
        if background and not self.scripted and age>=background.get('min_age',0):
            life_policy.expand_background(self.engine,owner,background,api=self.api,model=self.model)
        if 'cognition' in self.policy and not self.scripted:
            cognition.semantic_recall(self.engine,owner,situation,api=self.api,model=self.model)

    @staticmethod
    def _world_from_state(state):
        from .identity_state_prototype import AgentWorld
        world = AgentWorld()
        for event in state['events']:
            if event['status'] != 'applied':
                continue
            recipients = {owner: Engine._encoded_observation(state, event, owner, obs)
                for owner, obs in event['observations'].items()}
            world.add_event(event['id'], event['day'], event['description'], recipients)
        return world

    def process(self, opportunity, tick, occurrence=False):
        engine = self.engine
        owner = opportunity['actor']
        agent = engine.agent(owner)
        age = (engine.day - agent['birth_day']) / 365.25
        if not agent['alive'] or not opportunity.get('min_age', 0) <= age < opportunity.get('max_age', 1000):
            return
        if not household.available(engine,owner):
            return
        if occurrence and 'rate_modifiers' in opportunity:
            sequence = engine.state['runtime']['opportunity_counts'][opportunity['id']]
            cap = opportunity['rate_cap_per_year']
            if self.rng('thinning', opportunity['id'], sequence).random() * cap >= self.current_rate(opportunity):
                engine.state['runtime']['trace'].append({'day':engine.day,'opportunity':opportunity['id'],
                    'status':'thinned','rate_per_year':self.current_rate(opportunity),'envelope_per_year':cap})
                return
        goal_id = opportunity.get('goal_id')
        if goal_id and goal_id not in agent['goals']:
            goal = opportunity['new_goal']
            engine.goal(owner, goal_id, goal['description'], priority=goal.get('priority', 0.5))
        if goal_id and agent['goals'][goal_id]['status'] != 'active':
            return
        # Discrete-time opportunity process: at most one event per rule per tick.
        # ponytail: large timesteps approximate hazards; reduce step_days for dense opportunities.
        rng = self.rng('opportunity', tick, opportunity['id'])
        if not occurrence:
            probability = 1 - exp(-opportunity['rate_per_year'] * self.policy['step_days'] / 365.25)
            if rng.random() >= probability:
                return
        options = [option for option in opportunity['options'] if option.get('contact') is None or
                   (engine.state['agents'].get(option['contact'], {}).get('alive', True) and
                    engine.state['entities'][option['contact']]['facts'].get('birth_day', -1e8) <= engine.day and
                    household.available(engine,option['contact']) and
                    (not option.get('room_contact',False) or household.present(engine,option['contact'],household.location(engine,owner))))]
        if 'planning' in self.policy or any('requires' in o or 'effects_success' in o or 'effects_failure' in o for o in options):
            options = [option for option in options if life_policy.affordable(engine, owner, option)]
        if not options:
            return
        menu = [{'id': option['id'], 'label': option['label'],
                 **({k: option[k] for k in ('duration_hours','costs','goal_id') if k in option})} for option in options]
        key = f'life-{tick}-{opportunity["id"]}'
        self._before_decision(owner, opportunity['situation'])
        for target in dict.fromkeys([goal_id,*[o.get('goal_id',goal_id) for o in options]]):
            if target is not None:
                goal_plans.prepare(engine,owner,target,options,api=self.api,model=self.model,scripted=self.scripted)
        if not self.scripted and 'situational_personality' in self.policy:
            engine.generate_signatures(owner, api=self.api, model=self.model)
            engine.prepare_situation(owner, opportunity['situation'], key + '-situation',
                cues=opportunity.get('cues', []),
                half_life_days=self.policy['situational_personality'].get('recovery_half_life_days', 1.0),
                api=self.api, model=self.model)
        context = engine.context(owner, opportunity['situation'], opportunity.get('cues', []), menu)
        if self.scripted:
            selected = options[rng.randrange(len(options))]
            proposal = {'owner': owner, 'day': engine.day, 'context': context,
                        'decision': {'action_id': selected['id'], 'action': selected['label'],
                                     'speech': '', 'goal_id': goal_id, 'plan': [selected['label']], 'memory_ids': []}}
        else:
            proposal = engine.propose(owner, opportunity['situation'], options=menu,
                                      cues=opportunity.get('cues', []), api=self.api, model=self.model)
            selected = next(option for option in options if option['id'] == proposal['decision']['action_id'])
        goal_id = selected.get('goal_id', goal_id)
        if 'planning' in self.policy:
            proposal['decision']['goal_id'] = goal_id
        pending_probe = next((p for p in agent.get('probe_queue',[]) if p['status']=='pending' and
                              (p['target_id']==selected.get('contact') or
                               agent.get('unresolved_references',{}).get(p['target_id'],{}).get('speaker_id')==selected.get('contact'))), None)
        if pending_probe:
            proposal['decision']['speech'] += ' ' + pending_probe['question']
        engine.commit_action(key + '-action', proposal)
        contact = selected.get('contact')
        contact_proposal = None
        response = None
        if contact:
            engine.materialize_for_interaction(contact)
            if 'development' in self.policy:
                engine.configure_development(contact, self.policy['development'].get('maturation', {}))
            if self.policy.get('planning',{}).get('calendar_mode')=='elapsed':
                # Encode the actual approach before a reply, independently of
                # whether the later joint activity succeeds or is cancelled.
                name=engine.state['entities'][owner]['name']
                other=engine.state['entities'][contact]['name']
                speech=proposal['decision']['speech']
                request_observations={
                    owner:{'text':f'I approached {other}. I said: {speech} Request: '+selected['label'],
                           'source':'direct','kind':'direct','encountered':[contact]},
                    contact:{'text':f'{name} approached me and said: {speech} Request: '+selected['label'],
                             'source':owner,'kind':'direct','encountered':[owner]}}
                if not self.scripted:
                    request_observations={a:engine.appraise(a,o,api=self.api,model=self.model) for a,o in request_observations.items()}
                engine.schedule(key+'-request',engine.day,'A request is received; no task outcome yet.',request_observations,
                                requires={'alive':[owner,contact]})
                engine.advance(engine.day)
            if 'contact_responses' in selected:
                # A current perceived request is the only cross-agent model input.
                # No private profile, memories, plan or internal appraisal is shared.
                perceived_request = (engine.state['entities'][owner]['name'] + ' approaches you: ' +
                                     proposal['decision']['speech'] + ' Request: ' + selected['label'])
                replies = selected['contact_responses']
                reply_menu = [{'id':r['id'],'label':r['label']} for r in replies]
                self._before_decision(contact, perceived_request)
                if self.scripted:
                    response = replies[self.rng('contact-response',tick,opportunity['id']).randrange(len(replies))]
                    contact_proposal = {'owner':contact,'day':engine.day,
                        'context':engine.context(contact,perceived_request,options=reply_menu),
                        'decision':{'action_id':response['id'],'action':response['label'],'speech':'',
                                    'goal_id':None,'plan':[],'memory_ids':[]}}
                else:
                    if 'situational_personality' in self.policy:
                        engine.generate_signatures(contact,api=self.api,model=self.model)
                        engine.prepare_situation(contact,perceived_request,key+'-contact-situation',
                            half_life_days=self.policy['situational_personality'].get('recovery_half_life_days',1),
                            api=self.api,model=self.model)
                    contact_proposal = engine.propose(contact,perceived_request,options=reply_menu,api=self.api,model=self.model)
                    response = next(r for r in replies if r['id']==contact_proposal['decision']['action_id'])
                engine.commit_action(key+'-contact-action',contact_proposal)
        if pending_probe:
            pending_probe.update(status='asked',event=key)
        activity = {'key':key,'owner':owner,'contact':contact,'selected':deepcopy(selected),
            'response':deepcopy(response),'contact_speech':contact_proposal['decision']['speech'] if contact_proposal else '',
            'has_contact_action':bool(contact_proposal),'goal_id':goal_id,'tick':tick,'opportunity':deepcopy(opportunity),
            'plan_binding':goal_plans.bind(engine,owner,goal_id,selected['id'])}
        if self.policy.get('planning',{}).get('calendar_mode') == 'elapsed':
            from .calendar_time import reserve
            duration = (response or {}).get('activity_duration_hours',selected.get('duration_hours',0))
            reservations = {owner:reserve(engine,owner,duration,key)}
            if contact:
                contact_hours=(response or {}).get('duration_hours',selected.get('contact_duration_hours',duration))
                reservations[contact]=reserve(engine,contact,contact_hours,key)
            activity['reservations']=reservations
            activity['day']=max(r['end_day'] for r in reservations.values())
            engine.state['runtime'].setdefault('pending_activities',{})[key]=activity
            return
        self._resolve_activity(activity)

    def _resolve_activity(self, activity):
        engine=self.engine
        key,owner,contact=activity['key'],activity['owner'],activity['contact']
        selected,response=activity['selected'],activity['response']
        tick,opportunity,goal_id=activity['tick'],activity['opportunity'],activity['goal_id']
        agent=engine.agent(owner)
        contact_proposal = {'decision':{'speech':activity['contact_speech']}} if activity['has_contact_action'] else None
        probability = min(1, selected['success_probability'] * (response.get('success_multiplier',1) if response else 1))
        success = self.rng('outcome', tick, opportunity['id']).random() < probability
        text = (response or selected)['success_text'] if success else (response or selected)['failure_text']
        if contact_proposal and contact_proposal['decision']['speech']:
            text += ' ' + engine.state['entities'][contact]['name'] + ' said: ' + contact_proposal['decision']['speech']
        observation = {'text': text, 'source': 'direct', 'kind': 'direct',
                       'valence': selected['valence_success'] if success else selected['valence_failure'],
                       'arousal': selected.get('arousal', 0.2), 'importance': selected.get('importance', 0.5),
                       'meaning': text, 'confidence': 0.8}
        recipients = {owner: observation}
        if contact:
            observation['encountered'] = [contact]
            recipients[contact] = {'text': (response or selected)['contact_text'], 'source': 'direct', 'kind': 'direct',
                                   'encountered': [owner]}
            if 'caregiving' in selected:
                observation['caregiving'] = {'caregiver': contact, **deepcopy((response or {}).get('caregiving',selected['caregiving']))}
        if not self.scripted:
            recipients = {actor: engine.appraise(actor, observed, api=self.api, model=self.model)
                          for actor, observed in recipients.items()}
        outcomes = {}
        if goal_id and success and (not goal_plans.enabled(engine) or
                goal_plans.current_step(engine,owner,activity.get('plan_binding')) is not None):
            progress = min(1.0, agent['goals'][goal_id]['progress'] + selected.get('progress_gain', 0))
            outcomes[owner] = {'goals': {goal_id: {'progress': progress, 'status': 'completed' if progress >= 1 else 'active'}}}
        required = {'action':key+'-action','alive':list(recipients)}
        if contact_proposal:
            required['actions'] = [key+'-contact-action']
        engine.schedule(key, engine.day, text, recipients, outcomes=outcomes, requires=required)
        engine.advance(engine.day)
        goal_plans.record(engine,owner,activity.get('plan_binding'),key,success)
        if 'planning' in self.policy:
            life_policy.record_activity(engine,owner,selected,key,opportunity.get('cues',[]))
            if contact and self.policy['planning'].get('calendar_mode')=='elapsed':
                from .calendar_time import finish
                finish(engine,contact,key)
        effects = selected.get('effects_success' if success else 'effects_failure')
        if effects is not None:
            life_policy.apply_effects(engine,effects,key)
            self._register_births(effects)
        if success and 'conversation' in selected and engine.agent(owner)['alive'] and engine.agent(contact)['alive']:
            household.start_conversation(self,owner,contact,selected['conversation'],key+'-talk')
        if 'development' in self.policy and 'crystallization' in self.policy['development']:
            if engine.agent(owner)['alive']:
                engine.crystallize(owner, key + '-action', key, **self.policy['development']['crystallization'])
            if contact_proposal and engine.agent(contact)['alive']:
                engine.crystallize(contact, key + '-contact-action', key, **self.policy['development']['crystallization'])
        elif success and engine.agent(owner)['alive']:
            self.develop(owner, selected.get('development_success', {}), key)
        if not self.scripted and self.policy.get('consolidation_batch_size'):
            for actor in recipients:
                if engine.agent(actor)['alive']:
                    engine.consolidate(actor, api=self.api, model=self.model, batch_size=self.policy['consolidation_batch_size'])
        for actor in recipients:
            self._after_received(actor,key)
        if self.sampling == 'event_driven':
            self._ensure_background()
        engine.state['runtime']['trace'].append({'opportunity': opportunity['id'], 'day': engine.day,
            'action': selected['id'], 'success': success, 'event': key, 'policy': 'scenario_assumption',
            **({'contact_action':response['id']} if response else {})})

    def develop(self, owner, deltas, evidence):
        if not deltas:
            return
        engine = self.engine
        runtime = engine.state['runtime']
        age_year = int((engine.day - engine.agent(owner)['birth_day']) / 365.25)
        # Absolute change budget per facet, per simulated age-year, prevents event-count explosions.
        changes = {}
        for facet, delta in deltas.items():
            budget_key = f'{owner}:{age_year}:{facet}'
            used = runtime['trait_budget'].get(budget_key, 0.0)
            remaining = max(0, self.policy.get('max_trait_change_per_year', 1.0) - used)
            bounded = max(-remaining, min(remaining, delta))
            previous = engine.agent(owner)['facets'][facet]
            updated = max(0, min(100, previous + bounded))
            if updated != previous:
                changes[facet] = updated
                runtime['trait_budget'][budget_key] = used + abs(updated - previous)
        if changes:
            engine.develop(owner, changes, [evidence], evidence + '-development')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('world', type=Path)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--until-day', type=float, required=True)
    parser.add_argument('--save', type=Path, required=True)
    parser.add_argument('--scripted', action='store_true')
    parser.add_argument('--api', default='http://127.0.0.1:8081')
    parser.add_argument('--model', default='local')
    args = parser.parse_args()
    engine = Engine.load(args.world)
    controller = Lifetime(engine, json.loads(args.policy.read_text()), scripted=args.scripted, api=args.api, model=args.model)
    controller.run(args.until_day, args.save)
    print(json.dumps({'day': engine.day, 'ticks': engine.state['runtime']['tick'],
                      'provider': 'scripted_engineering_fixture' if args.scripted else 'local_model_api',
                      'actions': len(engine.state['actions']), 'checkpoint': str(args.save)}, indent=2))


if __name__ == '__main__':
    main()
