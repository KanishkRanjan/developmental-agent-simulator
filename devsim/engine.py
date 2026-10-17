"""Developmental social-agent engine, audited build-first prototype.

Only the Python standard library is required. Simulated time is in days.
Psychological rules are explicit, provisional configuration, not fitted laws.
The earlier event/observation prototype supplies the forgetting curve and
the exponential mood option. It is kept in this package as identity_state_prototype.py.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
from http.client import HTTPException
import json
import sqlite3
from math import isfinite, tanh
from pathlib import Path
import re
from urllib.request import Request, urlopen

from . import DATA_DIR
from .identity_state_prototype import AgentWorld, Observation, recall_availability
from .personality import describe
from . import situation as situational
from . import development
from . import sleep
from . import attention
from .context_view import compact

FACET_NAMES = dict(zip(
    [f'{d}{i}' for d in 'NEOAC' for i in range(1, 7)],
    ['anxiety', 'anger', 'depression', 'self_consciousness', 'immoderation', 'vulnerability',
     'friendliness', 'gregariousness', 'assertiveness', 'activity_level', 'excitement_seeking', 'cheerfulness',
     'imagination', 'artistic_interests', 'emotionality', 'adventurousness', 'intellect', 'liberalism',
     'trust', 'morality', 'altruism', 'cooperation', 'modesty', 'sympathy',
     'self_efficacy', 'orderliness', 'dutifulness', 'achievement_striving', 'self_discipline', 'cautiousness']))


def number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be finite and in [{low}, {high}]')
    return value


def profile(values):
    if set(values) != set(FACET_NAMES):
        raise ValueError('A profile must specify all 30 IPIP facets')
    return {key: number(values[key], 0, 100, key) for key in FACET_NAMES}


def sampled_profile(seed):
    """Reuse the fitted adult population sampler; no inherited-child claim."""
    from .profile_population_v1 import sample
    model = json.loads(DATA_DIR.joinpath('profile_population_v1_model.json').read_text())
    raw = sample(model, 1, seed).iloc[0]
    return {key: round(100 * (sum(counts[:int(raw[key]) - 4]) + counts[int(raw[key]) - 4] / 2) / sum(counts), 2)
            for key, counts in zip(model['facets'], model['marginal_counts'])}


LAST_USAGE = {}  # token counts and server timings of the latest model call (read by run_live's recorder)


def request_json(system, context, api, model, max_tokens=600):
    """Call the selected local server; context is a disposable, compactable view."""
    LAST_USAGE.clear()
    # A re-ask after a near-repeat samples more freely, or the same low temperature tends to return the same line.
    payload = {'model': model, 'temperature': 0.8 if 'repeat_notice' in context else 0.4, 'max_tokens': max_tokens,
               'chat_template_kwargs': {'enable_thinking': False}, 'response_format': {'type': 'json_object'},
               'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(context)}]}
    try:
        # The selected local llama.cpp server exposes its real template/tokenizer.
        # Check the rendered prompt, not a characters-per-token guess.
        with urlopen(api.rstrip('/') + '/v1/models', timeout=10) as response:
            models = json.load(response)['data']
        selected = next((entry for entry in models if entry['id'] == model), None)
        if selected is None:
            raise ValueError('The selected model is no longer served; no fallback is permitted')
        context_limit = selected['meta']['n_ctx']
        for _ in range(6):
            payload['messages'][1]['content'] = json.dumps(context)
            template_request = Request(api.rstrip('/') + '/apply-template', data=json.dumps({
                'messages': payload['messages'], 'chat_template_kwargs': payload['chat_template_kwargs']}).encode(),
                headers={'Content-Type':'application/json'})
            with urlopen(template_request, timeout=10) as response:
                prompt = json.load(response)['prompt']
            token_request = Request(api.rstrip('/') + '/tokenize', data=json.dumps({
                'content':prompt, 'add_special':False, 'parse_special':True}).encode(),
                headers={'Content-Type':'application/json'})
            with urlopen(token_request, timeout=10) as response:
                prompt_tokens = len(json.load(response)['tokens'])
            if prompt_tokens + max_tokens + 32 <= context_limit:
                break
            size = len(json.dumps(context).encode())
            target = max(256, int(size * max(0, context_limit-max_tokens-32) / max(1,prompt_tokens) * .9))
            compact(context,target)
            if len(json.dumps(context).encode()) >= size:
                raise ValueError('Essential context cannot fit the rendered prompt budget')
        else:
            raise ValueError('Rendered prompt remains too large after bounded context reduction')
        request = Request(api.rstrip('/') + '/v1/chat/completions', data=json.dumps(payload).encode(),
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=180) as response:
            body = json.load(response)
        usage, timings = body.get('usage') or {}, body.get('timings') or {}
        LAST_USAGE.update({k: v for k, v in {
            'prompt_tokens': usage.get('prompt_tokens'), 'completion_tokens': usage.get('completion_tokens'),
            'cached_tokens': timings.get('cache_n'), 'prompt_ms': timings.get('prompt_ms'),
            'generation_ms': timings.get('predicted_ms'), 'tokens_per_second': timings.get('predicted_per_second')}.items()
            if isinstance(v, (int, float))})
        result = json.loads(body['choices'][0]['message']['content'])
        if not isinstance(result, dict):
            raise ValueError('Expected a JSON object')
        return result
    except (OSError, HTTPException, ValueError, KeyError, IndexError) as exc:
        raise RuntimeError('Local model request failed; no agent state changed') from exc


class InvalidModelOutput(ValueError):
    """The model's output stayed invalid after repairs; nothing was changed."""


def validated_json(system, context, validate, api, model, max_tokens=600):
    """Repair malformed structured responses at most twice, before any mutation."""
    last_error = None
    for attempt in range(3):
        supplied = context if attempt == 0 else {**context, 'output_repair': {
            'attempt':attempt, 'validation_error':str(last_error)[:200]}}
        result = request_json(system, supplied, api, model, max_tokens)
        try:
            validate(result)
            return result
        except (ValueError, TypeError, KeyError) as exc:
            last_error = exc
    raise InvalidModelOutput('Local model output remained invalid after two repair attempts') from last_error


