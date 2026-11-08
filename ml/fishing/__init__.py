"""Fishing in protected areas (#157): the chance a fishing vessel GFW saw fishing in our four regions fishes inside a
marine protected area next week. Trained on GFW fishing events pulled straight from the GFW API (`ml.fishing.fetch`),
without waiting for the backend ingest. GFW data is CC BY-NC 4.0.
"""
import os

MAX_THREADS = 6   # shared training desktop: cap LightGBM, OpenMP and BLAS threads (set before they load)
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, str(MAX_THREADS))
