"""Developmental agent simulator: persistent agents, memory, mood and development."""
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
DATA_DIR = PACKAGE_DIR / 'data'
POLICY_DIR = PACKAGE_DIR / 'policies'
# Gitignored local runtime state (virtual environments, Graphiti config/outbox).
LOCAL_STATE_DIR = REPO_ROOT / 'work'
GRAPHITI_START = REPO_ROOT / 'services' / 'graphiti-local' / 'start.py'
