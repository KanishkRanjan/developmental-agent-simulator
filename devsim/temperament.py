"""Illustrative inherited latent dispositions using the existing adult copula.

This is not a child norm or a measured genetic model. h2 is a simulated
population variance share on latent Gaussian coordinates, not a fraction of
an individual's personality, and caregiving is independent of parentage.
The report's 0.5*G + 0.5*Normal(0,0.5) example does not give 50% genetic
variance. Square-root variance weights and explicit Mendelian residuals
keep unit variance for unrelated founders under the stated assumptions.
"""
from hashlib import sha256
import json
from pathlib import Path

from . import DATA_DIR
from .situation import bounded


def inherited(state, key, parents, h2):
    """Pure preparation; optional existing numpy/scipy environment is required."""
    import numpy as np
    from scipy.special import ndtr, ndtri
    bounded(h2, 0, 1)
    model = json.loads(DATA_DIR.joinpath('profile_population_v1_model.json').read_text())
    covariance = np.array(model['latent_correlation'])
    facets = model['facets']
    def noise(identity, purpose):
        seed = int.from_bytes(sha256(f'{state["seed"]}:{identity}:{purpose}'.encode()).digest()[:8], 'big')
        return np.random.default_rng(seed).multivariate_normal(np.zeros(len(facets)), covariance)
    inherited_parents = {}
    for parent in parents:
        agent = state['agents'][parent]
        existing = agent.get('temperament_origin')
        if existing:
            if existing['h2'] != h2:
                raise ValueError('A family cannot silently change its latent variance policy')
            inherited_parents[parent] = existing
        else:
            # Lazily drawing a founder genotype must not inherit later acquired changes.
            original = agent.get('initial_facets', agent.get('developmental_model', {}).get('initial_facets', agent['facets']))
            z = ndtri(np.clip([original[f] / 100 for f in facets], 1e-6, 1 - 1e-6))
            genetic = np.sqrt(h2) * z + np.sqrt(1 - h2) * noise(parent, 'conditional-founder')
            inherited_parents[parent] = {'h2': h2, 'genetic_latent': genetic.tolist(), 'parents': [],
                'policy': 'conditional_latent_founder_unfitted', 'population_limit': 'adult reference; not child norms',
                'conditioning': 'original materialization dispositions when available; legacy fallback explicitly population-limited'}
    # Two unrelated parents: Var((G1+G2)/2)=R/2, plus segregation R/2.
    # One known parent: remaining R*3/4 integrates unknown parent + segregation.
    if parents:
        genetic = .5 * sum(np.array(inherited_parents[p]['genetic_latent']) for p in parents)
        genetic += np.sqrt(1 - len(parents) / 4) * noise(key, 'segregation')
    else:
        genetic = noise(key, 'founder')
    latent = np.sqrt(h2) * genetic + np.sqrt(1 - h2) * noise(key, 'nonshared')
    percentiles = {}
    for facet, probability, counts in zip(facets, ndtr(latent), model['marginal_counts']):
        cumulative = np.cumsum(counts)
        index = min(int(np.searchsorted(cumulative / cumulative[-1], probability, side='right')), 16)
        percentiles[facet] = round(100 * (sum(counts[:index]) + counts[index] / 2) / sum(counts), 2)
    origin = {'h2': h2, 'genetic_latent': genetic.tolist(), 'nonshared_latent': (latent - np.sqrt(h2) * genetic).tolist(),
              'parents': list(parents), 'policy': 'additive_latent_family_unfitted',
              'population_limit': 'adult reference distribution extrapolated to initial dispositions; not child norms'}
    return percentiles, origin, inherited_parents
