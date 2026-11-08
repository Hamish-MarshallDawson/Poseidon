"""Zones (#157): lookups on the committed layers, incursion shares on a synthetic square, the /zones route shape."""
from __future__ import annotations

import json
import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dvm.predict import artifact, features as F, predictor as P
from dvm.zones import incursion as I, lookup as L
from dvm.zones.routes import make_router

DK, SE, DE, OM = 5674, 5694, 5669, 8354


@pytest.fixture(scope="module")
def z() -> L.Zones:
    return L.Zones(L.DATA_DIR)


# ---- lookups on the real layers ----

def test_danish_and_swedish_waters(z):
    assert z.zone_of(56.5, 11.5)["eez"] == DK          # Kattegat, Danish side
    assert z.zone_of(57.6, 11.3)["eez"] == SE          # off Gothenburg
    assert z.zone_of(55.7, 12.68)["eez"] == DK         # Oresund west of Saltholm
    assert z.zone_of(55.7, 12.95)["eez"] == SE         # Oresund off Malmo
    assert z.zone_of(54.55, 11.2)["eez"] == DE         # Fehmarn belt, German side
    assert z.zone_of(56.5, 11.5)["eez_name"].startswith("Danish")


def test_inside_a_known_mpa(z):
    t = z.zone_of(26.5, 56.4)                            # Musandam, Strait of Hormuz
    assert t["eez"] == OM
    assert "Marine Musandam Reserve" in t["mpa_names"]
    assert z.zone_of(56.5, 11.5)["mpa"] == []            # open Kattegat: no protected area


def test_outside_the_built_area(z):
    t = z.zone_of(40.0, 0.0)
    assert t == {"covered": False, "eez": None, "eez_name": None, "mpa": [], "mpa_names": []}


def test_border_distance(z):
    # the DK-SE border crosses 55.7 N at about 12.85 E (east of Saltholm); 0.1 deg of longitude there is ~6.3 km
    d = z.distance_to_eez_border_m(55.7, 12.75)
    assert 5_000 < d < 7_500
    assert z.distance_to_eez_border_m(56.5, 11.5) > z.distance_to_eez_border_m(57.6, 11.3)


def test_many_matches_single(z):
    pts = [(56.5, 11.5), (57.6, 11.3), (26.5, 56.4), (40.0, 0.0)]
    eez, mpa = z.zone_of_many([p[0] for p in pts], [p[1] for p in pts])
    assert eez == [DK, SE, OM, None]
    assert set(mpa[2]) == set(z.zone_of(26.5, 56.4)["mpa"])


# ---- incursion on a synthetic square ----

def _square(tmp_path, half_deg: float = 0.1):
    """Own EEZ 1 west of 10 E, foreign EEZ 2 east of it, one MPA square [9.9, 10.1] x [59.9, 60.1]."""
    def fc(feats):
        return {"type": "FeatureCollection", "features": feats}

    def poly(x0, y0, x1, y1):
        return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}
    eez = [{"type": "Feature", "geometry": poly(8, 58, 10, 62), "properties": {"mrgid": 1, "name": "West", "pol_type": "200NM"}},
           {"type": "Feature", "geometry": poly(10, 58, 12, 62), "properties": {"mrgid": 2, "name": "East", "pol_type": "200NM"}}]
    mpa = [{"type": "Feature", "geometry": poly(10 - half_deg, 60 - half_deg, 10 + half_deg, 60 + half_deg),
            "properties": {"site_id": 7, "name": "Square"}}]
    borders = [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[10, 58], [10, 62]]},
                "properties": {"a": 1, "b": 2}}]
    for name, d in (("eez", eez), ("mpa", mpa), ("eez_borders", borders)):
        (tmp_path / f"{name}.geojson").write_text(json.dumps(fc(d)))
    (tmp_path / "build.json").write_text(json.dumps({"regions": {"test": [8, 58, 12, 62]}}))
    return L.Zones(tmp_path)


