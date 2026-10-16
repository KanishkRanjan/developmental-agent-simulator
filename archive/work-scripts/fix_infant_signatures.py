from pathlib import Path
p=Path('outputs/agent_engine/situation.py')
s=p.read_text();marker='\ndef signature_stage(age):'
s=s.replace(marker,'''
# Scenario vocabulary prevents an infant's generated rules from introducing
# school/work/puzzle competence. These are representational limits, not norms.
INFANT_TRIGGERS = {
    'discomfort': ('Adversity', 'Current physical discomfort is felt.'),
    'familiar-presence': ('Sociality', 'A familiar caregiver is perceptibly nearby.'),
    'comfort': ('Positivity', 'Received soothing contact or attention is perceived.'),
    'novelty': ('Intellect', 'An unfamiliar sensory stimulus is present.'),
    'stimulation': ('Negativity', 'Current sensory stimulation feels overwhelming.'),
}
INFANT_REACTIONS = {
    'orient': 'Orient attention toward the immediate sensory cue.',
    'withdraw': 'Reduce engagement with the immediate stimulus.',
    'signal': 'Signal discomfort nonverbally.',
    'seek-contact': 'Seek familiar proximity or contact nonverbally.',
    'settle': 'Become quieter or more settled.',
}


def infant_rules(result):
    rules = result.get('rules')
    if not isinstance(rules, list) or len(rules) != 5:
        raise ValueError('Expected five bounded infant signatures')
    normalized = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {'id', 'trigger_id', 'reaction_id', 'state_modifiers'}:
            raise ValueError('Infant signatures require only catalog trigger/reaction ids and modifiers')
        if rule['trigger_id'] not in INFANT_TRIGGERS or rule['reaction_id'] not in INFANT_REACTIONS:
            raise ValueError('Unknown infant sensory trigger or nonverbal reaction')
        dimension, trigger = INFANT_TRIGGERS[rule['trigger_id']]
        normalized.append({'id': rule['id'], 'dimension': dimension, 'trigger_context': trigger,
                           'narrative_shift': INFANT_REACTIONS[rule['reaction_id']],
                           'state_modifiers': rule['state_modifiers']})
    return validate_rules(normalized)


def capability_band(age):
    return 'infant' if age < 2 else 'early-childhood' if age < 5 else 'child' if age < 12 else 'adolescent' if age < 18 else 'adult'


def capability_context(age):
    band = capability_band(age)
    limits = ('Nonverbal sensory responses only; no speech, abstract reasoning, verbal plans, puzzles, work or school competence.'
              if band == 'infant' else
              'Use simple immediate play, communication and caregiver interactions; no adult competence or hindsight.'
              if band == 'early-childhood' else
              'Use age-appropriate communication and reasoning from received experience; no assumed adult competence or hindsight.')
    return {'band': band, 'limits': limits, 'scope': 'scenario capability constraints, not measured developmental norms'}

''' + marker)
p.write_text(s)
p=Path('outputs/agent_engine/engine.py');s=p.read_text()
s=s.replace("stage = situational.signature_stage(age)\n", "stage = situational.signature_stage(age)\n        age_appropriate = self.state['config'].get('expression',{}).get('age_appropriate_actions',False)\n        band = situational.capability_band(age) if age_appropriate else None\n")
s=s.replace("if stage == original_stage and not (drift >= 5", "if stage == original_stage and (not age_appropriate or previous.get('capability_band') == band) and not (drift >= 5")
s=s.replace("result = validated_json(system, context, lambda r: situational.validate_rules(r.get('rules')), api, model, 1400)\n        rules = situational.validate_rules(result.get('rules'))", """infant = age_appropriate and age < 2
        if infant:
            context['infant_trigger_catalog'] = {key: value[1] for key,value in situational.INFANT_TRIGGERS.items()}
            context['infant_reaction_catalog'] = situational.INFANT_REACTIONS
            system = ('Construct five provisional sensory-response signatures for this fictional infant. '
                      'Use only catalog trigger and nonverbal reaction ids; no invented competence or biography. '
                      'Return JSON with rules: five objects containing only id (unique string), trigger_id, reaction_id, '
                      'and state_modifiers (affected N/E/O/A/C domains, shifts from -10 to 10). '
                      'These are simulation policies, not validated infant trait measurements.')
        validator = situational.infant_rules if infant else lambda r: situational.validate_rules(r.get('rules'))
        result = validated_json(system, context, validator, api, model, 1400)
        rules = validator(result)""")
s=s.replace("'facets_at_generation': dict(agent['facets']),", "'capability_band': band, 'facets_at_generation': dict(agent['facets']),")
s=s.replace("context['attachment_expectations']['learned_caregiver_models'] =", "if self.state['config'].get('expression',{}).get('age_appropriate_actions',False):\n            context['developmental_capabilities'] = situational.capability_context(context['identity']['age_years'])\n        context['attachment_expectations']['learned_caregiver_models'] =")
s=s.replace("'to satisfy a more specific trigger. Do not invent past experiences or new signatures.')", "'to satisfy a more specific trigger. Do not invent past experiences or new signatures. '\n                  'Respect developmental_capabilities when supplied. For an infant, meaning is a controller sensory/affective '\n                  'description, not a verbal self-report or evidence of abstract understanding.')")
p.write_text(s)
