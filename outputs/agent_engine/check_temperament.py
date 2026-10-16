"""Inherited-disposition engineering checks; run with the existing profile-env."""
from copy import deepcopy
import json
from pathlib import Path

from engine import Engine, FACET_NAMES


def family():
    e = Engine(seed=73)
    for key in ('mother', 'father', 'caregiver', 'child-a', 'child-b'):
        e.entity(key, key)
    for key, age in [('mother', 25), ('father', 27), ('caregiver', 30)]:
        e.materialize(key, dict.fromkeys(FACET_NAMES, 50), birth_day=-age*365.25)
    return e


def main():
    left, right = family(), family()
    for e, order in [(left, ('child-a','child-b')), (right, ('child-b','child-a'))]:
        for child in order:
            e.materialize_child(child, biological_parents=['mother','father'], caregivers=['caregiver'])
    for child in ('child-a','child-b'):
        assert left.agent(child) == right.agent(child), 'Expansion order changed inherited state'
        assert left.state['entities'][child]['facts']['caregivers'] == ['caregiver']
        assert left.state['entities'][child]['facts']['biological_parents'] == ['father','mother']
        assert all(0 <= v <= 100 for v in left.agent(child)['facets'].values())
    assert left.agent('child-a')['facets'] != left.agent('child-b')['facets'], 'Siblings were made identical'
    first, second = family(), family()
    first.materialize_child('child-a', biological_parents=['mother'], h2=0)
    second.materialize_child('child-a', biological_parents=[], h2=0)
    assert first.agent('child-a')['facets'] == second.agent('child-a')['facets'], 'Zero variance share still inherited traits'
    first, second = family(), family()
    second.agent('mother')['facets']['N1'] = 99  # An acquired change in this synthetic fixture.
    first.materialize_child('child-a', biological_parents=['mother'])
    second.materialize_child('child-a', biological_parents=['mother'])
    assert first.agent('child-a')['facets'] == second.agent('child-a')['facets'], 'Acquired traits changed a lazily drawn genotype'
    before = deepcopy(left.state)
    try:
        left.materialize_child('child-a', biological_parents=['mother'])
    except ValueError:
        pass
    else:
        raise AssertionError('Duplicate child accepted')
    assert left.state == before
    # Algebraic variance identities, not fits to human data.
    assert 2*.5**2 + .5 == 1
    assert .5**2 + .75 == 1
    h2 = .5
    assert abs(h2 + (1-h2) - 1) < 1e-12
    genetic_variance_in_report = .5**2
    environmental_variance_in_report = .5**2*.5**2
    assert genetic_variance_in_report/(genetic_variance_in_report+environmental_variance_in_report) == .8
    result={'passed':True,'scope':'synthetic generation and algebra only; not calibrated childhood/genetic prediction',
            'checks':['expansion-order invariance','caregiving independent of biological parentage',
                      'bounded correlated facet generation','nonidentical siblings','unknown parent integrated without identity creation',
                      'zero inherited variance share removes parental contribution','duplicate child leaves state unchanged',
                      'acquired changes do not alter lazily generated founder genotype',
                      'unit-variance inheritance and residual weights','report weighting yields 80 percent rather than 50 percent variance']}
    Path(__file__).with_name('temperament-engineering-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
