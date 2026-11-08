"""One unattended improvement cycle on the server, for every target (run by the dvm-ml systemd timer).

    python -m ml.auto [--targets route,godark,fishing] [--rounds 1] [--proposals 3] [--no-retrain] [--no-deploy]

Order, all under one exclusive lock (ML_LOCK, default <ML_ARTIFACTS>/../auto.lock; a second cycle that finds it
held exits at once, so two trainings never overlap):
1. Recalibrate the live champions from the graded ledger (ml.core.recalibrate, --apply). Cheap and measured on our
   own feed; the predictor reloads champions.json every cycle, so no restart.
2. Per target: refresh its training data (a target's refresh command, best effort), then one loop
   (ml.core.loop: proposals from Gemini only when ML_GEMINI_API_KEY is set, a key of its own so the briefings'
   GEMINI_API_KEY quota is never touched; else the fixed list; trained and scored on the
   frozen held-out set; promoted only by the rule, with a second-seed confirmation).
3. Deploy (only with ML_DEPLOY_RETRAINED=1; off by default until the server registry's champions are the live
   ones, since a registry champion has only beaten earlier runs of the same registry): a run the loop promoted over an earlier registry champion (not the first run against the baseline) is
   copied into PREDICT_MODEL_DIR and named in champions.json, when its artifact is deployable. The first champion of
   a fresh registry is recorded but not deployed: it has not beaten anything the live system runs.
Writes <ML_ARTIFACTS>/reports/auto-status.json (last cycle) and appends to auto-history.jsonl.
CPU: training threads are capped by ML_THREADS (default 3 of the server's 6); the unit also sets Nice and MemoryMax.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

THREADS = os.getenv("ML_THREADS", "3")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, THREADS)

from ml.core import env  # noqa: E402,F401  (repo .env)
from ml.core.registry import DEFAULT_ARTIFACTS, open_registry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# Best-effort data refresh per target before its loop (module, args). A failure keeps the cached data.
REFRESH = {
    "route": [["ml.route.tiger", "--hours", os.getenv("ML_ROUTE_HOURS", "72")]],
    "godark": [["ml.godark.tiger"], ["ml.godark.replay"], ["ml.godark.dataset"]],
    "fishing": [["ml.fishing.fetch", "--minutes", "5"], ["ml.fishing.dataset"]],
}
DATA = {"route": os.getenv("ML_ROUTE_DATA", "tiger")}   # our own feed; "dma:14+tiger" where the archive is
DEPLOY_TARGET = {"route": "route", "godark": "godark"}   # targets the live predictor serves


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def refresh(target: str, log) -> list[dict]:
    out = []
    if os.getenv("ML_NO_REFRESH"):
        return out
    for cmd in REFRESH.get(target, []):
        t0 = time.time()
        p = subprocess.run([sys.executable, "-m", *cmd], cwd=ROOT, capture_output=True, text=True, timeout=1800)
        out.append({"cmd": " ".join(cmd), "rc": p.returncode, "s": round(time.time() - t0, 1),
                    "tail": (p.stderr or p.stdout)[-300:] if p.returncode else ""})
        log(f"refresh {target}: {' '.join(cmd)} rc={p.returncode} in {out[-1]['s']} s")
        if p.returncode:
            break
    return out


def deployable(artifact: Path) -> bool:
    try:
        m = json.loads((artifact / "model.json").read_text())
    except OSError:
        return False
    return m.get("deployable", True) is not False


def deploy(target: str, run: dict, models_dir: Path, log) -> str | None:
    src = Path(run["artifact"])
    if target not in DEPLOY_TARGET or not deployable(src):
        log(f"deploy {target}: {run['run_id']} not deployable here (kept in the registry)")
        return None
    dst = models_dir / run["run_id"]
    if not dst.exists():
        shutil.copytree(src, dst)
    sys.path.insert(0, str(ROOT / "backend"))
    from dvm.predict import artifact as backend_artifact   # the live loader is the gate
    backend_artifact.load(dst)
    champs = json.loads((models_dir / "champions.json").read_text())
    champs[DEPLOY_TARGET[target]] = dst.name
    tmp = models_dir / "champions.json.tmp"
    tmp.write_text(json.dumps(champs, indent=1))
    os.replace(tmp, models_dir / "champions.json")
    log(f"deploy {target}: champions.json -> {dst.name}")
    return dst.name


def cycle(targets: list[str], rounds: int, proposals: int, retrain: bool, do_deploy: bool, models_dir: Path,
          log=print) -> dict:
    from ml.core.loop import loop
    from ml.core.target import get_target
    status = {"started": now(), "targets": {}, "threads": THREADS, "models_dir": str(models_dir)}
    if os.getenv("TIGER_DATABASE_URL") and (models_dir / "champions.json").exists():
        try:
            from ml.core.recalibrate import recalibrate
            r = recalibrate(models_dir, os.environ["TIGER_DATABASE_URL"], apply=do_deploy, log=log)
            status["recalibrate"] = {"rows": r["rows"], "changed": r["changed"]}
        except Exception as e:   # never stops the retraining
            status["recalibrate"] = {"error": repr(e)[:300]}
            log(f"recalibrate failed: {e!r}")
    if not retrain:
        return status | {"finished": now()}
    reg = open_registry(None)
    # Gemini only with a key of its own: GEMINI_API_KEY belongs to the live briefings (free-tier quota).
    ml_key = os.getenv("ML_GEMINI_API_KEY")
    if ml_key:
        os.environ["GEMINI_API_KEY"] = ml_key
    else:
        os.environ.pop("GEMINI_API_KEY", None)
    dry = not ml_key
    for t in targets:
        st = status["targets"][t] = {"started": now()}
        try:
            spec = get_target(t)
            st["refresh"] = refresh(t, log)
            before = (reg.champion(t) or {}).get("run_id")
            out = loop(spec, rounds, reg=reg, k=proposals, dry_run=dry, data=DATA.get(t), log=log)
            after = (reg.champion(t) or {}).get("run_id")
            st |= {"loop_id": out["loop_id"], "proposer": "default (no ML_GEMINI_API_KEY)" if dry else "gemini",
                   "rounds": out["rounds"], "champion_before": before, "champion_after": after}
            retrained_ok = os.getenv("ML_DEPLOY_RETRAINED", "0") == "1"
            if after and after != before and before and do_deploy and retrained_ok:
                st["deployed"] = deploy(t, reg.get_run(after), models_dir, log)
            elif after and not before:
                st["note"] = "first champion of this registry: recorded, not deployed"
            elif after and after != before:
                st["note"] = "new champion recorded; ML_DEPLOY_RETRAINED=1 would put it live"
        except Exception as e:
            st["error"] = repr(e)[:500]
            st["trace"] = traceback.format_exc()[-1500:]
            log(f"{t}: failed: {e!r}")
        st["finished"] = now()
    return status | {"finished": now()}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ml.auto", description=__doc__.split("\n\n")[0])
    ap.add_argument("--targets", default="godark,fishing,route")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--proposals", type=int, default=3)
    ap.add_argument("--no-retrain", action="store_true", help="only recalibrate from the ledger")
    ap.add_argument("--no-deploy", action="store_true", help="never touch champions.json")
    ap.add_argument("--models-dir", type=Path, default=Path(os.getenv("PREDICT_MODEL_DIR", "/opt/dvm/models")))
    a = ap.parse_args(argv)
    lock_path = Path(os.getenv("ML_LOCK", str(DEFAULT_ARTIFACTS.parent / "auto.lock")))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"ml.auto: another cycle holds {lock_path}; exiting")
            return
        status = cycle([t for t in a.targets.split(",") if t], a.rounds, a.proposals, not a.no_retrain,
                       not a.no_deploy, a.models_dir, log=lambda m: print(f"[{now()}] {m}", flush=True))
    reports = DEFAULT_ARTIFACTS / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "auto-status.json").write_text(json.dumps(status, indent=1, default=str))
    with open(reports / "auto-history.jsonl", "a") as f:
        f.write(json.dumps({k: v for k, v in status.items() if k != "targets"} |
                           {"targets": {t: {k: v for k, v in s.items() if k != "trace"}
                                        for t, s in status["targets"].items()}}, default=str) + "\n")
    print(json.dumps(status, indent=1, default=str))


if __name__ == "__main__":
    main()
