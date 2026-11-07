"""id-flags: identity-field conflict and validity rates from the AISStream capture.

Reads $WAVE/data/identity/aisstream-capture.jsonl, writes ais_flags.json.
Run: cd /tmp && python3 -I <this file>
"""
import json, os, re, collections, statistics, datetime

W = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
SRC = os.path.join(W, "data/identity/aisstream-capture.jsonl")
OUT = os.path.join(W, "data/id-flags/ais_flags.json")

# ITU MID list (maritime identification digits) valid as of the latest published
# Table of Maritime Identification Digits. Used only to test MMSI plausibility.
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

IMO_RE = re.compile(r"^\d{7}$")


def imo_ok(n: int) -> bool:
    s = str(n)
    if not IMO_RE.match(s):
        return False
    tot = sum(int(s[i]) * (7 - i) for i in range(6))
    return tot % 10 == int(s[6])


def norm_name(n: str) -> str:
    n = n.upper().replace("@", "")
    n = re.sub(r"[^A-Z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def mmsi_class(m: int):
    s = str(m).zfill(9)
    if len(s) != 9:
        return "bad_length"
    if s.startswith("0"):
        return "group_or_bad"      # 0MIDxxxxx group, 00MIDxxxx coast station
    if s.startswith("98") or s.startswith("99"):
        return "auxiliary"
    if s.startswith("970") or s.startswith("972") or s.startswith("974"):
        return "sar_ais"           # 970 AIS-SART, 972 MOB, 974 EPIRB
    if s.startswith("111"):
        return "sar_aircraft"
    mid = s[:3]
    return "ship_mid_valid" if mid in MIDS else "ship_mid_unknown"


def main():
    by_mmsi = collections.defaultdict(lambda: {
        "names": set(), "nnames": set(), "imos": set(), "calls": set(),
        "types": set(), "lengths": set(), "msgtypes": set(), "first": None, "last": None,
        "n": 0, "name_obs": []})
    msgcount = collections.Counter()
    meta_name_present = 0
    meta_name_total = 0
    bad_json = 0
    for line in open(SRC, encoding="utf-8"):
        try:
            d = json.loads(line)
        except Exception:
            bad_json += 1
            continue
        msg = d.get("msg") or {}
        mt = msg.get("MessageType")
        if mt == "SubscriptionConfirmation" or mt is None:
            continue
        meta = msg.get("MetaData") or {}
        m = meta.get("MMSI")
        if not m:
            body = msg.get("Message") or {}
            for v in body.values():
                if isinstance(v, dict) and v.get("UserID"):
                    m = v["UserID"]
                    break
        if not m:
            continue
        msgcount[mt] += 1
        rec = by_mmsi[int(m)]
        rec["n"] += 1
        rec["msgtypes"].add(mt)
        t = d.get("recv")
        if t is not None:
            rec["first"] = t if rec["first"] is None else min(rec["first"], t)
            rec["last"] = t if rec["last"] is None else max(rec["last"], t)
        sn = meta.get("ShipName")
        if sn is not None:
            meta_name_total += 1
            if sn.strip():
                meta_name_present += 1
            for n in {sn, (msg.get("Message") or {}).get("StaticDataReport", {}).get("ReportA", {}).get("Name"),
                      (msg.get("Message") or {}).get("ShipStaticData", {}).get("Name")}:
                if n and n.strip():
                    rec["names"].add(n.strip())
                    rec["nnames"].add(norm_name(n))
        body = msg.get("Message") or {}
        sd = body.get("ShipStaticData") or {}
        sdr = body.get("StaticDataReport") or {}
        if sd:
            imo = sd.get("ImoNumber") or 0
            if imo:
                rec["imos"].add(int(imo))
            if sd.get("CallSign", "").strip():
                rec["calls"].add(sd["CallSign"].strip())
            if sd.get("Type"):
                rec["types"].add(int(sd["Type"]))
            dim = sd.get("Dimension") or {}
            L = (dim.get("A") or 0) + (dim.get("B") or 0)
            if L:
                rec["lengths"].add(int(L))
            if sd.get("Name", "").strip():
                rec["names"].add(sd["Name"].strip())
                rec["nnames"].add(norm_name(sd["Name"]))
        if sdr:
            ra = sdr.get("ReportA") or {}
            rb = sdr.get("ReportB") or {}
            if ra.get("Name", "").strip():
                rec["names"].add(ra["Name"].strip())
                rec["nnames"].add(norm_name(ra["Name"]))
            if rb.get("CallSign", "").strip():
                rec["calls"].add(rb["CallSign"].strip())
            if rb.get("ShipType"):
                rec["types"].add(int(rb["ShipType"]))
            dim = rb.get("Dimension") or {}
            L = (dim.get("A") or 0) + (dim.get("B") or 0)
            if L:
                rec["lengths"].add(int(L))
        # class 19 carries name too
        for key in ("ExtendedClassBEquipmentPositionReport",):
            b = body.get(key) or {}
            if b.get("Name", "").strip():
                rec["names"].add(b["Name"].strip())
                rec["nnames"].add(norm_name(b["Name"]))

    n_ships = len(by_mmsi)
    multi_name = [m for m, r in by_mmsi.items() if len(r["nnames"]) > 1]
    multi_name_raw = [m for m, r in by_mmsi.items() if len(r["names"]) > 1]
    multi_imo = [m for m, r in by_mmsi.items() if len(r["imos"]) > 1]
    imo_to_mmsi = collections.defaultdict(set)
    for m, r in by_mmsi.items():
        for i in r["imos"]:
            imo_to_mmsi[i].add(m)
    shared_imo = {i: sorted(ms) for i, ms in imo_to_mmsi.items() if len(ms) > 1}
    multi_call = [m for m, r in by_mmsi.items() if len(r["calls"]) > 1]
    multi_type = [m for m, r in by_mmsi.items() if len(r["types"]) > 1]
    multi_len = [m for m, r in by_mmsi.items() if len(r["lengths"]) > 1]
    classes = collections.Counter(mmsi_class(m) for m in by_mmsi)
    imo_vals = [i for r in by_mmsi.values() for i in r["imos"]]
    imo_bad = [i for i in imo_vals if not imo_ok(i)]
    imo_zero_ships = sum(1 for r in by_mmsi.values() if not r["imos"])
    static_ships = sum(1 for r in by_mmsi.values() if r["msgtypes"] & {"ShipStaticData", "StaticDataReport", "ExtendedClassBEquipmentPositionReport"})

    # all IMOs seen in capture (ship static only), zero values stripped above
    out = {
        "capture": {
            "file": SRC, "size_bytes": os.path.getsize(SRC), "bad_json_lines": bad_json,
            "msg_types": dict(msgcount),
            "ships_with_any_message": n_ships,
            "ships_with_static_identity": static_ships,
            "meta_shipname_present_frac": [meta_name_present, meta_name_total],
        },
        "conflicts": {
            "mmsi_multi_normalised_name": len(multi_name),
            "mmsi_multi_raw_name": len(multi_name_raw),
            "mmsi_multi_imo": len(multi_imo),
            "mmsi_multi_callsign": len(multi_call),
            "mmsi_multi_shiptype": len(multi_type),
            "mmsi_multi_length": len(multi_len),
            "imo_on_multiple_mmsi": len(shared_imo),
            "imo_on_multiple_mmsi_examples": dict(list(shared_imo.items())[:10]),
            "examples_multi_name": {str(m): sorted(by_mmsi[m]["names"]) for m in multi_name_raw[:12]},
            "examples_multi_imo": {str(m): sorted(by_mmsi[m]["imos"]) for m in multi_imo[:12]},
        },
        "validity": {
            "mmsi_classes": dict(classes),
            "imo_values_seen": len(imo_vals),
            "imo_bad_checkdigit": len(imo_bad),
            "imo_bad_checkdigit_values": sorted(set(imo_bad))[:20],
            "ships_no_imo_in_static": imo_zero_ships,
        },
    }
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
