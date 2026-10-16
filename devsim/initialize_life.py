"""Create an explicit synthetic initial family; no inferred ancestry or biography."""
import argparse
from pathlib import Path

from .engine import Engine, FACET_NAMES


def initialize(inherited=False, integrated=False):
    engine = Engine(seed=42)
    for key, name in [('alex', 'Alex'), ('maya', 'Maya'), ('bea', 'Bea')]:
        engine.entity(key, name)
    # Synthetic initial dispositions; adult population data are not childhood norms.
    traits = dict.fromkeys(FACET_NAMES, 50)
    traits.update(N1=65, E3=35, C1=45)
    engine.materialize('maya', None if inherited else dict.fromkeys(FACET_NAMES, 50), birth_day=-25 * 365.25)
    if inherited:
        engine.materialize_child('alex', biological_parents=['maya'], caregivers=['maya'], birth_day=0)
    else:
        engine.materialize('alex', traits, birth_day=0, attachment={'caregiver_availability': 'unspecified'})
        engine.caregiver('alex', 'maya')
    engine.materialize('bea', dict.fromkeys(FACET_NAMES, 50), birth_day=0)
    if integrated:
        engine.entity('alex', 'Alex', {'health_status':'well'})
        engine.goal('alex', 'community-presentation', 'Prepare notes and materials for a community project presentation.', priority=.8)
        engine.goal('alex', 'friendship', 'Maintain time for friendships.', priority=.6)
        engine.agent('alex')['resources'] = {'money':100}
    return engine


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', type=Path, required=True)
    parser.add_argument('--inherited', action='store_true', help='Use provisional inherited latent dispositions; requires profile-env')
    parser.add_argument('--integrated', action='store_true', help='Seed competing goals/resources for integrated-demo.json')
    args = parser.parse_args()
    args.save.parent.mkdir(parents=True, exist_ok=True)
    initialize(args.inherited, args.integrated).save(args.save)
    print('Saved synthetic initial family')
