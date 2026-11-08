"""Route and go-dark prediction (#121): shared features, the live predictor, the fast graders and read-only routes.

See dvm/predict/README.md. The app starts it with `start(store)` when PREDICT=1.
"""
from __future__ import annotations

import asyncio
from typing import Optional

_running = None   # the running Predictor, if any (for /health and the leaderboard)


async def start(store) -> None:
    """Wait for the store's setup (outcomes and the append-only trigger must exist), then run the predictor."""
    global _running
    from dvm import config
    from dvm.predict.predictor import Predictor

    while store.pool is None:
        await asyncio.sleep(1)
    _running = Predictor(store.url, config.PREDICT_MODEL_DIR, config.PREDICT_INTERVAL_S, config.PREDICT_SAMPLE)
    try:
        await _running.run()
    finally:
        await _running.close()


def health() -> Optional[dict]:
    return _running.health() if _running else None
