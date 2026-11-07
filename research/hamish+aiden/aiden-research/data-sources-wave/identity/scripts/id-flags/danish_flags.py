"""id-flags: within-window and across-day identity conflict rates in Danish AIS.

Inputs (shared wave downloads):
  $WAVE/data/t-match/ais_0532_raw.csv        30 min, all classes, enriched identity fields
  $WAVE/data/t-ais-history/day_2026-11-01/classa_1630_1700Z.csv  30 min, class A
  $WAVE/data/t-ais-history/day_2026-11-01/vessels.csv           24 h per-MMSI summary (denominator)
Writes $WAVE/data/id-flags/danish_flags.json. Run: cd /tmp && python3 -I <file>
"""
import csv, json, os, re, collections

W = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
MORN = os.path.join(W, "data/t-match/ais_0532_raw.csv")
AFT = os.path.join(W, "data/t-ais-history/day_2026-11-01/classa_1630_1700Z.csv")
DAY = os.path.join(W, "data/t-ais-history/day_2026-11-01/vessels.csv")
OUT = os.path.join(W, "data/id-flags/danish_flags.json")

MIDS = set("""201 202 203 204 205 206 207 208 209 210 211 212 213 214 215 216 218 219
220 224 225 226 227 228 229 230 231 232 233 234 235 236 237 238 239 240 241 242
243 244 245 246 247 248 249 250 251 252 253 254 255 256 257 258 259 261 262 263
264 265 266 267 268 269 270 271 272 273 274 275 276 277 278 279 301 303 304 305
306 307 308 309 310 311 312 314 316 319 321 323 325 327 329 331 332 335 336 338
339 341 343 345 347 348 349 350 351 352 353 354 355 356 357 358 359 361 362 364
366 367 368 369 370 371 372 373 374 375 376 377 378 379 401 403 405 408 410 412
413 414 416 417 419 422 423 425 428 431 432 434 436 437 438 440 441 443 445 447
450 451 453 455 457 459 461 463 466 468 470 472 473 475 477 478 501 503 506 508
510 511 512 514 515 516 518 520 523 525 529 531 533 536 538 540 542 544 546 548
553 555 557 559 561 563 564 565 566 567 570 572 574 576 577 578 601 603 605 607
608 609 610 611 612 613 616 618 619 620 621 622 624 625 626 627 629 630 632 633
634 635 636 637 638 642 644 645 647 649 650 651 652 653 654 655 656 657 659 660
661 662 663 664 665 666 667 668 669 670 671 672 674 675 676 677 678 679 701 710
720 725 730 735 740 745 750 755 760 765 770 775 780 785 790""".split())


def imo_ok(n):
    s = str(n)
    if not re.match(r"^\d{7}$", s):
        return False
    return sum(int(s[i]) * (7 - i) for i in range(6)) % 10 == int(s[6])


