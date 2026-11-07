"""Parallel runner for the stress suite. Run from backend/.

    .venv/bin/python tests/stress/run_stress.py                          # quick, all cores but 4
    .venv/bin/python tests/stress/run_stress.py --scale full --workers 12 --replay data/raw/aisstream

Uses pytest-xdist (pip install -r tests/stress/requirements.txt). --workers defaults to the core count minus 4,
leaving headroom for the live backend and the Vite dev server. Never connects to AISStream or writes to Tiger.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", choices=["quick", "full"], default="quick")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 4))
    ap.add_argument("--replay", help="recorded raw log file or folder")
    ap.add_argument("--detector", choices=["dvm", "reference"], default="dvm")
    ap.add_argument("pytest_args", nargs="*", help="extra pytest arguments, after --")
    a = ap.parse_args()
    cmd = [sys.executable, "-m", "pytest", "tests/stress", "--stress", "--scale", a.scale, "--detector", a.detector,
           "-q", "-rxXs", "--durations=10", "-p", "no:cacheprovider"]
    if a.workers > 1:
        cmd += ["-n", str(a.workers), "--dist", "worksteal"]
    if a.replay:
        cmd += ["--replay", a.replay]
    cmd += a.pytest_args
    print(" ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=BACKEND)


if __name__ == "__main__":
    sys.exit(main())
