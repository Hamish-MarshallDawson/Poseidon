"""Stress suite switches. Off by default: plain `pytest tests` skips everything marked `stress`.

    .venv/bin/python -m pytest tests/stress --stress                      # quick, laptop
    .venv/bin/python tests/stress/run_stress.py --scale full --workers 12 # full, parallel (pytest-xdist)
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

SCALES = {
    # ships in the background fleet, simulated hours, Class A report interval, seeds per test, fuzz cases, burst size
    "quick": dict(ships=40, hours=2.0, interval_s=30, seeds=2, fuzz=4_000, burst=30_000),
    # full: about 0.5 GB per worker (1.5 KB per message held in memory); 12 workers need about 6 GB free
    "full": dict(ships=300, hours=3.0, interval_s=10, seeds=12, fuzz=300_000, burst=400_000),
}


def pytest_addoption(parser):
    g = parser.getgroup("stress")
    g.addoption("--stress", action="store_true", help="run the stress and failure suite (off by default)")
    g.addoption("--scale", choices=sorted(SCALES), default=os.environ.get("DVM_STRESS_SCALE", "quick"))
    g.addoption("--replay", default=os.environ.get("DVM_STRESS_REPLAY"),
                help="recorded raw log (.jsonl or .jsonl.gz file, or a folder of them) to replay")
    g.addoption("--detector", choices=["dvm", "reference"], default="dvm",
                help="dvm = Jake's dvm/gaps.py (default); reference = this suite's own checker")


def pytest_configure(config):
    config.addinivalue_line("markers", "stress: stress and failure suite; run with --stress")


def _opt(config, name, default=None):
    try:
        return config.getoption(name)
    except ValueError:   # options are only registered when pytest starts in or below tests/stress
        return default


def pytest_collection_modifyitems(config, items):
    if _opt(config, "--stress", False) or os.environ.get("DVM_STRESS") == "1":
        return
    skip = pytest.mark.skip(reason="stress suite: run `pytest tests/stress --stress`")
    for item in items:
        if "stress" in item.keywords:
            item.add_marker(skip)


def _replay_paths(config):
    p = _opt(config, "--replay")
    if not p:
        return []
    path = Path(p)
    if not path.is_dir():
        return [path]
    plain = sorted(path.glob("**/*.jsonl"))
    # Both X.jsonl and X.jsonl.gz means the gzip on rotation never finished (rawlog.py gzips in a daemon thread
    # and only then deletes the plain file), so the .gz is truncated: the plain file is the complete copy.
    gz = [g for g in sorted(path.glob("**/*.jsonl.gz")) if not g.with_suffix("").exists()]
    return sorted(plain + gz, key=lambda f: f.name)


def pytest_generate_tests(metafunc):
    if "seed" in metafunc.fixturenames:
        n = SCALES[_opt(metafunc.config, "--scale", "quick")]["seeds"]
        metafunc.parametrize("seed", range(n))
    if "replay_file" in metafunc.fixturenames:   # one test per hour file, so xdist spreads them over the cores
        files = _replay_paths(metafunc.config)
        metafunc.parametrize("replay_file", files or [None], ids=[f.name for f in files] or ["no-replay"])


@pytest.fixture(scope="session")
def replay_window(request):
    """The first three consecutive hour files, merged: enough for a 45 min switch-off with a baseline."""
    files = _replay_paths(request.config)[:3]
    if not files:
        pytest.skip("no recorded log: pass --replay <file or folder>")
    return files


@pytest.fixture(scope="session")
def scale(request):
    return SCALES[_opt(request.config, "--scale", "quick")]


@pytest.fixture
def detector(request):
    from tests.stress import adapter
    which = _opt(request.config, "--detector", "dvm")
    det = adapter.make(which)
    if det is None:
        pytest.skip("dvm/gaps.py GapDetector is not merged yet; run with --detector reference to check the suite")
    return det
