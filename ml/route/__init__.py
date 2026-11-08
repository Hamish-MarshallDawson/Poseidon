"""Route prediction: where a ship (dark or not) will be in 1, 3, 6 and 24 h, with an uncertainty radius."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HORIZONS_S = (3600, 3 * 3600, 6 * 3600, 24 * 3600)
# trained by default: the contract's horizons plus 30 min, 2 h and 12 h, so gap-length predictions interpolate well
TRAIN_HORIZONS_S = (1800, 3600, 2 * 3600, 3 * 3600, 6 * 3600, 12 * 3600, 24 * 3600)
