"""Explicit, unfitted attachment and developmental policies.

Sources: Lifespan Development sections 3, 4 and 6; situational report's
distinction between enduring traits and temporary states. These algorithms
are engineering choices, not fitted ECR-R scores, genetic estimates, causal
Big Five coefficients or a complete psychological TESSERA implementation.
"""
from collections import defaultdict
from math import exp, floor, log

from .situation import bounded


def validate_trajectory(curves):
    if not isinstance(curves, dict) or set(curves) - set('NEOAC'):
        raise ValueError('Maturation curves use domain keys N/E/O/A/C')
    for points in curves.values():
        if not isinstance(points, list) or not points:
            raise ValueError('Maturation curve needs age/offset pairs')
        previous = -1
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError('Maturation point must be [age_years, offset]')
            age, delta = point
            bounded(age, 0, 1000)
            bounded(delta, -20, 20)
            if age <= previous:
                raise ValueError('Maturation ages must strictly increase')
            previous = age
    return curves


def curve_value(points, age):
    if age <= points[0][0]:
        return points[0][1]
    for (left, low), (right, high) in zip(points, points[1:]):
        if age <= right:
            return low + (high - low) * (age - left) / (right - left)
    return points[-1][1]


def maturity(agent, day):
    policy = agent.get('developmental_model')
    if not policy:
        return dict.fromkeys(agent['facets'], 0.0)
    age = (day - agent['birth_day']) / 365.25
    origin_age = (policy['origin_day'] - agent['birth_day']) / 365.25
    return {key: curve_value(policy['maturation'][key[0]], age) - curve_value(policy['maturation'][key[0]], origin_age)
            if key[0] in policy['maturation'] else 0.0 for key in agent['facets']}


def projected_traits(agent, day):
    model = agent.get('developmental_model')
    if not model:
        return dict(agent['facets'])
    delta = maturity(agent, day)
    return {key: max(0, min(100, value + model['learned_change'][key] + delta[key]))
            for key, value in model['initial_facets'].items()}


def validate_caregiving(owner, observation, caregivers):
    care = observation.get('caregiving')
    if care is None:
        return
    if not isinstance(care, dict) or set(care) != {'caregiver', 'responsiveness', 'acceptance'}:
        raise ValueError('Caregiving requires caregiver, responsiveness and acceptance')
    caregiver = care['caregiver']
    if caregiver not in caregivers or caregiver == owner or observation.get('kind', 'direct') != 'direct':
        raise ValueError('Caregiving learning requires a direct experience with a committed caregiver')
    if caregiver not in observation.get('encountered', []) + observation.get('references', []):
        raise ValueError('Caregiving experience must identify the perceived caregiver')
    bounded(care['responsiveness'], 0, 1)
    bounded(care['acceptance'], 0, 1)


def attachment_models(agent, day):
    """Read-only posterior proxies: early anchor and decaying later evidence.

    One day's observations contribute at most one unit per caregiver, so
    splitting an interaction into many records cannot multiply its influence.
    The 18-year split, four-unit neutral prior and 180-day recovery are visible
    provisional choices. No attachment category or clinical diagnosis follows.
    """
    grouped = defaultdict(list)
    for event in agent.get('caregiving_experiences', []):
        grouped[event['caregiver']].append(event)
    models = {}
    for caregiver, events in grouped.items():
        days = defaultdict(list)
        for event in events:
            days[floor(event['day'])].append(event)
        early, recent = [], []
        for group in days.values():
            stamp = sum(e['day'] for e in group) / len(group)
            row = (stamp, sum(1 - e['responsiveness'] for e in group) / len(group),
                   sum(1 - e['acceptance'] for e in group) / len(group))
            (early if (stamp - agent['birth_day']) / 365.25 < 18 else recent).append(row)
        weight = 4 + len(early)
        anxiety = (2 + sum(row[1] for row in early)) / weight
        avoidance = (2 + sum(row[2] for row in early)) / weight
        prototype = {'anxiety': anxiety, 'avoidance': avoidance}
        recent_weight = sum(exp(-log(2) * (day - row[0]) / 180) for row in recent)
        state = {key: (4 * prototype[key] + sum(row[index] * exp(-log(2) * (day - row[0]) / 180)
                      for row in recent)) / (4 + recent_weight)
                 for key, index in [('anxiety', 1), ('avoidance', 2)]}
        models[caregiver] = {'prototype': prototype, 'current': state,
                             'independent_days': len(days), 'evidence': [e['event'] for e in events]}
    return models


def attachment_expression(agent, day):
    result = []
    for caregiver, values in attachment_models(agent, day).items():
        anxiety = values['current']['anxiety']
        avoidance = values['current']['avoidance']
        expectations = []
        if anxiety < .4:
            expectations.append('Usually expects this caregiver to respond when support is needed.')
        elif anxiety > .6:
            expectations.append('Is uncertain whether this caregiver will respond and may seek reassurance.')
        else:
            expectations.append('Has mixed or limited expectations about this caregiver responding.')
        if avoidance < .4:
            expectations.append('Usually feels able to seek comfort or disclose difficulty to this caregiver.')
        elif avoidance > .6:
            expectations.append('May hold back from seeking comfort or disclosing difficulty to this caregiver.')
        else:
            expectations.append('Has mixed or limited expectations about disclosing difficulty to this caregiver.')
        result.append({'caregiver': caregiver, 'expectations': expectations,
                       'basis': 'limited experience' if values['independent_days'] < 3 else 'repeated received experiences',
                       'evidence': values['evidence'][-8:]})
    return result
