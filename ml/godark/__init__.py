"""Go-dark risk: the chance a moving Class A ship goes silent (a gap of ours opens) in the next 1, 6 or 24 h (#121).

Targets are named as the frontend's RiskScore and the backend's `scores` rows: dark_6h (primary), dark_1h, dark_24h.
"""
import os

# The training desktop is shared with other jobs: cap every run's threads (LightGBM, OpenMP, BLAS) at 6. Set before
# lightgbm or numpy load; an explicit environment value wins.
MAX_THREADS = 6
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, str(MAX_THREADS))

TARGET_NAMES = {3600: "dark_1h", 6 * 3600: "dark_6h", 24 * 3600: "dark_24h"}
PRIMARY_HORIZON_S = 6 * 3600
