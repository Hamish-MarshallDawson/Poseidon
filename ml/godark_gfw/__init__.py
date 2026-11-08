"""Go-dark risk from Global Fishing Watch history alone (#121): the chance a ship GFW saw in our four regions starts
a GFW gap event (AIS likely disabled on purpose, anywhere in the world) within the next 7 or 30 days.

Built on months of GFW backfill rather than our own few days of live AIS, so it can show a learning curve: more
months of history, better model. GFW data is CC BY-NC 4.0.
"""
import os

MAX_THREADS = 6   # shared training desktop: cap LightGBM, OpenMP and BLAS threads (set before they load)
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, str(MAX_THREADS))
