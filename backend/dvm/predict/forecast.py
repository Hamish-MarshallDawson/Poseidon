"""The newest forecasts in memory, for the live WebSocket frames (#121, addendum 05:15).

The predictor updates one Forecast after every cycle; the Hub reads it to fill, in the frontend's types
(frontend/src/types.ts):
- `VesselView.risk_p` / `risk_rank`: the ship's newest `dark_6h` score of the last hour, ranked by p among all
  scored ships (the go-dark sample rotates, so an hour covers every moving Class A ship heard).
- `GapEvent.pred_*` on open gaps: the newest route prediction for the gap, at the first horizon not yet passed
  (the ghost circle grows as the gap ages): `pred_lat, pred_lon, pred_r80_m, pred_r95_m, pred_horizon_s,
  pred_made_at, pred_model`, and the zone incursion of that circle (#157): `pred_mpa_ids, pred_mpa_share_80,
  pred_foreign_eez, pred_foreign_share_80` (null when zones are not loaded). Absent when the gap has no prediction.
- `detail.route_prediction`: the ship's newest prediction set, every horizon (each point with the incursion fields); `detail.score`: its newest dark_6h
  RiskScore.
- `snapshot.watchlist` / `delta.watchlist`: the top WATCH_N ships by p (06 section 2.8). Reason codes come from the
  evidence (06 section 5), never from the model: HIGH_FORECAST (p >= p_alert), OPEN_GAP, RECENT_GAP (a gap of ours in
  the last 24 h), DRAUGHT_JUMP (draught changed by 1 m or more across a recent gap), BLANK_DESTINATION. Decision:
  `inspect` if rank <= INSPECT_K and p >= p_alert; `watch` if p >= p_alert, or OPEN_GAP or RECENT_GAP (06: a gap can
  raise a ship to watch, never to inspect on its own); otherwise `none`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

H_MS = 3_600_000
RISK_TTL_MS = H_MS            # a ship's score counts for the ranking this long
ROUTE_TTL_MS = 6 * H_MS       # an active ship's prediction set stays in its detail this long
PRIMARY = "dark_6h"
WATCH_N = 50
INSPECT_K = 10
DRAUGHT_JUMP_M = 1.0
INCURSION = ("mpa_ids", "mpa_share_80", "foreign_eez", "foreign_share_80")   # dvm/zones/incursion.py (#157)


def _hhmm(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%d %b %H:%M UTC")


def risk_score(row: dict, rank: Optional[int]) -> dict:
    """A scores row as the frontend's RiskScore: numeric features only (nulls dropped), as_of = made_at."""
    feats = row.get("features") or {}
    return {"id": row["id"], "mmsi": row["mmsi"], "made_at": row["made_at"], "as_of": row["made_at"],
            "horizon_s": row["horizon_s"], "target": row["target"], "p": row["p"], "rank": rank,
            "mode": row["mode"], "features": {k: v for k, v in feats.items() if isinstance(v, (int, float))
                                             and not isinstance(v, bool)},
            "contrib": row.get("contrib") or {}, "model_version": row["model_version"]}


