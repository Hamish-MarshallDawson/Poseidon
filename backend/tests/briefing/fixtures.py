from dvm.live import Live
from dvm.models import PositionReport, VesselStatic

NOW = 1_800_000_000_000


def pos(mmsi, lat, lon, sog=12.0, cog=90.0, ts=NOW - 60_000):
    return PositionReport(mmsi=mmsi, ts=ts, recv_ts=ts, lat=lat, lon=lon, sog_kn=sog, cog_deg=cog, cls="A",
                          ts_quality="source", src="aisstream")


def static(mmsi, **kw):
    return VesselStatic(mmsi=mmsi, ts=NOW, recv_ts=NOW, mid=int(str(mmsi)[:3]), src="aisstream", **kw)


def make_live() -> Live:
    live = Live()
    live.apply(pos(244000001, 55.00, 12.00))
    live.apply(static(244000001, name="NORDIC STAR", type_group="tanker", destination="ROTTERDAM", flag_iso2="NL"))
    live.apply(pos(244000002, 55.05, 12.10, sog=11.5, cog=95.0))
    live.apply(static(244000002, name="NORDIC MOON", type_group="tanker", destination="ROTTERDAM", flag_iso2="NL"))
    live.apply(pos(636000003, 58.0, 20.0, sog=0.2, cog=270.0))   # far away, no statics
    return live
