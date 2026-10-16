"""Provisional CAPS-style signatures and temporary states, separate from traits.

Source: Situational Personality Variability report pp.10–11 (procedure and
state update). Domain modifiers are applied equally to that domain's six
facets as an explicit engineering policy, not a validated TGA conversion.
Recovery uses elapsed simulated days, replacing the report's per-tick decay
so inserting a checkpoint or inspecting context cannot accelerate recovery.
No empirical effect size or human-prediction claim is attached to these rules.
"""
from math import exp, isfinite, log

from personality import BEHAVIORS

DIMENSIONS = ('Duty', 'Intellect', 'Adversity', 'Mating', 'Positivity', 'Negativity', 'Deception', 'Sociality')


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
    if not isinstance(result, dict) or 'rules' not in result:
        raise ValueError('Missing root JSON key rules: return {"rules": [five signature objects]}')
    rules = result['rules']
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


def signature_stage(age):
    """Scenario refresh boundaries, not a claim of discrete psychological stages."""
    return sum(age >= boundary for boundary in (12,18,40,65))


def bounded(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not low <= value <= high:
        raise ValueError('Invalid situation parameter')
    return value


def validate_rules(rules):
    if not isinstance(rules, list) or not 1 <= len(rules) <= 8:
        raise ValueError('Expected one to eight situational signatures')
    ids = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError('Signature must be an object')
        for field in ('id', 'trigger_context', 'narrative_shift'):
            if not isinstance(rule.get(field), str) or not rule[field].strip() or len(rule[field]) > 1000:
                raise ValueError('Signature needs bounded text fields')
        if rule['id'] in ids or rule.get('dimension') not in DIMENSIONS:
            raise ValueError('Duplicate signature or unknown dimension')
        ids.add(rule['id'])
        modifiers = rule.get('state_modifiers')
        if not isinstance(modifiers, dict) or not modifiers or set(modifiers) - set('NEOAC'):
            raise ValueError('Signature needs known domain modifiers')
        for delta in modifiers.values():
            bounded(delta, -10, 10)
    return rules


def offsets(agent, day):
    record = agent.get('situational_state')
    if not record:
        return dict.fromkeys(agent['facets'], 0.0)
    elapsed = day - record['day']
    if elapsed < 0:
        raise ValueError('Situational state lies in the future')
    half_life = bounded(record['recovery_half_life_days'], 1e-6, 36525)
    weight = exp(-log(2) * elapsed / half_life)
    return {key: value * weight for key, value in record['offsets'].items()}


def transition(agent, day, perception, half_life):
    """Validate everything before returning a new state; no mutation or RNG."""
    bounded(half_life, 1e-6, 36525)
    rules = agent.get('caps_rules', [])
    if not isinstance(perception, dict) or not isinstance(perception.get('meaning'), str):
        raise ValueError('Situation construal needs a subjective meaning')
    dimensions = perception.get('dimensions')
    if not isinstance(dimensions, dict) or set(dimensions) != set(DIMENSIONS):
        raise ValueError('Situation construal needs all eight dimensions')
    for strength in dimensions.values():
        bounded(strength, 0, 1)
    bounded(perception.get('controllability'), 0, 1)
    active = perception.get('active_rule_ids')
    if not isinstance(active, list) or not all(isinstance(key, str) for key in active) or len(set(active)) != len(active):
        raise ValueError('Invalid active rule ids')
    available = {rule['id']: rule for rule in rules}
    if any(key not in available for key in active):
        raise ValueError('Construal invented a signature')
    changes = offsets(agent, day)
    # Sum simultaneous influences, then bound once; no arbitrary rule-order effect.
    for key in changes:
        changes[key] += sum(available[r]['state_modifiers'].get(key[0], 0) *
                            dimensions[available[r]['dimension']] for r in active)
        changes[key] = max(-20, min(20, changes[key]))
        changes[key] = max(0, min(100, agent['facets'][key] + changes[key])) - agent['facets'][key]
    return {'day': day, 'offsets': changes, 'recovery_half_life_days': half_life,
            'perception': perception, 'policy': 'caps_elapsed_time_v1_unfitted'}


def expression(agent, day):
    """Behavioral language only; numeric state stays internal."""
    changes = offsets(agent, day)
    selected = sorted((k for k in changes if abs(changes[k]) >= 1), key=lambda k: (-abs(changes[k]), k))[:6]
    tendencies = ['For now, more inclined to ' + BEHAVIORS[k][0 if changes[k] > 0 else 1] + '.' for k in selected]
    return {'policy': 'temporary_behavioral_language_v1', 'tendencies': tendencies,
            'scope': 'Temporary departures from the enduring dispositions; these can recover without changing those dispositions.'}
