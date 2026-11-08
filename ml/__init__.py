"""POSEIDON training and evaluation. Run modules from the repo root: `ml/.venv/bin/python -m ml.core.run ...`.

Importing `ml` puts `backend/` on sys.path so `from dvm.predict import features` works: the feature code is shared
with the live predictor, so training and inference compute the same thing.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_BACKEND = str(REPO / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