def norm(n):
    n = (n or "").upper().replace("@", "")
    n = re.sub(r"[^A-Z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def mid_ok(m):
    s = str(m).zfill(9)
    return len(s) == 9 and s[:3] in MIDS and not s.startswith("0")


def scan(p, keymap, limit_rows=None):
    per = collections.defaultdict(lambda: {"names": set(), "nnames": set(), "imos": set(),
                                           "calls": set(), "types": set(), "dests": set(), "n": 0})
    rows = 0
    with open(p, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            rows += 1
            m = row.get(keymap["mmsi"]) or ""
            if not m.isdigit():
                continue
            r = per[int(m)]
            r["n"] += 1
            nm = row.get(keymap["name"]) or ""
            if nm.strip():
                r["names"].add(nm.strip())
                r["nnames"].add(norm(nm))
            im = (row.get(keymap["imo"]) or "").strip()
            if im.isdigit() and int(im) > 0:
                r["imos"].add(int(im))
            cs = (row.get(keymap["call"]) or "").strip()
            if cs:
                r["calls"].add(cs)
            ty = (row.get(keymap["type"]) or "").strip()
            if ty:
                r["types"].add(ty)
            de = (row.get(keymap["dest"]) or "").strip() if "dest" in keymap else ""
            if de:
                r["dests"].add(de)
    return per, rows


def summarize(per, label):
    n = len(per)
    imos = collections.defaultdict(set)
    for m, r in per.items():
        for i in r["imos"]:
            imos[i].add(m)
    bad_imo = [i for r in per.values() for i in r["imos"] if not imo_ok(i)]
    return {
        "window": label, "ships": n,
        "mmsi_multi_name_raw": sum(1 for r in per.values() if len(r["names"]) > 1),
        "mmsi_multi_name_norm": sum(1 for r in per.values() if len(r["nnames"]) > 1),
        "mmsi_multi_imo": sum(1 for r in per.values() if len(r["imos"]) > 1),
        "mmsi_imo_bad_checksum": len({m for m, r in per.items() if any(not imo_ok(i) for i in r["imos"])}),
        "imo_values_seen": sum(len(r["imos"]) for r in per.values()),
        "imo_bad_values": len(bad_imo),
        "mmsi_multi_callsign": sum(1 for r in per.values() if len(r["calls"]) > 1),
        "mmsi_multi_type": sum(1 for r in per.values() if len(r["types"]) > 1),
        "mmsi_multi_dest": sum(1 for r in per.values() if len(r["dests"]) > 1),
        "imo_on_multiple_mmsi": sum(1 for i, ms in imos.items() if len(ms) > 1),
        "imo_shared_examples": {str(i): sorted(ms) for i, ms in list(imos.items()) if len(ms) > 1} and
                               {str(i): sorted(ms) for i, ms in list((i, ms) for i, ms in imos.items() if len(ms) > 1)[:8]},
        "ships_bad_mmsi": sum(1 for m in per if not mid_ok(m)),
        "ships_no_imo": sum(1 for r in per.values() if not r["imos"]),
        "example_multi_names": {str(m): sorted(r["names"]) for m, r in per.items() if len(r["names"]) > 1},
    }


def main():
    mor, mrows = scan(MORN, {"mmsi": "MMSI", "name": "Name", "imo": "IMO", "call": "Callsign",
                             "type": "Ship type", "dest": "Destination"})
    aft, arows = scan(AFT, {"mmsi": "mmsi", "name": "name", "imo": "imo", "call": "callsign",
                            "type": "ship_type", "dest": "destination"})
    out = {"morning_window": summarize(mor, "2026-11-01 05:18-05:46Z Danish, all classes"),
           "afternoon_window": summarize(aft, "2026-11-01 16:30-17:00Z Danish, class A"),
           "rows": {"morning": mrows, "afternoon": arows}}

    # across the same day, ships present in both windows
    both = sorted(set(mor) & set(aft))
    chg = {"name": 0, "imo": 0, "callsign": 0, "type": 0}
    examples = []
    for m in both:
        a, b = mor[m], aft[m]
        if not (a["names"] and b["names"]):
            continue
        nm_change = norm(sorted(a["names"])[0]) != norm(sorted(b["names"])[0])
        im_change = a["imos"] != b["imos"] and a["imos"] and b["imos"]
        cs_change = a["calls"] != b["calls"] and a["calls"] and b["calls"]
        ty_change = a["types"] != b["types"] and a["types"] and b["types"]
        chg["name"] += nm_change
        chg["imo"] += bool(im_change)
        chg["callsign"] += bool(cs_change)
        chg["type"] += bool(ty_change)
        if nm_change or im_change:
            examples.append({"mmsi": m, "am": sorted(a["names"]), "pm": sorted(b["names"]),
                             "aimo": sorted(a["imos"]), "pimo": sorted(b["imos"])})
    out["same_day_overlap"] = {"ships_in_both_windows": len(both),
                               "ships_with_name_in_both": sum(1 for m in both if mor[m]["names"] and aft[m]["names"]),
                               "changed": chg, "examples": examples[:10]}

    # 24 h denominators
    day = []
    with open(DAY, newline="") as f:
        for row in csv.DictReader(f):
            day.append(row)
    out["day_2026-11-01"] = {
        "mmsi_rows": len(day),
        "mmsi_ship_like": sum(1 for r in day if r.get("cls") in ("A", "B")),
        "with_name": sum(1 for r in day if (r.get("name") or "").strip()),
        "with_imo": sum(1 for r in day if (r.get("imo") or "").strip() not in ("", "0")),
        "imo_bad_checksum": sum(1 for r in day if (r.get("imo") or "").strip().isdigit()
                                and int(r["imo"]) > 0 and not imo_ok(r["imo"])),
    }
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
