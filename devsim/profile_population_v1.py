"""Fit and sample bounded, correlated IPIP-NEO-120 facet profiles.

Install: pip install numpy pandas pyarrow scipy
Fit: python profile_population_v1.py fit --data IPIP120-SCORES.parquet --out model.json
Sample: python profile_population_v1.py sample --model model.json --count 5 --seed 42
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr, ndtri

KEY_PATH = Path(__file__).resolve().parent / 'data' / 'ipip_neo_120_key.json'
FACETS = [f'{domain}{i}' for domain in 'NEOAC' for i in range(1, 7)]
DERIVED_FACETS = dict(zip(
    [f'{domain}{i}' for domain in 'OC EAN'.replace(' ', '') for i in range(1, 7)],
    ['imagination', 'artistic_interests', 'emotionality', 'adventurousness', 'intellect', 'liberalism',
     'self_efficacy', 'orderliness', 'dutifulness', 'achievement_striving', 'self_discipline', 'cautiousness',
     'friendliness', 'gregariousness', 'assertiveness', 'activity_level', 'excitement_seeking', 'cheerfulness',
     'trust', 'morality', 'altruism', 'cooperation', 'modesty', 'sympathy',
     'anxiety', 'anger', 'depression', 'self_consciousness', 'immoderation', 'vulnerability']
))


def score_items(frame, key):
    """Score the specified derived parquet, whose item responses are already keyed."""
    scores = {}
    for facet in FACETS:
        members = [entry for entry in key['items'] if entry['facet'] == facet]
        assert len(members) == 4
        columns = []
        for entry in members:
            value = frame[f"i{entry['item']}"].to_numpy(dtype=np.float64)
            columns.append(value)
        scores[facet] = np.sum(columns, axis=0)
    return pd.DataFrame(scores)


def prepare(data_path):
    key = json.loads(KEY_PATH.read_text())
    item_columns = [f'i{i}' for i in range(1, 121)]
    columns = ['age'] + item_columns + [f'facet_{name}' for name in DERIVED_FACETS.values()]
    frame = pd.read_parquet(data_path, columns=columns)
    valid = frame['age'].between(18, 70) & frame[item_columns].ge(1).all(axis=1) & frame[item_columns].le(5).all(axis=1)
    scored = score_items(frame.loc[valid], key)
    assert scored.ge(4).all().all() and scored.le(20).all().all()
    for facet, name in DERIVED_FACETS.items():
        reference = frame.loc[valid, f'facet_{name}'].reset_index(drop=True)
        assert scored[facet].corr(reference) > 0.8, f'{facet} scoring disagrees with source'
    return scored


def fit(train):
    ranks = train.rank(axis=0, method='average').to_numpy(dtype=np.float64)
    latent = ndtri((ranks - 0.5) / len(train))
    corr = np.corrcoef(latent, rowvar=False)
    eigenvalues, vectors = np.linalg.eigh(corr)
    assert eigenvalues.min() > -1e-8
    corr = (vectors * np.maximum(eigenvalues, 1e-8)) @ vectors.T
    scales = np.sqrt(np.diag(corr))
    corr /= scales[:, None] * scales[None, :]
    return {
        'version': 1,
        'instrument': 'IPIP-NEO-120 raw 4-item facet sums (range 4–20)',
        'source': 'https://osf.io/tbmh5/ ; derived parquet with pre-keyed item responses: https://huggingface.co/datasets/ecorbari/IPIP120-SCORES',
        'facets': FACETS,
        'n_fit': len(train),
        'latent_correlation': corr.tolist(),
        'marginal_counts': [np.bincount(train[facet].to_numpy(dtype=int), minlength=21)[4:21].tolist() for facet in FACETS],
    }


def sample(model, count, seed):
    rng = np.random.default_rng(seed)
    corr = np.array(model['latent_correlation'])
    z = rng.multivariate_normal(np.zeros(len(FACETS)), corr, size=count)
    u = ndtr(z)
    values = np.column_stack([
        4 + np.minimum(np.searchsorted(np.cumsum(counts) / sum(counts), u[:, j], side='right'), 16)
        for j, counts in enumerate(model['marginal_counts'])
    ])
    return pd.DataFrame(values, columns=model['facets'])


def audit(real, generated):
    real_corr = real.corr().to_numpy()
    generated_corr = generated.corr().to_numpy()
    mask = np.triu(np.ones_like(real_corr, dtype=bool), 1)
    return {
        'heldout_n': len(real), 'generated_n': len(generated),
        'mean_abs_facet_mean_error': float(np.abs(real.mean() - generated.mean()).mean()),
        'mean_abs_facet_sd_error': float(np.abs(real.std() - generated.std()).mean()),
        'mean_abs_pairwise_correlation_error': float(np.abs(real_corr[mask] - generated_corr[mask]).mean()),
        'max_abs_pairwise_correlation_error': float(np.abs(real_corr[mask] - generated_corr[mask]).max()),
        'all_sampled_scores_in_range': bool(generated.ge(4).all().all() and generated.le(20).all().all()),
    }


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    fitting = sub.add_parser('fit')
    fitting.add_argument('--data', required=True)
    fitting.add_argument('--out', required=True)
    fitting.add_argument('--seed', type=int, default=42)
    sampling = sub.add_parser('sample')
    sampling.add_argument('--model', required=True)
    sampling.add_argument('--count', type=int, default=5)
    sampling.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.command == 'fit':
        scored = prepare(args.data)
        shuffled = np.random.default_rng(args.seed).permutation(len(scored))
        cut = int(0.8 * len(scored))
        train = scored.iloc[shuffled[:cut]].reset_index(drop=True)
        heldout = scored.iloc[shuffled[cut:]].reset_index(drop=True)
        model = fit(train)
        generated = sample(model, len(heldout), args.seed + 1)
        model['audit'] = audit(heldout, generated)
        Path(args.out).write_text(json.dumps(model, separators=(',', ':')) + '\n')
        print(json.dumps({'n_valid': len(scored), **model['audit']}, indent=2))
    else:
        model = json.loads(Path(args.model).read_text())
        print(sample(model, args.count, args.seed).to_json(orient='records', indent=2))


if __name__ == '__main__':
    main()
