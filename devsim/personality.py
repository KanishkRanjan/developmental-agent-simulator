"""Compile internal facet percentiles to bounded behavioral language.

Source: Personality Structures pp.10-11; Profiling Methods p.2, section 1d;
the shared conversation's personality pipeline and final benchmark request.
Descriptors and selection thresholds below are engineering choices. They
are not fitted psychometric translations or a validated TGA mapping.
"""

# (higher-score tendency, lower-score tendency), kept facet-specific.
BEHAVIORS = {
    'N1': ('anticipate possible problems and seek reassurance under uncertainty', 'remain relatively unworried when outcomes are uncertain'),
    'N2': ('feel irritation more readily when frustrated', 'be slow to anger when frustrated'),
    'N3': ('become discouraged more readily after setbacks', 'maintain their spirits relatively well after setbacks'),
    'N4': ('feel self-conscious when being evaluated', 'feel relatively unselfconscious when being evaluated'),
    'N5': ('find immediate temptations harder to resist', 'find immediate temptations easier to resist'),
    'N6': ('feel overwhelmed more readily under pressure', 'feel relatively capable of coping under pressure'),
    'E1': ('approach others warmly and readily', 'take time to warm up to unfamiliar people'),
    'E2': ('enjoy frequent contact with groups', 'prefer a smaller amount of social contact'),
    'E3': ('speak up and advocate their preferences', 'hold back or defer before voicing their preferences'),
    'E4': ('prefer a busy and energetic pace', 'prefer a slower and more unhurried pace'),
    'E5': ('seek stimulating and exciting experiences', 'prefer quieter and less stimulating experiences'),
    'E6': ('express enthusiasm and positive feelings readily', 'express positive feelings in a more reserved way'),
    'O1': ('explore imaginative possibilities and fantasy', 'focus on concrete, readily observable possibilities'),
    'O2': ('notice and value artistic and aesthetic experiences', 'give artistic and aesthetic experiences less attention'),
    'O3': ('notice and explore their own feelings', 'give their inner emotional experience less attention'),
    'O4': ('try unfamiliar activities and experiences', 'prefer familiar activities and routines'),
    'O5': ('enjoy exploring abstract ideas and complex questions', 'prefer practical questions to extended abstract discussion'),
    'O6': ('question conventions and consider alternative ways of doing things', 'value familiar conventions and established ways of doing things'),
    'A1': ('initially give others the benefit of the doubt', 'initially check others\' claims and motives cautiously'),
    'A2': ('communicate candidly and straightforwardly', 'be guarded and strategic about what they disclose'),
    'A3': ('notice others\' needs and offer assistance', 'prioritize their own demands before offering assistance'),
    'A4': ('seek compromise when preferences conflict', 'stand their ground when preferences conflict'),
    'A5': ('avoid emphasizing their own status and achievements', 'draw attention to their own strengths and achievements'),
    'A6': ('be moved by others\' difficulties', 'approach others\' difficulties in a more detached way'),
    'C1': ('feel confident in their ability to handle tasks', 'doubt their ability until they have concrete reassurance'),
    'C2': ('organize materials and prefer orderly surroundings', 'tolerate disorder and use flexible arrangements'),
    'C3': ('feel a strong obligation to follow through on commitments', 'treat commitments more flexibly when circumstances change'),
    'C4': ('set demanding goals and invest in achievement', 'be satisfied with less demanding achievement goals'),
    'C5': ('persist with tasks despite boredom', 'find it harder to continue once a task becomes tedious'),
    'C6': ('consider consequences before deciding', 'decide quickly without prolonged deliberation'),
}


def describe(facets, max_facets=8):
    """Return text only; no raw scores, questionnaire names or scales.

    Extreme-decile facets have priority. If none exist, retain up to four
    moderately distinctive facets, with explicitly moderate wording. This
    fallback is a declared adaptation: an all-moderate profile must not
    silently become the base model's unknown default personality.
    """
    ranked = sorted(facets, key=lambda k: (-abs(facets[k] - 50), k))
    selected = [k for k in ranked if facets[k] <= 10 or facets[k] >= 90][:max_facets]
    if not selected:
        selected = [k for k in ranked if abs(facets[k] - 50) >= 10][:min(4, max_facets)]
    lines = []
    for key in selected:
        value = facets[key]
        qualifier = 'Strong tendency to ' if value <= 10 or value >= 90 else 'Somewhat inclined to '
        lines.append(qualifier + BEHAVIORS[key][0 if value >= 50 else 1] + '.')
    if not lines:
        lines.append('No unusually pronounced disposition is specified; use a balanced, context-sensitive range of reactions.')
    return {'policy': 'behavioral_language_v1', 'tendencies': lines,
            'expression': 'These are tendencies, not obligations. Let the situation, goals, relationships and prior experiences shape their expression. Do not turn one disposition into a constant caricature or a diagnosis.'}
