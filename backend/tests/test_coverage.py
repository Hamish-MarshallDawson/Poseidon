"""Coverage read path and the /coverage login gate: no network, no database."""
import asyncio

import jwt
import pytest
from fastapi import HTTPException

from dvm import app, auth, coverage


@pytest.mark.parametrize("lat, lon, expected", [
    (60.04, 28.4, "600_284"),
    (-52.3, -0.05, "-523_-1"),     # floor, not truncation: -0.05 is in cell -1
    (0.0, 0.0, "0_0"),
])
def test_cell_id_format(lat, lon, expected):
    assert coverage.cell_id(coverage.cell_bin(lat), coverage.cell_bin(lon)) == expected


def test_parse_bbox():
    assert coverage.parse_bbox(None) is None
    assert coverage.parse_bbox("") is None
    assert coverage.parse_bbox("[[31,61],[19,54]]") == (19.0, 54.0, 31.0, 61.0)   # corners in any order


@pytest.mark.parametrize("bad", ["[[1,2]]", "not json", "[[200,0],[0,0]]", "[[0,95],[0,0]]", '[["x",0],[0,0]]'])
def test_parse_bbox_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        coverage.parse_bbox(bad)


def test_minutes_default_and_cap():
    assert coverage.coverage_sql(10, None)[1] == [10]
    assert coverage.coverage_sql(0, None)[1] == [1]
    assert coverage.coverage_sql(10**6, None)[1] == [coverage.MAX_MINUTES]


def test_bbox_becomes_cell_bins():
    sql, args = coverage.coverage_sql(5, (19.0, 54.0, 31.0, 61.0))
    assert args == [5, 190, 310, 540, 610]   # lon_bin 190..310, lat_bin 540..610
    assert "lon_bin BETWEEN $2 AND $3" in sql and "lat_bin BETWEEN $4 AND $5" in sql
    assert coverage.coverage_sql(5, None)[1] == [5]


class FakeAuth:
    def __init__(self, ok_token="good"):
        self.ok = ok_token

    async def verify(self, token):
        if token != self.ok:
            raise jwt.InvalidTokenError("bad")
        return {"sub": "auth0|1"}


@pytest.fixture
def gate(monkeypatch):
    monkeypatch.setattr(auth, "ENABLED", True)
    fake = FakeAuth()
    monkeypatch.setattr(auth, "verify_async", fake.verify)
    return fake


def refused(header):
    with pytest.raises(HTTPException) as e:
        asyncio.run(app.require_login(header))
    return e.value.status_code


def test_missing_or_malformed_header_is_401(gate):
    assert refused(None) == 401
    assert refused("") == 401
    assert refused("Bearer ") == 401
    assert refused("Basic good") == 401
    assert refused("good") == 401


def test_bad_token_is_401(gate):
    assert refused("Bearer wrong") == 401


def test_good_token_passes(gate):
    assert asyncio.run(app.require_login("Bearer good")) is None


def test_open_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(auth, "ENABLED", False)
    assert asyncio.run(app.require_login(None)) is None
