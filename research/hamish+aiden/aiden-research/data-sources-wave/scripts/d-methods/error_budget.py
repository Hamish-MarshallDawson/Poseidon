"""d-methods: error budget for matching AIS to Sentinel-1 radar.

Three questions, all arithmetic, no downloads:
 1. How far does a moving ship appear displaced in a Sentinel-1 image (the
    "azimuth shift" / moving-target shift)?
 2. How stale may an AIS position be before it falls outside a match gate?
 3. How likely is a coincidence match, given a gate radius and vessel density?

Formulas are the standard SAR ones, cross-checked against the correction that
Global Fishing Watch apply in
https://github.com/GlobalFishingWatch/paper-longline-ais-sar-matching
(5_SAR_AIS_Matching/01_extrapolate_ais.sql.j2).
"""

import math

# --- Sentinel-1 IW geometry (documented, SentiWiki S1 products page) ----------
ALT_KM = 693.0          # orbital altitude
SAT_SPEED = 7570.0      # ground-track speed m/s (7.57 km/s at 693 km)
INC_DEG = 38.3          # IW2 mid-incidence; IW range 32.9-43.1 deg
PIXEL_M = 10.0          # IW GRD HR pixel spacing
RES_AZ_M = 22.5         # IW GRD HR azimuth resolution
LOC_ACC_M = 7.0         # IW GRD absolute location accuracy (NRT), per SentiWiki

KNOT = 0.514444


def slant_range(inc_deg, alt_km=ALT_KM):
    """Slant range from incidence angle and altitude (flat earth, fine here)."""
    return alt_km * 1000.0 / math.cos(math.radians(inc_deg))


def azimuth_shift(speed_kn, heading_deg, sat_heading_deg, inc_deg=INC_DEG):
    """Along-track displacement of a moving ship in a SAR image, metres.

    shift = (R_slant / V_sat) * v_radial, where v_radial is the component of
    the ship's velocity towards/away from the radar (i.e. across the satellite
    ground track for a side-looking radar).
    """
    v = speed_kn * KNOT
    # range-direction component of the ship velocity
    v_radial = v * abs(math.sin(math.radians(heading_deg - sat_heading_deg)))
    return slant_range(inc_deg) / SAT_SPEED * v_radial, v_radial


def staleness_for_gate(gate_m, speed_kn):
    """Seconds of AIS staleness that move a ship `gate_m` from its last fix."""
    return gate_m / (speed_kn * KNOT)


def collision_prob(gate_m, n_vessels, area_km2):
    """Expected number of AIS vessels within `gate_m` of one radar detection if
    positions were unrelated (uniform density assumption)."""
    return n_vessels * math.pi * (gate_m / 1000.0) ** 2 / area_km2


print("Sentinel-1 IW2: slant range %.0f km, R/V = %.1f s"
      % (slant_range(INC_DEG) / 1000, slant_range(INC_DEG) / SAT_SPEED))
print()
print("1) azimuth (along-track) displacement, satellite heading 0 deg (N)")
print("   speed_kn  heading  radial_m/s   shift_m")
for speed in (5, 10, 15, 20):
    for heading in (90, 45):  # beam-on (worst case), 45 deg off track
        shift, vr = azimuth_shift(speed, heading, 0)
        print("   %8.0f %8.0f %11.2f %9.0f" % (speed, heading, vr, shift))
print()
print("2) AIS staleness budget: seconds until the ship is further than the gate")
for gate in (200, 500, 1000):
    row = "   gate %4d m:" % gate
    for speed in (5, 10, 15, 20):
        row += "  %2.0f kn -> %5.0f s" % (speed, staleness_for_gate(gate, speed))
    print(row)
print()
print("3) coincidence matches, one 250x200 km scene (50 000 km2 of sea)")
for area in (50000, 5000):  # open basin vs a narrow strait
    for n in (50, 200, 500):
        row = "   %6d km2, %3d vessels under way:" % (area, n)
        for gate in (200, 500, 1000):
            row += "  gate %4d m: %.2e" % (gate, collision_prob(gate, n, area))
        print(row)
print()
print("   (comparison: image resolution 20x22 m, pixel 10 m, location accuracy 7 m)")
