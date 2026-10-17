"""Society layer: a lazy, deterministic implicit population (design: 'MiroFish Society Layer v2').

Every number is a config entry in devsim/policies/society-layer.json, tagged V (verified, source named),
D (design default, unverified) or U (unverified figure). Only V values may be cited as evidence.
"""
from .core import Population, settings  # noqa: F401