class Forecast:
    def __init__(self, p_alert: float = 0.2):
        self.p_alert = p_alert
        self.risk: dict[int, dict] = {}          # mmsi -> newest dark_6h scores row
        self.by_target: dict[int, dict[str, dict]] = {}   # mmsi -> target -> newest scores row (dark_1h/6h/24h)
        self.rank: dict[int, int] = {}
        self.gap_pred: dict[str, list[dict]] = {}   # open gap id -> its newest route rows, by horizon
        self.ship_route: dict[int, list[dict]] = {}  # mmsi -> its newest route rows, by horizon
        self.version = 0                          # bumped by every update

    # ---- updates (the predictor) ----

    def update(self, scores: Iterable[dict], routes: Iterable[dict], open_gaps: Optional[set[str]], now: int) -> None:
        for s in scores:
            mine = self.by_target.setdefault(s["mmsi"], {})
            cur = mine.get(s["target"])
            if cur is None or s["made_at"] >= cur["made_at"]:
                mine[s["target"]] = s
                if s["target"] == PRIMARY:
                    self.risk[s["mmsi"]] = s
        sets: dict[tuple, list[dict]] = {}
        for r in routes:
            sets.setdefault((r["mmsi"], r["as_of"], r["model_version"]), []).append(r)
        for (mmsi, as_of, _), rows in sorted(sets.items(), key=lambda kv: kv[0][1]):
            rows = sorted(rows, key=lambda r: r["horizon_s"])
            cur = self.ship_route.get(mmsi)
            if cur is None or as_of >= cur[0]["as_of"]:
                self.ship_route[mmsi] = rows
            gid = rows[0].get("gap_id")
            if gid:
                cur = self.gap_pred.get(gid)
                if cur is None or rows[0]["made_at"] >= cur[0]["made_at"]:
                    self.gap_pred[gid] = rows
        self.risk = {m: s for m, s in self.risk.items() if s["made_at"] > now - RISK_TTL_MS}
        self.by_target = {m: t for m, t in self.by_target.items() if m in self.risk}
        if open_gaps is not None:
            self.gap_pred = {g: rows for g, rows in self.gap_pred.items() if g in open_gaps}
        keep = {rows[0]["mmsi"] for rows in self.gap_pred.values()}
        self.ship_route = {m: rows for m, rows in self.ship_route.items()
                           if m in keep or rows[0]["made_at"] > now - ROUTE_TTL_MS}
        ranked = sorted(self.risk.values(), key=lambda s: (-s["p"], s["mmsi"]))
        self.rank = {s["mmsi"]: i for i, s in enumerate(ranked, 1)}
        self.version += 1

    def frozen_set(self, hour: int) -> list[dict]:
        """The forecast committed at `hour` (06 section 2.7; what /scores serves and the graders check): every ship's
        newest score made in the hour before it, re-issued with made_at = hour, so its label window starts at the
        hour. The score was computed from data up to `hour - scored_age_s` (a feature), never after the hour."""
        out = []
        for mmsi, rows in self.by_target.items():
            pick = {t: r for t, r in rows.items() if hour - RISK_TTL_MS < r["made_at"] <= hour}
            if PRIMARY not in pick:
                continue
            ids = {t: f"score-{mmsi}-{t}-{hour}" for t in pick}
            for t, r in pick.items():
                feats = r["features"]
                if "same_as" in feats:
                    feats = {"same_as": ids[PRIMARY]}
                else:
                    feats = {**feats, "scored_age_s": (hour - r["made_at"]) / 1000}
                out.append({**r, "id": ids[t], "made_at": hour, "features": feats})
        return out

    # ---- reads (the Hub, for frames) ----

    def risk_of(self, mmsi: int) -> tuple[Optional[float], Optional[int]]:
        s = self.risk.get(mmsi)
        return (s["p"], self.rank.get(mmsi)) if s else (None, None)

    def score_of(self, mmsi: int) -> Optional[dict]:
        s = self.risk.get(mmsi)
        return risk_score(s, self.rank.get(mmsi)) if s else None

    def gap_fields(self, gap_id: str, now: int) -> dict:
        rows = self.gap_pred.get(gap_id)
        if not rows:
            return {}
        age_s = (now - rows[0]["as_of"]) / 1000
        r = next((x for x in rows if x["horizon_s"] >= age_s), rows[-1])
        return {"pred_lat": r["lat"], "pred_lon": r["lon"], "pred_r80_m": r["radius_m_80"],
                "pred_r95_m": r["radius_m_95"], "pred_horizon_s": r["horizon_s"], "pred_made_at": r["made_at"],
                "pred_model": r["model_version"], **{f"pred_{k}": r.get(k) for k in INCURSION}}

    def route_block(self, mmsi: int) -> Optional[dict]:
        rows = self.ship_route.get(mmsi)
        if not rows:
            return None
        r0 = rows[0]
        return {"as_of": r0["as_of"], "made_at": r0["made_at"], "model_version": r0["model_version"],
                "gap_id": r0.get("gap_id"),
                "points": [{"horizon_s": r["horizon_s"], "lat": r["lat"], "lon": r["lon"],
                            "radius_m_80": r["radius_m_80"], "radius_m_95": r["radius_m_95"],
                            "base_lat": r["base_lat"], "base_lon": r["base_lon"],
                            **{k: r.get(k) for k in INCURSION}} for r in rows]}

    def watchlist(self, live, now: int, prev_rank: dict[int, int]) -> dict:
        """06 WatchlistEntry rows for the top WATCH_N. `live` is dvm.live.Live (names, statics, gaps)."""
        entries = []
        for s in sorted(self.risk.values(), key=lambda s: (-s["p"], s["mmsi"]))[:WATCH_N]:
            mmsi, p = s["mmsi"], s["p"]
            rank = self.rank[mmsi]
            static = live.static.get(mmsi, {})
            codes, evidence = [], [{"kind": "score", "id": s["id"],
                                    "label": f"dark 6 h p = {p:.2f} ({s['model_version']})"}]
            if p >= self.p_alert:
                codes.append("HIGH_FORECAST")
            gap_id = live.open_gap.get(mmsi)
            recent = [g for g in live.gaps_of(mmsi) if g["start_ts"] > now - 24 * H_MS]
            if gap_id:
                codes.append("OPEN_GAP")
                evidence.append({"kind": "gap", "id": gap_id, "label": f"silent since {_hhmm(live.gaps[gap_id]['start_ts'])}"})
            closed = [g for g in recent if g["state"] == "closed"]
            if closed:
                codes.append("RECENT_GAP")
                g = closed[0]
                evidence.append({"kind": "gap", "id": g["id"],
                                 "label": f"gap {_hhmm(g['start_ts'])} to {_hhmm(g['end_ts'] or g['start_ts'])}"})
            if any(g.get("draught_before_m") is not None and g.get("draught_after_m") is not None
                   and abs(g["draught_after_m"] - g["draught_before_m"]) >= DRAUGHT_JUMP_M for g in recent):
                codes.append("DRAUGHT_JUMP")
            if not (static.get("destination") or "").strip():
                codes.append("BLANK_DESTINATION")
            if rank <= INSPECT_K and p >= self.p_alert:
                decision = "inspect"
            elif p >= self.p_alert or "OPEN_GAP" in codes or "RECENT_GAP" in codes:
                decision = "watch"
            else:
                decision = "none"
            entries.append({"rank": rank, "mmsi": mmsi, "name": static.get("name"), "p": p, "decision": decision,
                            "prev_rank": prev_rank.get(mmsi), "reason_codes": codes, "evidence": evidence})
        return {"snapshot_ts": max((s["made_at"] for s in self.risk.values()), default=now), "entries": entries}
