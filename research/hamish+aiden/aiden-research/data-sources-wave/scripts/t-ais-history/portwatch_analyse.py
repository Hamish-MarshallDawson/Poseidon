#!/usr/bin/env python3
"""Describe PortWatch series: lag, 2026 trend, anomalies (incl. Hormuz)."""
import csv
import os
import statistics as st
from collections import defaultdict

D = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", "data", "t-ais-history", "portwatch")


def load(fn):
    with open(os.path.join(D, fn)) as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


files = sorted(os.listdir(D))
print("=== summary per chokepoint (n_total) ===")
print(f"{'chokepoint':26s} {'last':10s} {'2026 mean':>9s} {'2026 max':>8s} {'Oct26 mean':>10s} "
      f"{'Oct26 tanker mean':>17s} {'last7d mean':>11s} {'last7d tankers':>14s}")
for fn in files:
    rs = load(fn)
    name = rs[0]["portname"]
    r26 = [r for r in rs if r["date"].startswith("2026")]
    oct26 = [r for r in r26 if r["date"].startswith("2026-10")]
    tail = rs[-7:]
    tot26 = [num(r["n_total"]) for r in r26 if num(r["n_total"]) is not None]
    tnk26 = [num(r["n_tanker"]) for r in r26 if num(r["n_tanker"]) is not None]
    oct_t = [num(r["n_tanker"]) for r in oct26 if num(r["n_tanker"]) is not None]
    tail_t = [num(r["n_tanker"]) for r in tail if num(r["n_tanker"]) is not None]
    tail_a = [num(r["n_total"]) for r in tail if num(r["n_total"]) is not None]
    print(f"{name:26s} {rs[-1]['date']:10s} {st.mean(tot26):9.1f} {max(tot26):8d} "
          f"{st.mean([num(r['n_total']) for r in oct26 if num(r['n_total']) is not None]):10.1f} "
          f"{st.mean(oct_t):17.1f} {st.mean(tail_a):11.1f} {st.mean(tail_t):14.1f}")

print("\n=== Strait of Hormuz: monthly means of n_total / n_tanker ===")
hr = load("Strait_of_Hormuz.csv")
bym = defaultdict(list)
for r in hr:
    bym[r["date"][:7]].append(r)
for m in sorted(bym):
    v = bym[m]
    tt = [num(r["n_total"]) for r in v if num(r["n_total"]) is not None]
    tk = [num(r["n_tanker"]) for r in v if num(r["n_tanker"]) is not None]
    zeros = sum(1 for t in tt if t == 0)
    print(f"{m} n={len(v):3d} total mean {st.mean(tt):7.1f} median {st.median(tt):6.1f} "
          f"min {min(tt):4d} max {max(tt):4d} zero-days {zeros:3d} tanker mean {st.mean(tk):6.1f}")

print("\n=== Hormuz last 40 days ===")
for r in hr[-40:]:
    print(r["date"], "total", r["n_total"], "tanker", r["n_tanker"], "cargo", r["n_cargo"])

print("\n=== other chokepoints: last 10 days of 2026 ===")
for fn in ["Malacca_Strait.csv", "Oresund_Strait.csv", "Bab_el-Mandeb_Strait.csv",
           "Suez_Canal.csv", "Kerch_Strait.csv"]:
    rs = load(fn)
    print(fn, [(r["date"], r["n_total"], r["n_tanker"]) for r in rs[-10:]])