def test_incursion_shares_on_a_square(tmp_path):
    zs = _square(tmp_path)
    # centred on the border: half the circle is foreign; a 5 km circle sits inside the 0.1 deg square
    r = I.incursion(60.0, 10.0, 5_000, own_eez=1, zones=zs)
    assert r["mpa_ids"] == [7] and r["mpa_share_80"] == 1.0
    assert r["foreign_eez"] == [2] and abs(r["foreign_share_80"] - 0.5) < 0.05
    # wholly in own waters, far from the MPA
    r = I.incursion(60.0, 9.0, 5_000, own_eez=1, zones=zs)
    assert r == {"mpa_ids": [], "mpa_share_80": 0.0, "foreign_eez": [], "foreign_share_80": 0.0}
    # a circle bigger than the square: share = square area / circle area
    rad = 20_000
    want = (0.2 * 111_320 * math.cos(math.radians(60))) * (0.2 * L.M_PER_DEG_LAT) / (math.pi * rad ** 2)
    r = I.incursion(60.0, 10.0, rad, own_eez=2, zones=zs)
    assert abs(r["mpa_share_80"] - want) < 0.04, (r, want)
    assert r["foreign_eez"] == [1] and abs(r["foreign_share_80"] - 0.5) < 0.05
    # own EEZ unknown: nothing is foreign; outside the built area: no answer
    assert I.incursion(60.0, 10.0, 5_000, own_eez=None, zones=zs)["foreign_share_80"] is None
    assert I.incursion(40.0, 0.0, 5_000, own_eez=1, zones=zs) == I.NONE
    assert zs.distance_to_eez_border_m(60.0, 9.9) == pytest.approx(0.1 * 111_320 * math.cos(math.radians(60)), rel=0.01)


def test_route_rows_carry_incursion(monkeypatch, tmp_path):
    zs = _square(tmp_path)
    monkeypatch.setattr(L, "_zones", zs)
    T, MIN = 1_780_000_000_000, 60_000
    rows = [{"mmsi": 1, "ts": T + i * MIN, "lat": 60.0, "lon": 9.8 + i * 0.002, "sog_kn": 10.0, "cog_deg": 90.0,
             "heading_deg": 90.0, "nav_status": 0, "cls": "A"} for i in range(30)]
    out = P.route_rows(artifact.RouteBaseline(), 1, F.Track.from_rows(rows), T + 29 * MIN, T + 30 * MIN, None, None,
                       "live")
    assert out and all(set(I.FIELDS) <= set(r) for r in out)
    inside = [r for r in out if zs.covered(r["lat"], r["lon"])]   # 24 h at 10 kn leaves the 4-degree test area
    assert inside and all(r["foreign_eez"] == [2] for r in inside)   # own EEZ (West) taken at the last fix
    assert all(r["mpa_ids"] is None for r in out if r not in inside)
    assert out[0]["horizon_s"] == 3600 and out[0]["mpa_ids"] == [7]   # 1 h east: the circle covers the square


# ---- route ----

def test_zones_route_shape(monkeypatch, tmp_path):
    zs = _square(tmp_path)
    monkeypatch.setattr(L, "_zones", zs)
    app = FastAPI()
    app.include_router(make_router(lambda: None))
    c = TestClient(app)
    d = c.get("/zones").json()
    assert d["type"] == "FeatureCollection"
    assert sorted(f["properties"]["layer"] for f in d["features"]) == ["eez", "eez", "mpa"]
    d = c.get("/zones", params={"bbox": "[[8.5,59],[9.5,61]]", "layers": "eez,borders"}).json()
    assert [f["properties"].get("mrgid") for f in d["features"]] == [1]
    d = c.get("/zones", params={"bbox": "[[9.5,59],[10.5,61]]", "layers": "borders"}).json()
    assert d["features"][0]["geometry"]["type"] == "MultiLineString"
    assert c.get("/zones", params={"layers": "land"}).status_code == 422
    assert c.get("/zones", params={"bbox": "x"}).status_code == 422


def test_mpa_ids_capped_on_big_circles(z):
    r = I.incursion(54.72, 12.8, 100_000, own_eez=DK, zones=z)   # a 6 h circle south of Copenhagen: 150+ sites
    assert len(r["mpa_ids"]) == I.MAX_IDS and 0 < r["mpa_share_80"] < 1
