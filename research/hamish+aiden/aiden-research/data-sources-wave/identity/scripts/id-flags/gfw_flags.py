"""id-flags: base rates for identity-period changes from GFW identity records.

Reads $WAVE/data/identity/gfw-identities.jsonl; writes gfw_flags.json.
Run: cd /tmp && python3 -I <this file>
"""
import json, os, re, collections, datetime

W = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
SRC = os.path.join(W, "data/identity/gfw-identities.jsonl")
OUT = os.path.join(W, "data/id-flags/gfw_flags.json")


def imo_ok(n):
    s = str(n)
    if not re.match(r"^\d{7}$", s):
        return False
    return sum(int(s[i]) * (7 - i) for i in range(6)) % 10 == int(s[6])


def dt(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def norm(n):
    n = (n or "").upper().replace("@", "")
    n = re.sub(r"[^A-Z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def main():
    ships_by_imo = {}
    imo_bad = 0
    match_fields = collections.Counter()
    registry_sources = collections.Counter()
    for line in open(SRC, encoding="utf-8"):
        d = json.loads(line)
        if not imo_ok(d["imo"]):
            imo_bad += 1
        for e in d.get("entries", []):
            for s0 in e.get("selfReportedInfo", []):
                match_fields[s0.get("matchFields")] += 1
            for r0 in e.get("registryInfo", []):
                for sc in r0.get("sourceCode") or []:
                    registry_sources[sc] += 1
        recs = []
        for e in d.get("entries", []):
            for s in e.get("selfReportedInfo", []):
                f, t = dt(s.get("transmissionDateFrom")), dt(s.get("transmissionDateTo"))
                if not f or not t:
                    continue
                recs.append({"ssvid": s.get("ssvid"), "name": norm(s.get("shipname")),
                             "raw_name": s.get("shipname"), "flag": s.get("flag"),
                             "callsign": (s.get("callsign") or "").strip(),
                             "imo": s.get("imo"), "f": f, "t": t,
                             "matches": s.get("matchFields")})
        recs.sort(key=lambda r: r["f"])
        if d["imo"] not in ships_by_imo:
            ships_by_imo[d["imo"]] = {"imo": d["imo"], "groups": set(), "regions": set(),
                                      "periods": [], "entries": [], "lines": 0}
        s1 = ships_by_imo[d["imo"]]
        s1["groups"].add(d["group"])
        s1["regions"].add(d["region"])
        s1["periods"].extend(recs)
        s1["entries"].extend(d.get("entries", []))
        s1["lines"] += 1
    ships = []
    for imo, s1 in ships_by_imo.items():
        # keep one copy of identical periods (same ssvid, name, flag, from, to)
        seen = set()
        per = []
        for r in sorted(s1["periods"], key=lambda r: r["f"]):
            k = (r["ssvid"], r["raw_name"], r["flag"], r["f"], r["t"])
            if k in seen:
                continue
            seen.add(k)
            per.append(r)
        s1["periods"] = per
        s1["group"] = ",".join(sorted(s1["groups"]))
        s1["region"] = ",".join(sorted(s1["regions"]))
        ships.append(s1)

    # summaries
    def summarize(subset):
        n = len(subset)
        multi_ssvid = sum(1 for s in subset if len({p["ssvid"] for p in s["periods"]}) > 1)
        multi_name = sum(1 for s in subset if len({p["name"] for p in s["periods"]}) > 1)
        multi_flag = sum(1 for s in subset if len({p["flag"] for p in s["periods"]}) > 1)
        multi_call = sum(1 for s in subset if len({p["callsign"] for p in s["periods"] if p["callsign"]}) > 1)
        periods = sum(len(s["periods"]) for s in subset)
        spans = [(s["periods"][-1]["t"] - s["periods"][0]["f"]).days / 365.25
                 for s in subset if s["periods"]]
        ship_years = sum(sp for sp in spans if sp > 0.08)
        trans = []
        for s in subset:
            for a, b in zip(s["periods"], s["periods"][1:]):
                gap_d = (b["f"] - a["t"]).total_seconds() / 86400.0
                trans.append({"gap_d": gap_d, "ssvid": a["ssvid"] != b["ssvid"],
                              "name": a["name"] != b["name"], "flag": a["flag"] != b["flag"],
                              "call": a["callsign"] != b["callsign"],
                              "raw_name": a["raw_name"] != b["raw_name"],
                              "imo": a["imo"], "group": s["group"], "region": s["region"],
                              "old": [a["ssvid"], a["raw_name"], a["flag"]],
                              "new": [b["ssvid"], b["raw_name"], b["flag"]]})
        return {"ships": n, "periods": periods, "ship_years": round(ship_years, 1),
                "ships_multi_ssvid": multi_ssvid, "ships_multi_name": multi_name,
                "ships_multi_flag": multi_flag, "ships_multi_callsign": multi_call,
                "ships_multi_ssvid_incl_callsign": trans and 0,
                "transitions": len(trans),
                "_trans": trans}

    alltrans = []
    per = {}
    for key, subset in [("all", ships)] + [((g, r), [s for s in ships if (s["group"], s["region"]) == (g, r)])
                                           for g in sorted({s["group"] for s in ships})
                                           for r in sorted({s["region"] for s in ships})]:
        summ = summarize(subset)
        alltrans.extend(summ.pop("_trans"))
        if isinstance(key, tuple):
            key = "%s/%s" % key
        per[key] = summ

    def bucket(trans, pred):
        sel = [t for t in trans if pred(t)]
        return len(sel)

    def shares(trans):
        n = len(trans)
        if not n:
            return {}
        res = {}
        for label, pred in [
            ("ssvid_changed", lambda t: t["ssvid"]),
            ("name_changed", lambda t: t["name"]),
            ("flag_changed", lambda t: t["flag"]),
            ("callsign_changed", lambda t: t["call"]),
            ("ssvid_and_name", lambda t: t["ssvid"] and t["name"]),
            ("imu_ssvid_no_name", lambda t: t["ssvid"] and not t["name"]),
            ("name_only", lambda t: t["name"] and not t["ssvid"]),
            ("gap_le_1d", lambda t: t["gap_d"] <= 1),
            ("gap_lt_0_overlap", lambda t: t["gap_d"] < 0),
            ("gap_0_to_7d", lambda t: 0 <= t["gap_d"] <= 7),
            ("gap_gt_30d", lambda t: t["gap_d"] > 30),
            ("ssvid_change_gap_le_7d", lambda t: t["ssvid"] and 0 <= t["gap_d"] <= 7),
            ("ssvid_change_gap_gt_60d", lambda t: t["ssvid"] and t["gap_d"] > 60),
        ]:
            res[label] = [bucket(trans, pred), n]
        return res

    # changes per ship-year: transitions with a real gap <= 400d
    t_all = [t for t in alltrans]
    years = per["all"]["ship_years"]
    out = {
        "ships": len(ships),
        "match_fields": dict(match_fields),
        "registry_sources": dict(registry_sources),
        "imo_bad_checkdigit_records": imo_bad,
        "groups": per,
        "all_transitions": len(alltrans),
        "transition_shares": shares(t_all),
        "transitions_per_ship_year": round(len(alltrans) / years, 3) if years else None,
        "gap_hist_days": collections.Counter(
            ("<0" if t["gap_d"] < 0 else "0-1" if t["gap_d"] <= 1 else "1-7" if t["gap_d"] <= 7
             else "7-30" if t["gap_d"] <= 30 else "30-365" if t["gap_d"] <= 365 else ">365")
            for t in t_all).most_common(),
        "examples_ssvid_change_fast": sorted(
            [t for t in t_all if t["ssvid"] and abs(t["gap_d"]) <= 1],
            key=lambda t: abs(t["gap_d"]))[:15],
        "examples_ssvid_and_name": [t for t in t_all if t["ssvid"] and t["name"]][:15],
    }

    # per calendar year changes per 100 ship-years
    peryear = collections.defaultdict(lambda: {"ships": set(), "changes": 0, "ssvid_ch": 0, "name_ch": 0})
    for s in ships:
        for p in s["periods"]:
            for y in range(p["f"].year, p["t"].year + 1):
                peryear[y]["ships"].add(s["imo"])
        for a, b in zip(s["periods"], s["periods"][1:]):
            y = b["f"].year
            peryear[y]["changes"] += 1
            peryear[y]["ssvid_ch"] += a["ssvid"] != b["ssvid"]
            peryear[y]["name_ch"] += a["name"] != b["name"]
    out["per_year"] = {str(y): {"ships": len(v["ships"]), "period_starts": v["changes"],
                                "ssvid_changes": v["ssvid_ch"], "name_changes": v["name_ch"],
                                "changes_per_100_ship_years": round(100.0 * v["changes"] / len(v["ships"]), 1)}
                       for y, v in sorted(peryear.items()) if len(v["ships"]) >= 5}

    # registry vs self-reported disagreement (latest registry record per IMO)
    dis = collections.Counter()
    nreg = 0
    for s in ships:
        regs = [r for e in s["entries"] for r in e.get("registryInfo", [])]
        if not regs or not s["periods"]:
            continue
        nreg += 1
        last = s["periods"][-1]
        latest = [r for r in regs if r.get("latestVesselInfo")] or regs
        r = latest[-1]
        if norm(r.get("shipname")) != last["name"]:
            dis["name_differs"] += 1
        if (r.get("flag") or "") != (last["flag"] or ""):
            dis["flag_differs"] += 1
        if str(r.get("ssvid") or "") != str(last["ssvid"] or ""):
            dis["ssvid_differs"] += 1
        if (r.get("imo") or "") != s["imo"]:
            dis["imo_differs"] += 1
    out["registry_vs_selfreported"] = {"ships": nreg, "differences": dict(dis)}

    json.dump(out, open(OUT, "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in out.items() if k not in ("groups",)}, indent=1, default=str)[:5000])
    print("GROUPS", json.dumps({k: {kk: vv for kk, vv in v.items()} for k, v in per.items()}, indent=1)[:2500])


if __name__ == "__main__":
    main()