class Engine:
    def __init__(self, seed=42, mood_kernel='power_law'):
        if mood_kernel not in ('power_law', 'exponential', 'average'):
            raise ValueError('Unsupported mood kernel')
        self.state = {
            'version': 1, 'seed': seed, 'day': 0.0, 'entities': {}, 'agents': {},
            'events': [], 'pending': [], 'actions': [], 'updates': [],
            'config': {'mood_kernel': mood_kernel, 'mood_half_life_days': 1.0,
                       'mood_tau_days': 1.0, 'mood_alpha': 0.5,
                       'affect_budget': 2.0, 'arousal_budget': 2.0,
                       'memory_base_stability_days': 3.0,
                       'memory_importance_weight': 2.0, 'memory_arousal_weight': 1.0,
                       'rehearsal_gain': 0.1, 'rehearsal_gap_days': 1.0,
                       'max_stability_days': 3650.0, 'recall_affect_gap_days': 1.0},
        }
        self.world = AgentWorld()

    @property
    def day(self):
        return self.state['day']

    def _new_handle(self, key, name):
        """Unique Instagram-style handle: name letters plus 4 digits seeded by world seed and id (priya0123)."""
        base = re.sub(r'[^a-z0-9]', '', name.lower())[:20] or 'person'
        taken = {e['facts'].get('handle') for e in self.state['entities'].values()}
        n = int(sha256(f'{self.state["seed"]}:{key}'.encode()).hexdigest(), 16) % 10000
        while f'{base}{n:04d}' in taken:
            n = (n + 1) % 10000
        return f'{base}{n:04d}'

    def label(self, key):
        """How a person is shown to others: 'Priya (@priya0123)' when handles are on, else the plain name."""
        entity = self.state['entities'][key]
        return entity['name'] + (f" (@{entity['facts']['handle']})" if entity['facts'].get('handle') else '')

    def entity(self, key, name, facts=None):
        """Controller commits identity. Agent testimony never calls this method."""
        if not key or not name:
            raise ValueError('Identity and name are required')
        facts = deepcopy(facts or {})
        json.dumps(facts, allow_nan=False)
        previous = self.state['entities'].get(key)
        if previous:
            if previous['name'] != name or any(k in previous['facts'] and previous['facts'][k] != v for k, v in facts.items()):
                raise ValueError('Expansion contradicts committed identity facts')
            previous['facts'].update(facts)
        else:
            if self.state['config'].get('identity_handles') and 'handle' not in facts:
                facts['handle'] = self._new_handle(key, name)
            elif 'handle' in facts and (not isinstance(facts['handle'], str) or not re.fullmatch(r'[a-z0-9_.]{3,30}', facts['handle'])
                                        or any(e['facts'].get('handle') == facts['handle'] for e in self.state['entities'].values())):
                raise ValueError('A handle is 3-30 lowercase letters, digits, dots or underscores, and unique')
            self.state['entities'][key] = {'name': name, 'facts': facts}

    def materialize(self, key, facets=None, birth_day=0.0, attachment=None, culture=None, affect=None):
        if key not in self.state['entities']:
            raise ValueError('Commit a world identity before materializing it')
        if key in self.state['agents']:
            raise ValueError('Agent already materialized')
        number(birth_day, -1e8, self.day, 'birth_day')
        committed_birth = self.state['entities'][key]['facts'].get('birth_day')
        if committed_birth is not None and committed_birth != birth_day:
            raise ValueError('Materialization contradicts the committed birth day')
        entity_seed = int.from_bytes(sha256(f'{self.state["seed"]}:{key}'.encode()).digest()[:4], 'big')
        facets = profile(facets if facets is not None else sampled_profile(entity_seed))
        affect = deepcopy(affect or {})
        allowed_affect = {'recovery_multiplier', 'positive_reactivity', 'negative_reactivity',
                          'intensity_duration_gain', 'rumination_fraction'}
        if set(affect) - allowed_affect:
            raise ValueError('Unknown affect parameter')
        for field, value in affect.items():
            number(value, 0.01 if field == 'recovery_multiplier' else 0, 1 if field == 'rumination_fraction' else 10, field)
        self.state['agents'][key] = {
            'facets': facets, 'initial_facets': dict(facets), 'birth_day': birth_day, 'alive': True,
            'attachment': deepcopy(attachment or {}), 'culture': deepcopy(culture or {}),
            'goals': {}, 'relationships': {}, 'references': {}, 'beliefs': {},
            'memory_meta': {}, 'rules': [], 'affect_events': [], 'recall_log': [],
            'affect_parameters': affect,
        }

    def agent(self, key):
        if key not in self.state['agents']:
            raise ValueError(f'Agent is not materialized: {key}')
        return self.state['agents'][key]

    def materialize_child(self, key, *, biological_parents=(), caregivers=(), birth_day=None, h2=.5):
        """Parent-first inherited proxy; caregivers need not be biological parents.

        Missing biological parents are integrated as population draws, never
        manufactured identities. No recursive ancestry expansion is required.
        """
        from .temperament import inherited
        birth_day = self.day if birth_day is None else birth_day
        number(birth_day, -1e8, self.day, 'birth day')
        if not isinstance(biological_parents, (list, tuple)) or len(biological_parents) > 2:
            raise ValueError('Provide zero to two known biological parents')
        if not all(isinstance(p, str) for p in biological_parents) or len(set(biological_parents)) != len(biological_parents):
            raise ValueError('Biological parents must be distinct identities')
        if not isinstance(caregivers, (list, tuple)) or not all(isinstance(c, str) for c in caregivers):
            raise ValueError('Caregivers must be identity ids')
        if key not in self.state['entities'] or key in self.state['agents']:
            raise ValueError('Child needs an existing unmaterialized identity')
        for parent in biological_parents:
            if parent == key or self.agent(parent)['birth_day'] >= birth_day:
                raise ValueError('Biological parent must precede the child')
        if any(c == key or c not in self.state['entities'] for c in caregivers):
            raise ValueError('Caregiver must be a distinct committed identity')
        facets, origin, parent_origins = inherited(self.state, key, sorted(biological_parents), h2)
        backup = deepcopy(self.state)
        try:
            self.entity(key, self.state['entities'][key]['name'],
                        {'biological_parents': sorted(biological_parents), 'birth_day': birth_day})
            self.materialize(key, facets, birth_day=birth_day)
            self.agent(key)['temperament_origin'] = origin
            for parent, info in parent_origins.items():
                self.agent(parent).setdefault('temperament_origin', info)
            for caregiver in dict.fromkeys(caregivers):
                self.caregiver(key, caregiver)
        except Exception:
            self.state = backup
            raise

    def materialize_for_interaction(self, key, *, default_age_years=25):
        """Necessity-driven activation, without turning testimony into biography.

        Only committed identity/family constraints determine age. Unknown age
        uses a labeled scenario assumption. No past observations are invented
        and no private accounts about this person are passed into their model.
        """
        if key in self.state['agents']:
            return
        if key not in self.state['entities']:
            raise ValueError('Only a committed world identity can be activated')
        number(default_age_years, 18, 100, 'default activation age')
        entity = self.state['entities'][key]
        children = [a['birth_day'] for owner, a in self.state['agents'].items()
                    if key in self.state['entities'][owner]['facts'].get('caregivers', [])]
        basis = 'committed_birth_day' if 'birth_day' in entity['facts'] else 'explicit_scenario_age_assumption'
        birth_day = entity['facts'].get('birth_day', min([self.day, *children]) - default_age_years * 365.25)
        number(birth_day, -1e8, self.day, 'activation birth day')
        observed_care_days = [event['day'] for agent in self.state['agents'].values()
                              for event in agent.get('caregiving_experiences', []) if event['caregiver'] == key]
        if observed_care_days and birth_day > min(observed_care_days):
            raise ValueError('Activation birth day follows an existing caregiving experience')
        # Prepare the optional sampler before any mutation.
        seed = int.from_bytes(sha256(f'{self.state["seed"]}:{key}'.encode()).digest()[:4], 'big')
        facets = sampled_profile(seed)
        self.materialize(key, facets, birth_day=birth_day)
        entity['facts'].setdefault('birth_day', birth_day)
        self.agent(key)['materialization_provenance'] = {'day': self.day, 'age_basis': basis,
            'policy': 'interaction_required_identity_expansion', 'invented_historical_observations': False}

    def relate(self, owner, other, role, *, firsthand=False, evidence=None, trust=0.5, closeness=0.0):
        agent = self.agent(owner)
        if other not in self.state['entities']:
            raise ValueError('Relationship target must have a committed identity')
        number(trust, 0, 1, 'trust')
        number(closeness, 0, 1, 'closeness')
        if firsthand and not any(o.event_id == evidence and other in agent['memory_meta'][evidence]['encountered']
                                 for o in self.world.observations.get(owner, [])):
            raise ValueError('Firsthand relationship requires an observed encounter')
        old = agent['relationships'].get(other, {})
        agent['relationships'][other] = {'role': role, 'firsthand': firsthand or old.get('firsthand', False),
                                         'evidence': evidence or old.get('evidence'), 'trust': trust, 'closeness': closeness,
                                         **({'last_interaction_day':old['last_interaction_day']} if 'last_interaction_day' in old else {}),
                                         **({'versions':deepcopy(old['versions'])} if 'versions' in old else {})}

    def goal(self, owner, key, description, *, priority=0.5, deadline=None):
        number(priority, 0, 1, 'priority')
        if deadline is not None:
            number(deadline, self.day, 1e8, 'deadline')
        goals = self.agent(owner)['goals']
        if key in goals:
            raise ValueError('Goal already exists')
        goals[key] = {'description': description, 'priority': priority, 'deadline': deadline,
                      'status': 'active', 'progress': 0.0, 'plan': []}

    def situation_rule(self, owner, key, cues, tendency):
        if not cues or not all(isinstance(c, str) and c for c in cues):
            raise ValueError('Situation rules need explicit cue labels')
        self.agent(owner)['rules'].append({'id': key, 'cues': list(cues), 'tendency': tendency})

    def generate_signatures(self, owner, *, api='http://127.0.0.1:8081', model='local'):
        """Reuse stable signatures; refresh at configured scenario age/trait shifts."""
        agent = self.agent(owner)
        if not agent['alive']:
            raise ValueError('A dead agent cannot generate signatures')
        age = (self.day - agent['birth_day']) / 365.25
        stage = situational.signature_stage(age)
        age_appropriate = self.state['config'].get('expression',{}).get('age_appropriate_actions',False)
        band = situational.capability_band(age) if age_appropriate else None
        previous = agent.get('caps_provenance')
        if agent.get('caps_rules'):
            if not previous:  # Explicit externally supplied rules remain under caller control.
                return deepcopy(agent['caps_rules'])
            original_stage = previous.get('stage',situational.signature_stage((previous['day']-agent['birth_day'])/365.25))
            drift = max(abs(agent['facets'][k]-previous['facets_at_generation'][k]) for k in FACET_NAMES)
            if stage == original_stage and (not age_appropriate or previous.get('capability_band') == band) and not (drift >= 5 and self.day - previous['day'] >= 365.25):
                return deepcopy(agent['caps_rules'])
        context = self.context(owner, 'Describe how your reactions may vary across different situations.')
        context['task'] = 'generate_situational_signatures'
        context['situation_dimensions'] = list(situational.DIMENSIONS)
        context = compact(context)
        system = ('Construct five specific if-then signatures for this fictional agent from the supplied behavioral '
                  'tendencies and received experience. Do not invent biography or diagnose conditions. '
                  'Use situations appropriate to the supplied age; do not give a child adult roles or sexual scenarios. '
                  'These are provisional simulation policies, not discovered facts about a real person. '
                  'Return JSON with rules, a list of five objects: id (unique short string), dimension '
                  '(one supplied situation dimension), trigger_context (specific condition), narrative_shift '
                  '(temporary behavioral change, not a mandatory action), and state_modifiers '
                  '(object of affected Big Five domain keys N/E/O/A/C, each a shift from -10 to 10). '
                  'Avoid making all situations express the same stereotyped reaction. One signature must cover what this '
                  'agent does when the same thing keeps happening, such as being asked the same question again or an '
                  'unchanging routine: for example boredom, irritation, going quiet, arguing back or leaving, as this '
                  'agent\'s tendencies suggest.')
        infant = age_appropriate and age < 2
        if infant:
            context['infant_trigger_catalog'] = {key: value[1] for key,value in situational.INFANT_TRIGGERS.items()}
            context['infant_reaction_catalog'] = situational.INFANT_REACTIONS
            system = ('Construct five provisional sensory-response signatures for this fictional infant. '
                      'Use only catalog trigger and nonverbal reaction ids; no invented competence or biography. '
                      'Return JSON with rules: five objects containing only id (unique string), trigger_id, reaction_id, '
                      'and state_modifiers (affected N/E/O/A/C domains, shifts from -10 to 10). '
                      'Required root shape: {"rules": [{"id": "r1", "trigger_id": "discomfort", '
                      '"reaction_id": "signal", "state_modifiers": {"N": 1}}, four more rule objects]}. '
                      'These are simulation policies, not validated infant trait measurements.')
        validator = situational.infant_rules if infant else lambda r: situational.validate_rules(r.get('rules'))
        try:
            result = validated_json(system, context, validator, api, model, 1400)
        except InvalidModelOutput as exc:
            self.skip_model_step('signatures', owner, exc)
            return deepcopy(agent.get('caps_rules', []))
        rules = validator(result)
        if agent.get('caps_rules'):
            agent.setdefault('caps_versions',[]).append({'rules':deepcopy(agent['caps_rules']),
                                                         'provenance':deepcopy(previous)})
        agent['caps_rules'] = deepcopy(rules)
        agent['caps_provenance'] = {'day': self.day, 'stage':stage, 'model': model, 'policy': 'local_llm_unfitted',
                                   'capability_band': band, 'facets_at_generation': dict(agent['facets']),
                                   'evidence': [m['event'] for m in context['memories']]}
        return deepcopy(rules)

    def prepare_situation(self, owner, situation, update_id, *, cues=(), half_life_days=1.0,
                          api='http://127.0.0.1:8081', model='local'):
        """A cognitive event before action, unlike read-only context inspection.

        The classifier sees only delivered information and the agent's context.
        Its dimension estimates and rule matches are subjective, not world facts.
        """
        agent = self.agent(owner)
        if any(u['id'] == update_id for u in self.state['updates']):
            raise ValueError('Duplicate situation event')
        number(half_life_days, 1e-6, 36525, 'situational recovery half life')
        context = self.context(owner, situation, cues)
        context.update(task='construe_situation', candidate_signatures=deepcopy(agent.get('caps_rules', [])),
                       situation_dimensions=list(situational.DIMENSIONS))
        context = compact(context)
        system = ('Construe the supplied situation from this fictional agent\'s perspective using only its context. '
                  'Return JSON with meaning (subjective interpretation string), dimensions (object containing all '
                  'eight supplied names with intensity 0 to 1), controllability (0 to 1), active_rule_ids '
                  '(list of candidate signature ids whose full trigger_context is satisfied; may be empty). '
                  'Ambiguous intentions are uncertain interpretations. A matching dimension alone is insufficient '
                  'to satisfy a more specific trigger. Do not invent past experiences or new signatures. '
                  'Repetition the agent has noticed (repeated_question, conversation_so_far) is part of the situation. '
                  'Respect developmental_capabilities when supplied. For an infant, meaning is a controller sensory/affective '
                  'description, not a verbal self-report or evidence of abstract understanding.')
        try:
            perception = validated_json(system, context, lambda r: situational.transition(agent, self.day, r, half_life_days),
                                        api, model, 650)
        except InvalidModelOutput as exc:
            return self.skip_model_step('situation', owner, exc)
        record = situational.transition(agent, self.day, perception, half_life_days)
        from . import expression
        record = expression.vary(self,owner,update_id,record)
        record.update(id=update_id, situation=situation, cues=list(cues), model=model)
        agent['situational_state'] = deepcopy(record)
        self.state['updates'].append({'id': update_id, 'kind': 'situation_state', 'owner': owner,
                                     'day': self.day, 'state': deepcopy(record)})
        return deepcopy(record)

    def skip_model_step(self, step, owner, error):
        """An optional cognitive step whose output stayed invalid is skipped and recorded, not fatal.
        Actions and appraisals stay strict: they decide what happens and what is remembered."""
        self.state.setdefault('runtime', {}).setdefault('skipped_model_steps', []).append(
            {'step': step, 'owner': owner, 'day': self.day, 'error': str(error.__cause__ or error)[:300]})

    def caregiver(self, child, adult, role='caregiver'):
        """Commit the minimum family constraint; adult need not be materialized."""
        self.agent(child)
        if child == adult or adult not in self.state['entities']:
            raise ValueError('Caregiver must be a distinct, committed identity')
        ancestors = [adult]
        visited = set()
        while ancestors:
            key = ancestors.pop()
            if key == child:
                raise ValueError('Caregiver graph would contain a cycle')
            if key not in visited:
                visited.add(key)
                ancestors.extend(self.state['entities'][key]['facts'].get('caregivers', []))
        existing = list(self.state['entities'][child]['facts'].get('caregivers', []))
        if adult not in existing:
            existing.append(adult)
        self.state['entities'][child]['facts']['caregivers'] = existing
        self.relate(child, adult, role)

    def develop(self, owner, changes, evidence, update_id):
        """Explicit slow trait revision; no automatic trait change from one mood swing."""
        agent = self.agent(owner)
        if not agent['alive'] or not evidence or any(e not in agent['memory_meta'] for e in evidence):
            raise ValueError('Development requires a living agent and received evidence')
        if any(u['id'] == update_id for u in self.state['updates']):
            raise ValueError('Duplicate developmental update')
        updated = profile({**agent['facets'], **changes})
        self.state['updates'].append({'id': update_id, 'kind': 'development', 'owner': owner,
            'day': self.day, 'previous': dict(agent['facets']), 'next': updated, 'evidence': list(evidence),
            'policy': 'controller_supplied_unfitted'})
        if 'developmental_model' in agent:
            model = agent['developmental_model']
            maturity = development.maturity(agent, self.day)
            model['learned_change'] = {key: updated[key] - model['initial_facets'][key] - maturity[key] for key in updated}
        agent['facets'] = updated

    def configure_development(self, owner, maturation):
        """Explicit scenario curve; never a fitted or genetically fixed baseline."""
        agent = self.agent(owner)
        development.validate_trajectory(maturation)
        if 'developmental_model' in agent:
            if agent['developmental_model']['maturation'] != maturation:
                raise ValueError('Cannot silently replace an existing maturation policy')
            return
        if not agent['alive']:
            raise ValueError('Cannot initialize development for a dead agent')
        agent['developmental_model'] = {'origin_day': self.day, 'initial_facets': dict(agent['facets']),
            'learned_change': dict.fromkeys(FACET_NAMES, 0.0), 'maturation': deepcopy(maturation),
            'policy': 'scenario_piecewise_linear_unfitted'}

    def _advance_development(self, day):
        for agent in self.state['agents'].values():
            if agent['alive'] and 'developmental_model' in agent:
                agent['facets'] = development.projected_traits(agent, day)

    def crystallize(self, owner, action_id, evidence, *, rate=0.005, minimum_days=3,
                    max_change_per_year=0.5):
        """Repeated enacted-state proxy, gated by received resolved consequences.

        It uses the state present in the action request, not a mood or the
        number of memory reads. At most one small update per facet per day;
        evidence from independent days is required. These are explicit scenario
        policies, not an empirical micro-to-macro personality-change law.
        """
        number(rate, 0, .1, 'crystallization rate')
        number(max_change_per_year, 0, 10, 'crystallization annual bound')
        if isinstance(minimum_days, bool) or not isinstance(minimum_days, int) or minimum_days < 2:
            raise ValueError('Crystallization needs at least two independent days')
        agent = self.agent(owner)
        actions = [a for a in self.state['actions'] if a['id'] == action_id and a['owner'] == owner]
        if not agent['alive'] or evidence not in agent['memory_meta'] or not actions:
            raise ValueError('Crystallization requires a living actor and received outcome')
        action = actions[0]
        if action['status'] != 'resolved' or action.get('outcome_event') != evidence:
            raise ValueError('An intention alone cannot drive crystallization')
        exposures = agent.setdefault('developmental_exposures', [])
        if any(e['action'] == action_id for e in exposures):
            raise ValueError('Duplicate developmental exposure')
        offsets = action.get('temporary_offsets', dict.fromkeys(FACET_NAMES, 0.0))
        exposures.append({'day': self.day, 'action': action_id, 'evidence': evidence, 'offsets': dict(offsets)})
        # ponytail: a small exact evidence scan; index daily summaries if history grows large.
        from math import floor
        year = int((self.day - agent['birth_day']) / 365.25)
        budget = agent.setdefault('crystallization_budget', {})
        last = agent.setdefault('last_crystallization_day', {})
        changes, used_after = {}, {}
        for facet in FACET_NAMES:
            days = {}
            for exposure in exposures:
                if self.day - exposure['day'] <= 180 and abs(exposure['offsets'][facet]) >= 1:
                    days.setdefault(floor(exposure['day']), []).append(exposure['offsets'][facet])
            if len(days) < minimum_days or last.get(facet) == floor(self.day):
                continue
            mean = sum(sum(values) / len(values) for values in days.values()) / len(days)
            key = f'{year}:{facet}'
            remaining = max(0, max_change_per_year - budget.get(key, 0))
            delta = max(-min(.05, remaining), min(min(.05, remaining), rate * mean))
            updated = max(0, min(100, agent['facets'][facet] + delta))
            if updated != agent['facets'][facet]:
                changes[facet] = updated
                used_after[facet] = budget.get(key, 0) + abs(updated - agent['facets'][facet])
        if changes:
            source_ids = list(dict.fromkeys(e['evidence'] for e in exposures if self.day - e['day'] <= 180 and
                                          any(abs(e['offsets'][facet]) >= 1 for facet in changes)))
            self.develop(owner, changes, source_ids, action_id + '-crystallization')
            self.state['updates'][-1]['policy'] = 'repeated_enacted_state_proxy_unfitted'
            for facet in changes:
                budget[f'{year}:{facet}'] = used_after[facet]
                last[facet] = floor(self.day)
        return changes

    def believe(self, owner, key, text, confidence, evidence, update_id):
        agent = self.agent(owner)
        if not agent['alive']:
            raise ValueError('A dead agent cannot update beliefs')
        number(confidence, 0, 1, 'confidence')
        if not evidence or any(e not in agent['memory_meta'] for e in evidence):
            raise ValueError('Belief requires received evidence')
        if any(u['id'] == update_id for u in self.state['updates']):
            raise ValueError('Duplicate belief update')
        previous = deepcopy(agent['beliefs'].get(key))
        agent['beliefs'][key] = {'text': text, 'confidence': confidence, 'evidence': list(evidence), 'day': self.day}
        self.state['updates'].append({'id': update_id, 'kind': 'belief', 'owner': owner,
                                     'day': self.day, 'key': key, 'previous': previous})

    def schedule(self, key, day, description, observations, *, facts=None, outcomes=None, requires=None):
        number(day, self.day, 1e8, 'event day')
        if any(e['id'] == key for e in self.state['events'] + self.state['pending']):
            raise ValueError('Duplicate event id')
        event = {'id': key, 'day': day, 'description': description, 'observations': deepcopy(observations),
                 'facts': deepcopy(facts or {}), 'outcomes': deepcopy(outcomes or {}),
                 'requires': deepcopy(requires or {})}
        self._validate_event(event)
        self.state['pending'].append(event)

    def _validate_event(self, event):
        json.dumps(event, allow_nan=False)
        for key, values in event['facts'].items():
            if key not in self.state['entities'] or not isinstance(values, dict):
                raise ValueError('World facts require a known entity and object values')
            committed = self.state['entities'][key]['facts']
            for field in ('birth_day', 'biological_parents', 'caregivers'):
                if field in values and field in committed and values[field] != committed[field]:
                    raise ValueError('An event cannot silently rewrite committed birth or family identity')
            if 'birth_day' in values:
                number(values['birth_day'], -1e8, event['day'], 'committed birth day')
                if key in self.state['agents'] and values['birth_day'] != self.agent(key)['birth_day']:
                    raise ValueError('World birth day contradicts materialized age')
        for owner, obs in event['observations'].items():
            self.agent(owner)
            if not obs.get('text') or not obs.get('source') or obs.get('kind', 'direct') not in ('direct', 'testimony', 'internal'):
                raise ValueError('Observation needs text, source and a supported kind')
            for field, low, high, default in [('valence', -1, 1, 0), ('arousal', 0, 1, 0), ('importance', 0, 1, 0), ('confidence', 0, 1, 0.5)]:
                number(obs.get(field, default), low, high, field)
            if 'stability_days' in obs:
                number(obs['stability_days'], 1e-9, 1e8, 'stability_days')
            if 'gist' in obs and (not isinstance(obs['gist'], str) or not obs['gist'].strip() or len(obs['gist']) > 300):
                raise ValueError('Observation gist must be short nonempty text')
            encountered = obs.get('encountered', [])
            for field in ('encountered', 'references', 'cued_memories', 'addressed'):
                if not isinstance(obs.get(field, []), list) or not all(isinstance(k, str) for k in obs.get(field, [])):
                    raise ValueError('Observation identity and memory references must be lists of ids')
            if not all(other in self.state['entities'] for other in encountered):
                raise ValueError('Encountered identities must exist in the world')
            if obs.get('kind', 'direct') != 'direct' and encountered:
                raise ValueError('Testimony and reflection cannot establish a firsthand encounter')
            if any(mid not in self.agent(owner)['memory_meta'] for mid in obs.get('cued_memories', [])):
                raise ValueError('Reminder must refer to a memory already received by this listener')
            if 'reused_appraisal' in obs and (obs['reused_appraisal'] not in self.agent(owner)['memory_meta'] or
                    isinstance(obs.get('exposures'), bool) or not isinstance(obs.get('exposures'), int) or obs['exposures'] < 1):
                raise ValueError('A habituated appraisal must reuse one of this listener\'s own memories')
            if 'repeat_of' in obs and obs['repeat_of'] not in self.agent(owner)['memory_meta']:
                raise ValueError('A repeated question must link to a question this listener already received')
            development.validate_caregiving(owner, obs, self.state['entities'][owner]['facts'].get('caregivers', []))
            if 'mentions' in obs or 'resolved_references' in obs:
                from . import references
                references.validate(self,owner,obs)
        for owner, changes in event['outcomes'].items():
            agent = self.agent(owner)
            if set(changes) - {'alive', 'goals'}:
                raise ValueError('Unsupported outcome field')
            if 'alive' in changes and not isinstance(changes['alive'], bool):
                raise ValueError('alive must be boolean')
            for goal_id, update in changes.get('goals', {}).items():
                if goal_id not in agent['goals'] or set(update) - {'progress', 'status'}:
                    raise ValueError('Unknown goal or unsupported goal outcome')
                if 'progress' in update:
                    number(update['progress'], 0, 1, 'progress')
                if update.get('status', 'active') not in ('active', 'completed', 'abandoned'):
                    raise ValueError('Invalid goal status')
        if set(event['requires']) - {'alive', 'facts', 'action', 'actions'}:
            raise ValueError('Unsupported event prerequisite')
        linked = event['requires'].get('actions', [])
        if not isinstance(linked,list) or not all(isinstance(a,str) and a for a in linked) or len(set(linked)) != len(linked):
            raise ValueError('Linked actions must be a list of distinct ids')
        for owner in event['requires'].get('alive', []):
            self.agent(owner)
        for key in event['requires'].get('facts', {}):
            if key not in self.state['entities']:
                raise ValueError('Prerequisite refers to an unknown identity')

    def advance(self, day):
        number(day, self.day, 1e8, 'advance day')
        due = sorted((e for e in self.state['pending'] if e['day'] <= day), key=lambda e: (e['day'], e['id']))
        for event in due:
            # Recheck against current state: a preceding event may change eligibility.
            eligible = all(self.agent(a)['alive'] for a in event['requires'].get('alive', []))
            eligible &= all(all(self.state['entities'][key]['facts'].get(k) == v for k, v in values.items())
                            for key, values in event['requires'].get('facts', {}).items())
            eligible &= all(self.agent(a)['alive'] for a in event['observations'])
            eligible &= all(self.agent(a)['alive'] for a in event['outcomes'])
            action_id = event['requires'].get('action')
            action_ids = list(dict.fromkeys(([action_id] if action_id is not None else []) + event['requires'].get('actions', [])))
            eligible &= all(any(a['id'] == aid and a['status'] == 'intended' for a in self.state['actions']) for aid in action_ids)
            self._validate_event(event)
            self._advance_development(event['day'])
            if 'sleep' in self.state['config']:
                sleep.due(self, event['day'])  # a sleep opportunity before this event consolidates the earlier buffer
            if eligible:
                recipients = {}
                attended, encoded = {}, dict(event['observations'])  # attention may coarsen what each listener encodes
                for owner, obs in event['observations'].items():
                    cfg = self.state['config']
                    if cfg.get('attention', {}).get('enabled'):
                        attended[owner] = attention.allocate(self, owner, event, obs)
                        obs = encoded[owner] = attention.encoded(self, owner, obs, attended[owner])
                    stability = obs.get('stability_days', cfg['memory_base_stability_days'] * (
                        1 + cfg['memory_importance_weight'] * obs.get('importance', 0) + cfg['memory_arousal_weight'] * obs.get('arousal', 0)))
                    # Mood and Memory, coupling pathway 1: events met in a strong mood are encoded more durably.
                    # shortcut: linear in |mood valence| with a provisional weight; the report's equation is not legible in the text.
                    mood_weight = cfg.get('cognition', {}).get('mood_encoding_weight', 0)
                    if mood_weight and 'stability_days' not in obs:
                        stability = min(cfg['max_stability_days'],
                                        stability * (1 + mood_weight * abs(self.mood(owner, event['day'])['valence'])))
                    if 'sleep' in cfg and 'stability_days' not in obs:
                        stability *= sleep.encoding_multiplier(self, owner)
                    if owner in attended and 'stability_days' not in obs:
                        stability *= attention.encoding_factor(cfg['attention'], attended[owner], buffered='sleep' in cfg)
                    recipients[owner] = Observation(event['id'], event['day'], obs['text'], obs['source'],
                                                     obs.get('valence', 0), obs.get('arousal', 0), stability)
                self.world.add_event(event['id'], event['day'], event['description'], recipients)
                for owner, obs in encoded.items():
                    agent = self.agent(owner)
                    agent['memory_meta'][event['id']] = {
                        'kind': obs.get('kind', 'direct'), 'confidence': obs.get('confidence', 0.5),
                        'importance': obs.get('importance', 0), 'meaning': obs.get('meaning', ''),
                        'versions': [], 'stability_days': recipients[owner].stability_days,
                        'encoding_stability_days': recipients[owner].stability_days,
                        'last_recall_day': None, 'encountered': obs.get('encountered', []),
                        'provenance': obs.get('provenance', event['id']),
                    }
                    if obs.get('gist'):
                        agent['memory_meta'][event['id']]['summary'] = obs['gist']
                    if 'reused_appraisal' in obs:
                        agent['memory_meta'][event['id']].update(reused_appraisal=obs['reused_appraisal'], exposures=obs['exposures'])
                    if 'repeat_of' in obs:
                        agent['memory_meta'][event['id']].update(repeat_of=obs['repeat_of'],
                            times_asked_before=agent['memory_meta'][obs['repeat_of']].get('times_asked_before', 0) + 1)
                    if owner in attended:
                        attention.record(agent['memory_meta'][event['id']], attended[owner], buffered='sleep' in self.state['config'])
                        attention.felt_ignored(self, owner, event, obs, attended[owner])
                    if 'sleep' in self.state['config'] and agent['memory_meta'][event['id']].get('tier') != attention.UNATTENDED:
                        sleep.buffer(self, owner, event, obs)
                        if owner in attended:
                            agent['hippocampal_buffer'][-1]['attention_weight'] = attention.trace_factor(cfg['attention'], attended[owner])
                    for other in obs.get('references', []):
                        agent['references'].setdefault(other, []).append(event['id'])
                    for other in obs.get('encountered', []):
                        old = agent['relationships'].get(other, {})
                        from . import society
                        old = society.relationship(self,old,event['day'])
                        agent['relationships'][other] = {'role': old.get('role', 'acquaintance'),
                            'trust': old.get('trust', 0.5), 'closeness': old.get('closeness', 0.0),
                            'firsthand': True, 'evidence': event['id'], 'last_interaction_day':event['day'],
                            **({'versions':deepcopy(old['versions'])} if 'versions' in old else {})}
                    if 'caregiving' in obs:
                        agent.setdefault('caregiving_experiences', []).append({
                            **deepcopy(obs['caregiving']), 'event': event['id'], 'day': event['day']})
                    if 'mentions' in obs or 'resolved_references' in obs:
                        from . import references
                        references.record(self,owner,obs,event['id'],event['day'])
                for key, facts in event['facts'].items():
                    self.state['entities'][key]['facts'].update(facts)
                for owner, changes in event['outcomes'].items():
                    if 'alive' in changes:
                        self.agent(owner)['alive'] = changes['alive']
                    for goal_id, update in changes.get('goals', {}).items():
                        self.agent(owner)['goals'][goal_id].update(update)
                for linked_id in action_ids:
                    action = next(a for a in self.state['actions'] if a['id'] == linked_id)
                    action.update(status='resolved', outcome_event=event['id'])
                self.state['day'] = event['day']
                for owner, obs in encoded.items():
                    for mid in dict.fromkeys(obs.get('cued_memories', [])):
                        self.recall(owner, mid, f'{event["id"]}:reminder:{owner}:{mid}', rehearse=True, affect=True)
            self.state['events'].append({**event, 'status': 'applied' if eligible else 'ineligible'})
            self.state['pending'].remove(event)
            self.state['day'] = event['day']
        self.state['day'] = day
        if 'sleep' in self.state['config']:
            sleep.due(self, day)
        self._advance_development(day)

    def affect(self, owner):
        """Mood parameters: explicit affect_parameters win; with cognition affect_from_traits, the rest come from current
        traits (Mood and Memory trait table and reference code: inertia 1+2N, reactivity 1+1.5E / 1+1.5N, rumination N,
        rated strong). Divided by their values at N = E = 0.5 so an average person keeps 1.0 (and 0.25 rumination).
        """
        agent = self.agent(owner)
        derived = {}
        if self.state['config'].get('cognition', {}).get('affect_from_traits'):
            f = agent['facets']
            n, e = (sum(f[d + str(i)] for i in range(1, 7)) / 600 for d in 'NE')
            derived = {'recovery_multiplier': (1 + 2 * n) / 2, 'positive_reactivity': (1 + 1.5 * e) / 1.75,
                       'negative_reactivity': (1 + 1.5 * n) / 1.75, 'rumination_fraction': .5 * n}
        return {**derived, **agent.get('affect_parameters', {})}

    def mood(self, owner, day=None):
        now = self.day if day is None else day
        agent = self.agent(owner)
        cfg = self.state['config']
        settings = self.affect(owner)
        def impulse(day, valence, arousal):
            reactivity = settings.get('positive_reactivity' if valence > 0 else 'negative_reactivity', 1.0)
            tau = cfg['mood_tau_days'] * settings.get('recovery_multiplier', 1.0)
            tau *= 1 + settings.get('intensity_duration_gain', 0.0) * arousal
            return day, valence * reactivity, arousal, tau
        impulses = [impulse(o.day, o.valence, o.arousal) for o in self.world.observations.get(owner, [])]
        if 'attention' in cfg:  # an inattentive listener is barely moved
            scales = [attention.emotion_scale(agent['memory_meta'][o.event_id]) for o in self.world.observations.get(owner, [])]
            impulses = [impulse(o.day, o.valence * k, o.arousal * k) for o, k in zip(self.world.observations.get(owner, []), scales)]
        impulses += [impulse(r['day'], r['valence'], r['arousal']) for r in agent['affect_events']]
        impulses = sorted((x for x in impulses if x[0] <= now), key=lambda x: x[0])
        if cfg['mood_kernel'] == 'average':
            # Intensity-weighted average of recent affect (v2 run: summed kernels pinned all 7 people at arousal ~0.95,
            # incl. calm ones). Each impulse weighs arousal^2 x 2^(-age/tau) (squared so one strong event outweighs a day of
            # small talk), tau = half-life x inertia; baseline weight c
            # pulls toward neutral. Bounded without tanh, so steady mild days give a mild mood. shortcut: c and the
            # half-life are provisional; Mood and Memory's heavy tail is replaced by exponential fading here.
            c = cfg.get('mood_baseline_weight', 1.0)
            w = [(2 ** (-(now - day) / tau), v, a) for day, v, a, tau in impulses]
            strength = sum(x * a * a for x, _, a in w)
            return {'valence': max(-1, min(1, sum(x * a * a * v for x, v, a in w) / (c + strength))),
                    'arousal': sum(x * a for x, _, a in w) / (c + sum(x for x, _, _ in w))}
        if cfg['mood_kernel'] == 'exponential':
            from math import exp, log
            v = a = previous = 0.0
            for day, valence, arousal, _ in impulses:
                decay = exp(-log(2) * (day - previous) / cfg['mood_half_life_days'])
                v = max(-1, min(1, v * decay + valence))
                a = max(0, min(1, a * decay + arousal))
                previous = day
            decay = exp(-log(2) * (now - previous) / cfg['mood_half_life_days'])
            return {'valence': v * decay, 'arousal': a * decay}
        # Preserve power-law impulses, bounding latent mass at *encoding*, not just display.
        # ponytail: exact history scan is O(n²); optimize only after profiling larger worlds.
        active = []
        for day, v, a, tau in impulses:
            active.append([day, v, a, tau])
            for column, limit in [(1, cfg['affect_budget']), (2, cfg['arousal_budget'])]:
                mass = sum(abs(x[column]) * (1 + (day - x[0]) / x[3]) ** -cfg['mood_alpha'] for x in active)
                if mass > limit:
                    for item in active:
                        item[column] *= limit / mass
        v = a = 0.0
        for day, valence, arousal, tau in active:
            weight = (1 + (now - day) / tau) ** -cfg['mood_alpha']
            v += valence * weight
            a += arousal * weight
        return {'valence': tanh(v), 'arousal': tanh(a)}

    def memories(self, owner, query, limit=6):
        if not isinstance(limit, int) or limit < 0:
            raise ValueError('Memory count must be a nonnegative integer')
        if 'cognition' in self.state['config']:
            from .cognition import views
            return views(self, owner, query, limit, collapse=True)
        agent = self.agent(owner)
        stop = {'the', 'a', 'an', 'i', 'me', 'my', 'you', 'your', 'is', 'was', 'and', 'or', 'to', 'of', 'in', 'for', 'it', 'do', 'what', 'with'}
        tokens = set(re.findall(r'\w+', query.lower())) - stop
        result = []
        mood = self.mood(owner)
        for observation in self.world.observations.get(owner, []):
            meta = agent['memory_meta'][observation.event_id]
            tier = meta.get('tier')
            if tier in sleep.HIDDEN:
                continue
            age = self.day - (meta['last_recall_day'] if meta['last_recall_day'] is not None else observation.day)
            availability = sleep.lability(age, self.state['config']['sleep']) if tier == 'buffer' else \
                recall_availability(age, meta['stability_days'])
            text = meta['summary'] if tier == 'gist' else observation.text
            overlap = len(tokens & (set(re.findall(r'\w+', (text + ' ' + meta['meaning']).lower())) - stop))
            # Declared retrieval policy: low-access episodes need a specific cue;
            # retained gist beliefs remain separate from the original details.
            if availability < self.state['config'].get('minimum_episode_accessibility', 0.15) and overlap < 3:
                continue
            score = 3 * overlap + availability + meta['importance'] + 0.2 * mood['valence'] * observation.valence
            result.append({'event': observation.event_id, 'day': observation.day, 'text': text,
                           'source': observation.source, 'kind': meta['kind'], 'meaning': meta['meaning'],
                           'confidence': meta['confidence'], 'availability': availability,
                           'provenance': meta['provenance'], 'score': score})
        # Availability is a ranking factor, not a calibrated Bernoulli recall probability.
        return sorted(result, key=lambda x: (x['score'], x['day'], x['event']), reverse=True)[:limit]

    def recall(self, owner, memory_id, cognitive_id, *, rehearse=False, affect=False):
        """Explicit cognitive event. Querying/printing never invokes this."""
        agent = self.agent(owner)
        if any(x['id'] == cognitive_id for x in self.state['updates']):
            raise ValueError('Duplicate cognitive event')
        if not agent['alive']:
            raise ValueError('A dead agent cannot recall')
        meta = agent['memory_meta'][memory_id]
        rehearse = rehearse and meta.get('tier') not in sleep.HIDDEN
        affect = affect and meta.get('tier') not in sleep.HIDDEN  # a forgotten memory brings back no feeling
        if rehearse and 'cognition' in self.state['config']:
            from .cognition import views
            available = next((m for m in views(self,owner,'',len(agent['memory_meta'])) if m['event']==memory_id),None)
            rehearse = bool(available and available['original_detail_available'])
        cfg = self.state['config']
        prior_rehearsals = [x['day'] for x in agent['recall_log'] if x['memory'] == memory_id and x['rehearsed']]
        reinforced = bool(rehearse and (not prior_rehearsals or self.day - max(prior_rehearsals) >= cfg['rehearsal_gap_days']))
        if reinforced and meta.get('tier') == 'buffer':
            sleep.rehearse(agent, memory_id)
        elif reinforced:
            meta['stability_days'] = min(cfg['max_stability_days'], meta['stability_days'] * (1 + cfg['rehearsal_gain']))
            meta['last_recall_day'] = self.day
        prior_affect = [x['day'] for x in agent['affect_events'] if x['memory'] == memory_id]
        if affect and (not prior_affect or self.day - max(prior_affect) >= cfg['recall_affect_gap_days']):
            obs = next(o for o in self.world.observations[owner] if o.event_id == memory_id)
            fraction = self.affect(owner).get('rumination_fraction', 0.25)
            # Habituation applies to modeled recall, never database inspection.
            fraction /= 1 + len(prior_affect)
            agent['affect_events'].append({'day': self.day, 'valence': obs.valence * fraction,
                                          'arousal': obs.arousal * min(1, fraction), 'memory': memory_id})
        agent['recall_log'].append({'id': cognitive_id, 'day': self.day, 'memory': memory_id, 'rehearsed': reinforced})
        self.state['updates'].append({'id': cognitive_id, 'kind': 'recall', 'owner': owner, 'day': self.day})

    def revise(self, owner, memory_id, meaning, confidence, evidence, update_id):
        agent = self.agent(owner)
        if not agent['alive']:
            raise ValueError('A dead agent cannot reinterpret a memory')
        number(confidence, 0, 1, 'confidence')
        if update_id in {x['id'] for x in self.state['updates']}:
            raise ValueError('Duplicate revision')
        if not evidence or any(e not in agent['memory_meta'] for e in evidence):
            raise ValueError('Revision requires evidence this agent received')
        meta = agent['memory_meta'][memory_id]
        meta['versions'].append({'day': self.day, 'meaning': meta['meaning'], 'confidence': meta['confidence'],
                                 'replaced_by': update_id})
        meta.update(meaning=meaning, confidence=confidence)
        self.state['updates'].append({'id': update_id, 'kind': 'revision', 'owner': owner,
                                     'day': self.day, 'memory': memory_id, 'evidence': list(evidence)})

    def consolidate(self, owner, *, api='http://127.0.0.1:8081', model='local', batch_size=8):
        """Personality-conditioned gist from received episodes; never world truth.

        Inferences retain episode evidence. Original observations are preserved;
        archiving does not mean a fact became false. This is not a latent-cause
        reconsolidation model and does not restore the rejected numeric rules.
        """
        agent = self.agent(owner)
        if not agent['alive'] or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError('Consolidation needs a living agent and positive batch size')
        episodes = [o for o in self.world.observations.get(owner, [])
                    if not agent['memory_meta'][o.event_id].get('consolidated')
                    and agent['memory_meta'][o.event_id].get('tier') not in sleep.HIDDEN][:batch_size]  # forgotten stays forgotten
        if len(episodes) < batch_size:
            return 0
        context = self.context(owner, 'Reflect on what these experienced episodes may mean for you.')
        context['episodes_to_consolidate'] = [{**asdict(o), 'meaning': agent['memory_meta'][o.event_id]['meaning'],
                                             'kind': agent['memory_meta'][o.event_id]['kind']} for o in episodes]
        if 'cognition' in self.state['config']:
            from .cognition import views
            accessible = {m['event']: m for m in views(self, owner, '', len(agent['memory_meta']))}
            context['episodes_to_consolidate'] = [
                {**entry, 'text': accessible[entry['event_id']]['text'],
                 'representation': accessible[entry['event_id']]['representation']}
                for entry in context['episodes_to_consolidate'] if entry['event_id'] in accessible]
            if not context['episodes_to_consolidate']:
                return 0
        context = compact(context)
        system = ('Reflect as the fictional agent using the supplied behavioral tendencies and received episodes. '
                  'Extract up to three tentative personal lessons or patterns, preserving disagreement and uncertainty. '
                  'Do not invent new incidents, diagnose conditions or turn testimony into verified events. '
                  'Return JSON with gists, a list of objects with text (string), confidence (0 to 1), '
                  'and evidence (a nonempty list of ids from episodes_to_consolidate). An empty gists list is allowed.')
        allowed = {o['event_id'] for o in context['episodes_to_consolidate']}
        def validate_gists(result):
            gists = result.get('gists')
            if not isinstance(gists, list) or len(gists) > 3:
                raise ValueError('Invalid consolidation output')
            for gist in gists:
                if not isinstance(gist, dict) or not isinstance(gist.get('text'), str) or not gist['text'].strip():
                    raise ValueError('Gist needs text')
                number(gist.get('confidence'), 0, 1, 'gist confidence')
                if not isinstance(gist.get('evidence'), list) or not gist['evidence'] or any(e not in allowed for e in gist['evidence']):
                    raise ValueError('Gist cites unavailable episodes')
        try:
            result = validated_json(system, context, validate_gists, api, model, 600)
        except InvalidModelOutput as exc:
            self.skip_model_step('consolidation', owner, exc)
            return 0
        gists = result['gists']
        digest = sha256(json.dumps(sorted(allowed)).encode()).hexdigest()[:16]
        for i, gist in enumerate(gists):
            key = f'gist-{digest}-{i}'
            self.believe(owner, key, gist['text'], gist['confidence'], gist['evidence'], f'{owner}:{key}')
            agent['beliefs'][key]['kind'] = 'inferred_semantic_gist'
        for episode in episodes:
            if episode.event_id in allowed:
                agent['memory_meta'][episode.event_id].update(consolidated=True, archived=True)
        self.state['updates'].append({'id': f'{owner}:consolidate:{digest}', 'kind': 'consolidation',
            'owner': owner, 'day': self.day, 'evidence': sorted(allowed), 'gist_count': len(gists)})
        return len(gists)

    def context(self, owner, situation, cues=(), options=None):
        agent = self.agent(owner)
        if not agent['alive']:
            raise ValueError('A dead agent cannot act')
        # Only committed self-identity/known formal roles and received private state;
        # no pending events, other agents' memories, or unrestricted world facts.
        context = {'identity': {'id': owner, 'name': self.state['entities'][owner]['name'],
                             **({'handle': '@' + self.state['entities'][owner]['facts']['handle']}
                                if self.state['entities'][owner]['facts'].get('handle') else {}),
                             'age_years': (self.day - agent['birth_day']) / 365.25,
                             'known_caregiving_roles': [
                                 {'dependent':key, 'name':entity['name']}
                                 for key,entity in self.state['entities'].items()
                                 if owner in entity['facts'].get('caregivers', [])]},
                'personality': describe(agent['facets']),
                'temporary_behavior': situational.expression(agent, self.day),
                'attachment_expectations': deepcopy(agent['attachment']), 'culture': deepcopy(agent['culture']),
                'simulated_day': self.day, 'mood': self.mood(owner),
                'goals': deepcopy(agent['goals']), 'relationships': deepcopy(agent['relationships']),
                'heard_about': deepcopy(agent['references']), 'beliefs': deepcopy(agent['beliefs']),
                'active_situation_rules': [r for r in deepcopy(agent['rules']) if set(r['cues']) <= set(cues)],
                'memories': self.memories(owner, situation), 'situation': situation, 'situation_cues': list(cues)}
        if self.state['config'].get('expression',{}).get('age_appropriate_actions',False):
            context['developmental_capabilities'] = situational.capability_context(context['identity']['age_years'])
        context['attachment_expectations']['learned_caregiver_models'] = development.attachment_expression(agent, self.day)
        if 'society' in self.state['config']:
            from . import society
            context['relationships']={key:society.relationship(self,value) for key,value in agent['relationships'].items()}
        if agent.get('culture',{}).get('expression_rules') or agent.get('additional_traits'):
            from . import expression
            context['cultural_and_additional_expression'] = expression.language(agent,cues)
        entity = self.state['entities'][owner]
        background_keys = {key for record in entity.get('background_versions', {}).values() for key in record['choices']}
        background_keys.update(key for record in entity.get('generated_biography',{}).values() for key in record['current_facts'])
        if background_keys:
            # Only canonical chosen slots become the agent's initialized personal
            # context. Generated overview prose never becomes facts or memories.
            context['background_facts'] = {key:deepcopy(entity['facts'][key]) for key in sorted(background_keys)}
        if entity.get('generated_biography'):
            context['biographical_context'] = {'policy':'synthetic_initialization_not_episodic_recall',
                'timeline':[deepcopy(epoch) for record in entity['generated_biography'].values() for epoch in record['timeline']][-12:]}
        if 'cognition' in self.state['config']:
            context['narrative_identity'] = deepcopy(agent.get('narrative_identity'))
            context['pending_questions'] = deepcopy([p for p in agent.get('probe_queue', []) if p['status'] == 'pending'][-4:])
            context['unresolved_references'] = deepcopy(agent.get('unresolved_references',{}))
        if 'planning' in self.state['config']:
            from .life_policy import planning_context
            context['practical_constraints'] = planning_context(self, owner)
            if self.state['config']['planning'].get('grounded_plans',False):
                for goal_view in context['goals'].values():
                    goal_view.pop('execution_plan_versions',None)
        state = agent.get('situational_state')
        if state and state['day'] == self.day and state['situation'] == situation:
            context['perceived_situation'] = deepcopy(state['perception'])
            active = set(state['perception']['active_rule_ids'])
            context['active_situation_rules'].extend(
                {'id': rule['id'], 'tendency': rule['narrative_shift']} for rule in agent.get('caps_rules', []) if rule['id'] in active)
        if options is not None:
            context['available_actions'] = deepcopy(options)
        repeat = self.repeated_question(owner)
        if repeat:
            context['repeated_question'] = repeat
        if 'society_layer' in self.state['config']:
            from .population.bridge import context as social_world
            world = social_world(self, owner)
            if world:
                context['social_world'] = world
        if 'household' in self.state['config']:
            from .household import view, conversation_memory
            context['physical_environment'] = view(self,owner)
            recent = conversation_memory(self, owner)
            if recent:
                context['conversation_so_far'] = recent
        return compact(context)

    def propose(self, owner, situation, *, api='http://127.0.0.1:8081', model='local', cues=(), options=None):
        validation_context = self.context(owner, situation, cues, options)
        context = deepcopy(validation_context)
        system = ('Simulate the supplied fictional agent at the current instant. Express the supplied behavioral tendencies, '
                  'current mood, memories, learned caregiver expectations, social knowledge, goals and situational tendencies in behavior. '
                  'Caregiver expectations may influence other relationships without making all people behave like that caregiver. '
                  'Personality descriptions express relative tendencies, not commands or diagnoses. '
                  'Reported claims and interpretations can be mistaken. Use only the agent context for personal knowledge. '
                  'Choose an intended action and a short goal plan; intentions do not establish outcomes. '
                  'Return a JSON object with action (string), speech (string), goal_id (existing id or null), '
                  'plan (list of strings), and memory_ids (list of supplied event ids).')
        if options is not None:
            system += ' Also return action_id chosen from available_actions. Choose only an offered action.'
            system += ' If the chosen option has speech_allowed false, speech must be empty. If plan_allowed is false, plan must be [].'
        age_appropriate = self.state['config'].get('expression',{}).get('age_appropriate_actions',False)
        infant = age_appropriate and validation_context['identity']['age_years'] < 2
        if age_appropriate:
            system += ' Use age-appropriate capabilities and only lived/received knowledge; do not give a child adult hindsight.'
        if infant:
            system += ' This agent is an infant: speech must be empty and plan must be []. Express only the offered nonverbal actions.'
        def validate_output(result):
            self.validate_decision(owner,result,context)
            if infant and (result['speech'] or result['plan']):
                raise ValueError('An infant action must have empty speech and plan []')
        decision = validated_json(system, context, validate_output, api, model)
        earlier = self.repeated_speech(owner, decision['speech'])
        if earlier:
            # One re-ask with the collision shown; a second repeat is kept, since people do repeat on purpose.
            context['repeat_notice'] = {'your_earlier_words': earlier['speech'], 'days_ago': round(self.day - earlier['day'], 1),
                'note': 'You were about to say almost exactly what you said before. Take into account what has happened '
                        'since then. Repeat yourself only if you mean to.'}
            decision = validated_json(system, context, validate_output, api, model)
        return {'owner': owner, 'day': self.day, 'decision': decision, 'context': context,
                'validation_context':validation_context}

    def appraise(self, owner, observation, *, api='http://127.0.0.1:8081', model='local', routine=False):
        """Estimate subjective meaning before encoding, from delivered content only.

        The controller supplies source, kind and information access. The model
        supplies an interpretation and provisional affect/salience estimates.
        It cannot add world facts, references or new recipients here.
        """
        if not observation.get('text') or not observation.get('source'):
            raise ValueError('Perceived text and source are required')
        if routine and 'caregiving' not in observation:
            habituated = self.habituated(owner, observation)
            if habituated:
                return habituated
        context = self.context(owner, observation['text'])
        context.pop('repeated_question', None)  # about the previous observation; this one is judged below
        # Collision check at encoding: the listener's own model judgment, over their own recent questions from this speaker.
        meta = self.agent(owner)['memory_meta']
        earlier = [{'id': o.event_id, 'days_ago': round(self.day - o.day, 1), 'text': o.text,
                    'times_asked_before': meta[o.event_id].get('times_asked_before', 0)}
                   for o in self.world.observations.get(owner, []) if o.source == observation['source'] and '?' in o.text
                   and meta[o.event_id].get('tier') not in sleep.HIDDEN][-5:] \
            if observation['source'] in self.state['entities'] and observation['source'] != owner and '?' in observation['text'] else []
        if earlier:
            context['earlier_questions_from_speaker'] = earlier
        context['new_observation'] = deepcopy(observation)
        for field in ('valence', 'arousal', 'importance', 'confidence', 'meaning'):
            context['new_observation'].pop(field, None)
        if 'caregiving' in observation:
            context['new_observation']['caregiving'] = {'caregiver': observation['caregiving']['caregiver']}
        resolve_references = self.state['config'].get('cognition',{}).get('reference_resolution',False)
        if resolve_references:
            from . import references
            context['reference_candidates'] = references.known(self,owner,observation)
        context = compact(context)
        system = ('Interpret the supplied observation from this fictional agent\'s perspective. '
                  'Use traits, attachment expectations, mood, goals, relationships and remembered experiences. '
                  'Distinguish perceived words from inferred intentions; preserve ambiguity. '
                  'Return a JSON object with meaning (string), valence (-1 to 1), arousal (0 to 1), '
                  'importance (0 to 1), confidence (0 to 1). These are model estimates, not measured psychology. '
                  'Calibrate to everyday life: routine events (a commute, someone entering or leaving a room, a usual '
                  'greeting) are near 0, within about 0.2 either way, unless this agent\'s context gives them special '
                  'meaning; beyond 0.8 either way is for rare, major events such as a serious loss, public humiliation or a '
                  'great success.')
        # Fuzzy-trace (Graph DB Memory Decay Implementation p.9): exact wording fades fast, gist remains.
        gist_needed = self.state['config'].get('cognition', {}).get('verbatim_days') is not None
        if gist_needed:
            system += (' Also return gist: one short plain sentence (at most 25 words) of what was said or happened, '
                       'as this agent would remember it a day later. Not a quotation; keep who did what.')
        if 'caregiving' in observation:
            system += (' Also return caregiving with the supplied caregiver id, responsiveness (0 to 1, '
                       'perceived attention and response to a need), and acceptance (0 to 1, perceived warmth '
                       'and permission to express difficulty). Task failure alone is not unresponsiveness or rejection.')
        if earlier:
            system += (' Also return asked_before: the id from earlier_questions_from_speaker that new_observation asks '
                       'essentially again, even in different words, or null if it asks something new. How the agent feels about being '
                       'asked again follows from its own tendencies and situation.')
        if resolve_references:
            system += (' Also return mentions (up to twelve objects with span exactly copied from new_observation.text '
                'and candidate_ids from reference_candidates, or [] for an unknown/ambiguous identity), '
                'and reminded_memory_ids (supplied memory ids actually brought to mind, or []). '
                'Names/pronouns do not create people, prove an account or imply a meeting.')
        def validate_appraisal(result):
            if not isinstance(result.get('meaning'), str):
                raise ValueError('Appraisal needs a meaning')
            for field, low in [('valence', -1), ('arousal', 0), ('importance', 0), ('confidence', 0)]:
                number(result.get(field), low, 1, field)
            if resolve_references:
                references.normalize(self,owner,observation,result.get('mentions',[]))
                reminders=result.get('reminded_memory_ids',[])
                if not isinstance(reminders,list) or not all(isinstance(mid,str) and mid in {m['event'] for m in context['memories']} for mid in reminders):
                    raise ValueError('Reminder cites a memory unavailable to this listener')
            if gist_needed and (not isinstance(result.get('gist'), str) or not result['gist'].strip()
                                or len(result['gist']) > 300):
                raise ValueError('Appraisal needs gist: one short sentence, at most 25 words')
            if earlier and result.get('asked_before') not in {None, *(q['id'] for q in earlier)}:
                raise ValueError('asked_before must be null or an id from earlier_questions_from_speaker')
            if 'caregiving' in observation:
                care = result.get('caregiving')
                if not isinstance(care, dict) or care.get('caregiver') != observation['caregiving']['caregiver']:
                    raise ValueError('Appraisal cannot invent or replace a caregiver')
                development.validate_caregiving(owner, {**observation, 'caregiving':care},
                                                self.state['entities'][owner]['facts'].get('caregivers', []))
        result = validated_json(system, context, validate_appraisal, api, model, 400)
        appraised = {**deepcopy(observation), **{k: result[k] for k in ('meaning', 'valence', 'arousal', 'importance', 'confidence')},
                     'appraisal_policy': 'local_llm_unfitted'}
        if gist_needed:
            appraised['gist'] = result['gist'].strip()
        if earlier and result.get('asked_before'):
            appraised['repeat_of'] = result['asked_before']
        if resolve_references:
            appraised['mentions'] = references.normalize(self,owner,observation,result.get('mentions',[]))
            appraised['cued_memories'] = list(dict.fromkeys([*observation.get('cued_memories',[]),*result.get('reminded_memory_ids',[])]))
        if 'caregiving' in observation:
            appraised['caregiving'] = deepcopy(result.get('caregiving'))
            if not isinstance(appraised['caregiving'], dict) or appraised['caregiving'].get('caregiver') != observation['caregiving']['caregiver']:
                raise ValueError('Appraisal cannot invent or replace a caregiver')
            development.validate_caregiving(owner, appraised, self.state['entities'][owner]['facts'].get('caregivers', []))
        return appraised

    def habituated(self, owner, observation):
        """Reuse this person's own recent full appraisal of an identical routine observation, without a model call.

        Lifestyle-policy reuse (Affordable Generative Agents, arXiv 2402.02053) with habituation: valence, arousal and
        importance shrink as 1/(1+n) over n reuses. A full appraisal older than routine_reappraisal_days is not reused,
        so the meaning can change over time. shortcut: exact text match and a 1/(1+n) curve, both provisional.
        """
        meta = self.agent(owner)['memory_meta']
        same = [o for o in self.world.observations.get(owner, []) if o.text == observation['text'] and o.source == observation['source']]
        if not same:
            return None
        last = meta[same[-1].event_id]
        full = last.get('reused_appraisal', same[-1].event_id)
        original = next(o for o in same if o.event_id == full)
        if self.day - original.day > self.state['config'].get('routine_reappraisal_days', 30):
            return None
        n = last.get('exposures', 0) + 1
        return {**deepcopy(observation), 'meaning': meta[full]['meaning'], 'valence': original.valence / (1 + n),
                'arousal': original.arousal / (1 + n), 'importance': meta[full]['importance'] / (1 + n),
                'confidence': meta[full]['confidence'], 'appraisal_policy': 'habituated_reuse_v1',
                'reused_appraisal': full, 'exposures': n, **({'gist': meta[full]['summary']} if meta[full].get('summary') else {})}

    def repeated_speech(self, owner, speech, recent=10, similarity=.8):
        """The owner's own recent committed action whose speech nearly matches, or None. Very short replies are exempt."""
        if len(speech.split()) < 3:
            return None
        from difflib import SequenceMatcher
        own = [a for a in self.state['actions'] if a['owner'] == owner and a['status'] != 'cancelled' and a['decision'].get('speech')]
        # Word-level, autojunk off: character-level autojunk drops spaces and vowels from lines over 200 characters,
        # so near-copies scored ~0.06 (environment-v2 run-2: 0 of 42 Rohan repeats caught).
        return next((a | {'speech': a['decision']['speech']} for a in reversed(own[-recent:])
                     if SequenceMatcher(None, speech.lower().split(), a['decision']['speech'].lower().split(),
                                        autojunk=False).ratio() >= similarity), None)

    def repeated_question(self, owner):
        """The latest question received today, if the owner's own appraisal linked it to an earlier one from
        the same person. Only the fact is supplied; the reaction comes from the person's signatures and tendencies."""
        received = self.world.observations.get(owner, [])
        if not received or self.day - received[-1].day > 1:
            return None
        meta = self.agent(owner)['memory_meta']
        latest = received[-1]
        if not meta[latest.event_id].get('repeat_of'):
            return None
        first = latest.event_id
        while meta[first].get('repeat_of'):
            first = meta[first]['repeat_of']
        first_day = next(o.day for o in received if o.event_id == first)
        return {'from': self.label(latest.source), 'times_asked_before': meta[latest.event_id]['times_asked_before'],
                'first_asked_days_ago': round(self.day - first_day, 1),
                'note': 'You have been asked this before. How you react (boredom, irritation, going quiet, pushing back, '
                        'leaving, or patience) depends on you.'}

    def validate_decision(self, owner, decision, context):
        if not isinstance(decision, dict) or not isinstance(decision.get('action'), str) or not decision['action'].strip():
            raise ValueError('Model decision needs a nonempty action')
        if not isinstance(decision.get('speech'), str) or not isinstance(decision.get('plan'), list) or not all(isinstance(p, str) for p in decision['plan']):
            raise ValueError('Model decision has invalid speech or plan')
        if decision.get('goal_id') is not None and decision['goal_id'] not in self.agent(owner)['goals']:
            raise ValueError('Model invented a goal id')
        ids = decision.get('memory_ids')
        if not isinstance(ids, list) or any(not isinstance(m, str) or m not in {x['event'] for x in context['memories']} for m in ids):
            raise ValueError('Model cited an unavailable memory')
        if 'available_actions' in context and decision.get('action_id') not in {a['id'] for a in context['available_actions']}:
            raise ValueError('Model chose an unavailable action')
        if 'available_actions' in context:
            selected=next(a for a in context['available_actions'] if a['id']==decision['action_id'])
            if selected.get('speech_allowed') is False and decision['speech']:
                raise ValueError('This action requires empty speech')
            if selected.get('plan_allowed') is False and decision['plan']:
                raise ValueError('This action requires an empty plan')

    def commit_action(self, action_id, proposal):
        owner = proposal['owner']
        if proposal['day'] != self.day or not self.agent(owner)['alive']:
            raise ValueError('Stale proposal or dead actor')
        if any(a['id'] == action_id for a in self.state['actions']):
            raise ValueError('Duplicate action')
        # Context equality prevents committing an intention after intervening experiences.
        old_context = proposal['context']
        validation_context = proposal.get('validation_context',old_context)
        current = self.context(owner, old_context['situation'], old_context['situation_cues'], old_context.get('available_actions'))
        if validation_context != current:
            raise ValueError('Agent state changed since proposal')
        self.validate_decision(owner, proposal['decision'], old_context)
        self.state['actions'].append({'id': action_id, 'owner': owner, 'day': self.day,
                                      'decision': deepcopy(proposal['decision']), 'status': 'intended',
                                      'temporary_offsets': situational.offsets(self.agent(owner), self.day)})
        goal_id = proposal['decision'].get('goal_id')
        if goal_id:
            self.agent(owner)['goals'][goal_id]['plan'] = list(proposal['decision']['plan'])
        for mid in dict.fromkeys(proposal['decision']['memory_ids']):
            detailed = next(m for m in old_context['memories'] if m['event'] == mid).get('original_detail_available', True)
            self.recall(owner, mid, f'{action_id}:used-memory:{mid}', rehearse=detailed, affect=True)
        # The controller schedules the resulting world event; an LLM cannot award itself success.

    def save(self, path):
        path = Path(path)
        if path.suffix in ('.sqlite','.db'):
            from .graph_store import save
            result=save(path,self.state)
            self._publish_graph_view()
            return result
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(json.dumps(self.state, indent=2, allow_nan=False) + '\n')
        temporary.replace(path)
        self._publish_graph_view()

    def _publish_graph_view(self):
        if self.state['config'].get('cognition',{}).get('graphiti_retrieval'):
            try:
                from .graphiti_bridge import publish
                publish(self)
            except (OSError,ValueError,RuntimeError,sqlite3.Error) as exc:
                import warnings
                warnings.warn('Checkpoint saved; graph outbox publication deferred: '+str(exc),RuntimeWarning)

    @classmethod
    def load(cls, path):
        with Path(path).open('rb') as source:
            sqlite = source.read(16) == b'SQLite format 3\x00'
        if sqlite:
            from .graph_store import load
            state=load(path)
        else:
            state = json.loads(Path(path).read_text())
        if state.get('version') != 1:
            raise ValueError('Unsupported checkpoint version')
        engine = cls(state['seed'], state['config']['mood_kernel'])
        engine.state = state
        # Reconstruct immutable observations; cognition metadata lives in the snapshot.
        for event in state['events']:
            if event['status'] != 'applied':
                continue
            recipients = {owner: cls._encoded_observation(state, event, owner, obs)
                          for owner, obs in event['observations'].items()}
            engine.world.add_event(event['id'], event['day'], event['description'], recipients)
        return engine

    @staticmethod
    def _encoded_observation(state, event, owner, obs):
        """Rebuild original encoding, not the current rehearsed accessibility."""
        cfg = state['config']
        meta = state['agents'][owner]['memory_meta'][event['id']]
        # Legacy snapshots lack the explicit encoding value; explicit observation
        # stability or the unchanged historical encoding policy supplies a fallback.
        original = meta.get('encoding_stability_days', obs.get('stability_days',
            cfg['memory_base_stability_days'] * (1 + cfg['memory_importance_weight'] * obs.get('importance', 0) +
                                               cfg['memory_arousal_weight'] * obs.get('arousal', 0))))
        return Observation(event['id'], event['day'], obs['text'], obs['source'],
                           obs.get('valence', 0), obs.get('arousal', 0), original)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint')
    parser.add_argument('--agent', required=True)
    parser.add_argument('--situation', required=True)
    parser.add_argument('--api', default='http://127.0.0.1:8081')
    parser.add_argument('--model', default='local')
    parser.add_argument('--context-only', action='store_true')
    parser.add_argument('--commit-action', help='Record the returned intention under this unique action id')
    parser.add_argument('--save', help='Save the checkpoint after committing an intention')
    args = parser.parse_args()
    if bool(args.commit_action) != bool(args.save) or (args.context_only and args.commit_action):
        parser.error('--commit-action and --save must be supplied together, without --context-only')
    engine = Engine.load(args.checkpoint)
    result = engine.context(args.agent, args.situation) if args.context_only else engine.propose(
        args.agent, args.situation, api=args.api, model=args.model)
    if args.commit_action:
        engine.commit_action(args.commit_action, result)
        engine.save(args.save)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
