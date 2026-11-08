import json

import pytest

from ml.core import propose
from ml.core.toy import ToyTarget


@pytest.fixture
def spec():
    return ToyTarget()


def test_validate(spec):
    assert propose.validate(spec, spec.default_config) == []
    assert propose.validate(spec, {**spec.default_config, "l2": 1000})            # out of range
    assert propose.validate(spec, {**spec.default_config, "code": "import os"})   # unknown key
    assert propose.validate(spec, {**spec.default_config, "features": ["held_out_truth"]})
    assert propose.validate(spec, {"model": "linear"})                            # no seed
    assert propose.validate(spec, "linear")
    errs = propose.validate(spec, {**spec.default_config, "model": "nope"})
    assert len(errs) == 1


def test_dry_run_is_fixed_and_includes_an_invalid_one(spec):
    a = propose.dry_run_proposals(spec, 3, 1)
    assert a == propose.dry_run_proposals(spec, 3, 1)
    assert len(a) == 4
    assert [bool(propose.validate(spec, p["config"])) for p in a] == [False, False, False, True]
    assert propose.dry_run_proposals(spec, 3, 2)[0] != a[0]   # rounds step through the list


def test_dry_run_generic_fallback(spec):
    spec.dry_run_proposals = None
    ps = propose.dry_run_proposals(spec, 3, 1)
    assert all(not propose.validate(spec, p["config"]) for p in ps[:-1])


def test_strip_drops_unsupported_keywords(spec):
    s = propose._strip(spec.config_schema)
    assert "additionalProperties" not in s and "uniqueItems" not in s["properties"]["features"]


@pytest.fixture(autouse=True)
def counter(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_GEMINI_COUNTER", str(tmp_path / "calls.json"))
    monkeypatch.delenv("ML_GEMINI_DAILY_CAP", raising=False)
    return tmp_path / "calls.json"


def _ok(payload, key):
    text = json.dumps({"proposals": [{"config": {"model": "linear", "seed": 0}, "rationale": "r"}]})
    return {"steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}]}


def test_model_default_and_override(spec, monkeypatch):
    seen = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(propose, "_post", lambda p, k: seen.append(p["model"]) or _ok(p, k))
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    propose.propose(spec, {}, 1, 1, dry_run=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-other")
    propose.propose(spec, {}, 1, 1, dry_run=False)
    assert seen == ["gemini-3.5-flash-lite", "gemini-other"]


def test_daily_cap_falls_back_without_calling(spec, monkeypatch, counter):
    calls = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("ML_GEMINI_DAILY_CAP", "2")
    monkeypatch.setattr(propose, "_post", lambda p, k: calls.append(1) or _ok(p, k))
    whos = [propose.propose(spec, {}, 1, 1, dry_run=False)[:2] for _ in range(3)]
    assert len(calls) == 2
    assert [w for w, _ in whos] == ["gemini", "gemini", "default"]
    assert "fallback" in whos[2][1] and "daily Gemini cap" in whos[2][1]
    assert list(json.loads(counter.read_text()).values()) == [2]


def test_429_is_a_clean_fallback(spec, monkeypatch):
    import io
    import urllib.error

    def boom(req, timeout):
        raise urllib.error.HTTPError(propose.URL, 429, "Too Many Requests", {}, io.BytesIO(b"secret body"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(propose.urllib.request, "urlopen", boom)
    who, source, ps = propose.propose(spec, {}, 3, 1, dry_run=False)
    assert who == "default" and "429" in source and "secret" not in source
    assert ps == propose.dry_run_proposals(spec, 3, 1)


def test_other_http_errors_still_stop(spec, monkeypatch):
    import io
    import urllib.error

    def boom(req, timeout):
        raise urllib.error.HTTPError(propose.URL, 500, "err", {}, io.BytesIO(b""))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(propose.urllib.request, "urlopen", boom)
    with pytest.raises(propose.ProposerError) as ei:
        propose.propose(spec, {}, 3, 1, dry_run=False)
    assert not isinstance(ei.value, propose.ProposerSkipped)


def test_gemini_parsing_without_network(spec, monkeypatch):
    seen = {}

    def fake_post(payload, key):
        seen["payload"] = payload
        text = json.dumps({"proposals": [
            {"config": {"model": "gbm", "seed": 0, "n_estimators": 100}, "rationale": "x" * 500},
            {"config": {"model": "linear", "seed": 0, "l2": -5}, "rationale": "bad range"}]})
        return {"steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}]}

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(propose, "_post", fake_post)
    who, source, ps = propose.propose(spec, {"recent_runs": []}, 2, 1, dry_run=False)
    assert who == "gemini" and source == seen["payload"]["model"] and len(ps) == 2
    assert len(ps[0]["rationale"]) == propose.MAX_RATIONALE
    assert propose.validate(spec, ps[0]["config"]) == [] and propose.validate(spec, ps[1]["config"])
    facts = json.loads(seen["payload"]["input"])
    assert set(facts) == {"target", "how_many", "config_schema", "summary"}


def test_gemini_garbage_is_an_error(spec, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(propose, "_post", lambda p, k: {"steps": []})
    with pytest.raises(propose.ProposerError):
        propose.gemini_proposals(spec, {}, 2)
