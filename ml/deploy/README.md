# The improvement loop on the server (`python -m ml.auto`)

Every 3 hours (`dvm-ml.timer`), one cycle under an exclusive lock (a cycle that finds it held exits):
1. **Recalibrate from the graded ledger** (`ml.core.recalibrate`): route radius factors per horizon and
   go-dark logit shifts, fitted on the older half of the graded outcomes of the live champions and kept only if the
   newer half gets closer to nominal. A head that was measured and refused keeps its radii (factor 1.0); only a head
   with too few graded rows takes the kept heads' median factor. A kept fit becomes `<version>-calN` in
   `/opt/dvm/models` and is recorded (status file, Lab history), but **not installed** unless `ML_DEPLOY_RECAL=1`
   (off by default: Hamish decides installs). With it, champions.json is rewritten atomically; the predictor reloads
   it every cycle, no restart. To install a recorded one by hand, point champions.json at the `-calN` folder.
   Old folders stay for rollback.
2. **Retrain** each target (godark, fishing, route): refresh its data from Tiger read-only (and GFW for fishing,
   5 minutes, polite), then one `ml.core.loop` round: 3 Gemini proposals, only with `ML_GEMINI_API_KEY` (a separate key, so the
   briefings' `GEMINI_API_KEY` quota is never used; one call per model and cycle, capped per day), else the fixed
   list, trained, scored on the frozen held-out set, promoted only by the rule with a
   second-seed check.
3. **Deploy retrained champions** only with `ML_DEPLOY_RETRAINED=1` (off: the server registry starts empty, so its
   champions have only beaten its own earlier runs, not the live models). Fishing is never deployed (no live
   features yet).

Resources: Nice 19, idle I/O, at most 3 of the 6 vCPUs (`CPUQuota=300%`, `ML_THREADS=3`), 6 GB memory cap, one
cycle at a time. Status: `/opt/dvm/ml-data/models/reports/auto-status.json` and `auto-history.jsonl`; leaderboards
in the same folder.

## Install (once, as root, from /opt/dvm with the repo's ml/ present)

```bash
python3 -m venv /opt/dvm/ml/.venv && /opt/dvm/ml/.venv/bin/pip install -q -r /opt/dvm/ml/requirements.txt
mkdir -p /opt/dvm/ml-data && chown dvm: /opt/dvm/ml-data && chown -R dvm: /opt/dvm/models
cp /opt/dvm/ml/deploy/dvm-ml.service /opt/dvm/ml/deploy/dvm-ml.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now dvm-ml.timer
systemctl start dvm-ml.service          # first cycle now; journalctl -u dvm-ml -f to watch
```
The unit needs `/opt/dvm/backend/.env` (TIGER_DATABASE_URL, GFW_API_TOKEN; ML_GEMINI_API_KEY only if a separate Gemini key exists) and the backend
package next to ml/ (the deploy step loads artifacts with the live loader).
