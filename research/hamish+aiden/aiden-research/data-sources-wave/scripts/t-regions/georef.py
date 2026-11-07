#!/usr/bin/env python3
"""Georeference a sentinel-s1-l1c GRD measurement tiff from its SAFE annotation.

The measurement/iw-vv.tiff in the open bucket carries no CRS or transform. The
annotation/iw-vv.xml does carry 210 geolocationGridPoints (line, pixel -> lat, lon).
GRD products are map-projected on a north-up UTM grid, so an affine
(pixel,line) -> (UTM X, UTM Y) fit is accurate to a few pixels.
"""
import os, re, json, urllib.request
import numpy as np
from pyproj import Transformer

CACHE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/t-regions/anno"
BASE = "https://sentinel-s1-l1c.s3.amazonaws.com/"

def _anno_url(vv_url, pol="vv"):
    # .../GRD/YYYY/M/D/IW/DV/<ID>/measurement/iw-vv.tiff -> .../<ID>/annotation/iw-vv.xml
    d = vv_url.rsplit("/measurement/", 1)[0]
    return d + f"/annotation/iw-{pol}.xml"

def fetch_annotation(vv_url):
    os.makedirs(CACHE, exist_ok=True)
    pid = vv_url.split("/")[-3]
    p = os.path.join(CACHE, pid + ".xml")
    if not os.path.exists(p):
        urllib.request.urlretrieve(_anno_url(vv_url), p)
    return p

def parse_points(xml_path):
    s = open(xml_path, encoding="utf-8", errors="ignore").read()
    i = s.find("<geolocationGridPointList")
    j = s.find("</geolocationGridPointList>", i)
    blk = s[i:j]
    out = []
    for m in re.finditer(r"<geolocationGridPoint>(.*?)</geolocationGridPoint>", blk, re.S):
        g = m.group(1)
        def f(k):
            mm = re.search(rf"<{k}>([^<]+)</{k}>", g)
            return float(mm.group(1)) if mm else None
        out.append((f("line"), f("pixel"), f("latitude"), f("longitude")))
    return out

def affine_for(vv_url):
    pts = parse_points(fetch_annotation(vv_url))
    lat = np.array([p[2] for p in pts]); lon = np.array([p[3] for p in pts])
    line = np.array([p[0] for p in pts]); pix = np.array([p[1] for p in pts])
    zone = int((lon.mean() + 180) // 6) + 1
    epsg = 32600 + zone if lat.mean() >= 0 else 32700 + zone
    tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    X, Y = tr.transform(lon, lat)
    A = np.column_stack([pix, line, np.ones_like(pix)])
    cx, *_ = np.linalg.lstsq(A, X, rcond=None)
    cy, *_ = np.linalg.lstsq(A, Y, rcond=None)
    resx = np.abs(A @ cx - X); resy = np.abs(A @ cy - Y)
    return {"epsg": epsg, "cx": cx.tolist(), "cy": cy.tolist(),
            "res_m": [float(np.median(resx)), float(np.median(resy)),
                      float(np.percentile(np.hypot(resx, resy), 95))],
            "n_points": len(pts)}

def lonlat_to_pixelline(aff, lon, lat):
    tr = Transformer.from_crs("EPSG:4326", f"EPSG:{aff['epsg']}", always_xy=True)
    X, Y = tr.transform(lon, lat)
    cx = aff["cx"]; cy = aff["cy"]
    # invert [[cx0,cx1,cx2],[cy0,cy1,cy2]] mapping (pix,line,1) -> (X,Y)
    M = np.array([[cx[0], cx[1]], [cy[0], cy[1]]])
    Minv = np.linalg.inv(M)
    v = np.array([np.asarray(X) - cx[2], np.asarray(Y) - cy[2]])
    p = Minv @ v
    return p[0], p[1]  # pixel, line

def pixelline_to_lonlat(aff, pix, line):
    cx = aff["cx"]; cy = aff["cy"]
    X = cx[0] * pix + cx[1] * line + cx[2]
    Y = cy[0] * pix + cy[1] * line + cy[2]
    tr = Transformer.from_crs(f"EPSG:{aff['epsg']}", "EPSG:4326", always_xy=True)
    return tr.transform(X, Y)

if __name__ == "__main__":
    import sys, json, rasterio
    inv = json.load(open("/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/t-regions/inventory.json"))
    it = inv[sys.argv[1]]["items"][-1]
    aff = affine_for(it["vv"])
    print(it["id"], json.dumps(aff))
    with rasterio.open(it["vv"]) as ds:
        print("shape", ds.shape, "px", aff["cx"][0], aff["cy"][1])
    # round trip a known tie point
    pts = parse_points(fetch_annotation(it["vv"]))
    p = pts[100]
    lon, lat = pixelline_to_lonlat(aff, p[1], p[0])
    print("tie", p, "-> ", round(lon, 5), round(lat, 5))
