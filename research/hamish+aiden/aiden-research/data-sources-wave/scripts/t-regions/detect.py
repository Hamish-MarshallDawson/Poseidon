#!/usr/bin/env python3
"""Read real Sentinel-1 GRD windows over the candidate regions, count bright point
targets with a simple documented detector, save crops.

Detector (deliberately plain):
  1. VV window at full 10 m sampling, DN -> dB
  2. background = 101x101 px (~1 km) mean of dB
  3. candidate pixel: dB - background > CONTRAST and dB > ABS_FLOOR
  4. 8-connected components, keep 5 <= area <= 4000 px
  5. drop targets on land (global-land-mask) and save the rest

Georeferencing comes from georef.py (SAFE annotation grid), because the open
bucket's measurement tiff has no CRS.
"""
import json, sys, math, os
import numpy as np
import rasterio
from rasterio.windows import Window
from scipy import ndimage
from PIL import Image
from global_land_mask import globe
import georef

CONTRAST = 7.0     # dB above local 1 km mean
ABS_FLOOR = -14.0  # dB absolute minimum for a target on open water
MIN_AREA = 5       # px (30 m boat ~ 6 px at 10 m)
MAX_AREA = 4000    # px

def db_of(a):
    return 10.0 * np.log10(np.maximum(a.astype(np.float32), 1.0))

def box_to_window(aff, box):
    W, S, E, N = box
    pixs, lines = [], []
    for lon, lat in [(W, S), (E, S), (W, N), (E, N), ((W + E) / 2, (S + N) / 2)]:
        p, l = georef.lonlat_to_pixelline(aff, lon, lat)
        pixs.append(float(p)); lines.append(float(l))
    c0, c1 = int(min(pixs)), int(max(pixs))
    r0, r1 = int(min(lines)), int(max(lines))
    return Window(c0, r0, c1 - c0, r1 - r0), (min(pixs), min(lines), max(pixs), max(lines))

def detect(db, ox, oy, aff):
    bg = ndimage.uniform_filter(db, size=101)
    cand = (db - bg > CONTRAST) & (db > ABS_FLOOR)
    lab, n = ndimage.label(cand, structure=np.ones((3, 3)))
    if n == 0:
        return []
    idx = np.arange(1, n + 1)
    area = ndimage.sum(cand, lab, idx)
    peak = ndimage.maximum(db, lab, idx)
    cy, cx = np.array(ndimage.center_of_mass(cand, lab, idx)).T
    keep = (area >= MIN_AREA) & (area <= MAX_AREA)
    px_scale = abs(aff["cx"][0])
    rows = []
    for i in np.where(keep)[0]:
        r, c = cy[i] + oy, cx[i] + ox
        lon, lat = georef.pixelline_to_lonlat(aff, c, r)
        if globe.is_land(lat, lon) or globe.is_land(lat, lon - 0.02) or globe.is_land(lat, lon + 0.02):
            continue
        sub = (lab[max(0, int(cy[i]) - 40):int(cy[i]) + 41,
                   max(0, int(cx[i]) - 40):int(cx[i]) + 41] == i + 1)
        if sub.sum() and (sub[0].any() or sub[-1].any() or sub[:, 0].any() or sub[:, -1].any()):
            continue  # touches the 800 m inspection box edge: part of a larger object
        major = major_axis_px(sub)
        if major > 45:  # >450 m long: coastline fragment, no ship is that long
            continue
        rows.append({"row": float(cy[i]), "col": float(cx[i]), "area_px": float(area[i]),
                     "peak_db": float(peak[i]), "major_px": float(major),
                     "len_m": float(math.sqrt(area[i]) * px_scale),
                     "lon": float(lon), "lat": float(lat)})
    return rows

def major_axis_px(sub):
    ys, xs = np.nonzero(sub)
    if len(ys) < 3:
        return float(len(ys))
    c = np.cov(np.vstack([xs, ys]).astype(float))
    ev = np.linalg.eigvalsh(c)
    return float(4.0 * math.sqrt(max(ev[-1], 0)))  # ~ full length of a uniform bar

def run(item, box):
    url = item["vv"]
    aff = georef.affine_for(url)
    win, (minpix, minline, _, _) = box_to_window(aff, box)
    with rasterio.open(url) as ds:
        win = Window(int(win.col_off), int(win.row_off),
                     int(min(win.width, ds.width - win.col_off)),
                     int(min(win.height, ds.height - win.row_off)))
        a = ds.read(1, window=win)
    db = db_of(a)
    rows = detect(db, int(win.col_off), int(win.row_off), aff)
    return rows, a, db, aff

def save_crop(db, r, path, half=80):
    r0, c0 = int(r["row"]), int(r["col"])
    sub = db[max(0, r0 - half):r0 + half, max(0, c0 - half):c0 + half]
    lo, hi = np.percentile(sub, 2), np.percentile(sub, 99.8)
    img = np.clip((sub - lo) / max(hi - lo, 1e-6), 0, 1)
    Image.fromarray((img * 255).astype(np.uint8)).save(path)
