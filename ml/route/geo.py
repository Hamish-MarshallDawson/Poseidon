"""Spherical-earth helpers, vectorised with numpy. Degrees in, degrees out; distances in metres."""
from __future__ import annotations

import numpy as np

R_EARTH_M = 6_371_008.8
KN_TO_MS = 1852.0 / 3600.0


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R_EARTH_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def bearing_deg(lat1, lon1, lat2, lon2):
    """Initial great-circle bearing from point 1 to point 2, 0 to 360 (0 = north)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    y = np.sin(dlmb) * np.cos(p2)
    x = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dlmb)
    return np.degrees(np.arctan2(y, x)) % 360.0


def destination(lat, lon, bearing, dist_m):
    """Point reached from (lat, lon) after dist_m along the great circle with initial bearing (degrees)."""
    p1, l1 = np.radians(lat), np.radians(lon)
    th = np.radians(bearing)
    d = np.asarray(dist_m, dtype=float) / R_EARTH_M
    p2 = np.arcsin(np.clip(np.sin(p1) * np.cos(d) + np.cos(p1) * np.sin(d) * np.cos(th), -1.0, 1.0))
    l2 = l1 + np.arctan2(np.sin(th) * np.sin(d) * np.cos(p1), np.cos(d) - np.sin(p1) * np.sin(p2))
    return np.degrees(p2), (np.degrees(l2) + 540.0) % 360.0 - 180.0


def enu_offset_m(lat0, lon0, lat, lon):
    """East and north offset (m) of (lat, lon) from (lat0, lon0) on the local tangent plane (exact on the sphere
    for direction and distance: azimuthal equidistant around lat0, lon0)."""
    d = haversine_m(lat0, lon0, lat, lon)
    b = np.radians(bearing_deg(lat0, lon0, lat, lon))
    return d * np.sin(b), d * np.cos(b)


def apply_enu_offset(lat0, lon0, east_m, north_m):
    """Inverse of enu_offset_m."""
    east_m, north_m = np.asarray(east_m, float), np.asarray(north_m, float)
    dist = np.hypot(east_m, north_m)
    brg = np.degrees(np.arctan2(east_m, north_m)) % 360.0
    return destination(lat0, lon0, brg, dist)


def angle_diff_deg(a, b):
    """Signed smallest difference a - b in degrees, -180 to 180."""
    return (np.asarray(a) - np.asarray(b) + 540.0) % 360.0 - 180.0
