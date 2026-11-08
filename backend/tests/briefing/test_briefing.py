import asyncio
import json

import pytest
from fastapi import FastAPI, HTTPException

from dvm.briefing import gather, gemini, voice
from dvm.briefing.routes import BriefingRequest, SpeechRequest, make_router
from tests.briefing.fixtures import NOW, make_live

GOOD = {"headline": "h", "overview": "o", "speech_script": "s",
        "per_vessel": [{"mmsi": 244000001, "risk": "low", "findings": ["f"]}],
        "correlation": {"found": False, "strength": "none", "explanation": "none found"}}


def reply(obj_or_text):
    text = obj_or_text if isinstance(obj_or_text, str) else json.dumps(obj_or_text)
    return {"steps": [{"type": "thought"}, {"type": "model_output", "content": [{"type": "text", "text": text}]}]}


def run(c):
    return asyncio.run(c)


def test_single_ship_has_no_pairs():
    f = gather.gather(make_live(), [244000001], NOW)
    assert len(f["ships"]) == 1 and f["pairs"] == []


def test_duplicates_collapse_and_pairs_count():
    f = gather.gather(make_live(), [244000001, 244000001, 244000002, 636000003], NOW)
    assert len(f["ships"]) == 3 and len(f["pairs"]) == 3


def test_pair_facts_are_computed():
    f = gather.gather(make_live(), [244000001, 244000002, 636000003], NOW)
    near = next(p for p in f["pairs"] if p["mmsi_b"] == 244000002)
    far = next(p for p in f["pairs"] if p["mmsi_b"] == 636000003)
    assert near["near"] and 5 < near["distance_km"] < 12 and near["course_diff_deg"] == 5.0
    assert near["shared"]["destination"]["same"] and near["shared"]["flag_iso2"]["same"]
    assert not far["near"] and far["distance_km"] > 500 and "destination" not in far["shared"]


def test_missing_data_is_listed_not_filled():
    f = gather.gather(make_live(), [636000003], NOW)
    assert set(f["ships"][0]["data_not_available"]) == {"gaps", "risk_score", "statics"}


def test_gap_overlap_uses_open_gaps():
    live = make_live()
    d = live.detail
    live.detail = lambda m: {**d(m), "gaps": [{"start_ts": NOW - 3_600_000, "end_ts": None}]}
    f = gather.gather(live, [244000001, 244000002], NOW)
    assert f["pairs"][0]["gap_overlap_s"] == 3600


def test_unknown_ship_raises():
    with pytest.raises(KeyError):
        gather.gather(make_live(), [1], NOW)


def test_gemini_ok_and_sends_facts(monkeypatch):
    seen = {}
    monkeypatch.setattr(gemini, "_post", lambda p, k: seen.update(p=p, k=k) or reply(GOOD))
    s = run(gemini.summarise({"x": 1}, key="K"))
    assert s.correlation.strength == "none" and seen["k"] == "K" and json.loads(seen["p"]["input"]) == {"x": 1}


def test_gemini_retries_once_on_bad_json(monkeypatch):
    answers = iter([reply("not json"), reply(GOOD)])
    monkeypatch.setattr(gemini, "_post", lambda p, k: next(answers))
    assert run(gemini.summarise({}, key="K")).headline == "h"


def test_gemini_gives_up_after_two_bad_answers(monkeypatch):
    monkeypatch.setattr(gemini, "_post", lambda p, k: reply("nope"))
    with pytest.raises(gemini.BriefingError) as e:
        run(gemini.summarise({}, key="K"))
    assert e.value.status == 502


def test_gemini_without_key_is_503(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(gemini.BriefingError) as e:
        run(gemini.summarise({}))
    assert e.value.status == 503


def make_app(monkeypatch):
    from types import SimpleNamespace
    hub = SimpleNamespace(live=make_live())
    return make_router(hub, lambda: None)


def endpoint(router, path):
    return next(r.endpoint for r in router.routes if r.path == path)


def test_route_returns_summary_and_voice_flag(monkeypatch):
    monkeypatch.setattr(gemini, "_post", lambda p, k: reply(GOOD))
    monkeypatch.setenv("GEMINI_API_KEY", "K")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    out = run(endpoint(make_app(monkeypatch), "/briefing")(BriefingRequest(mmsis=[244000001])))
    assert out["summary"]["headline"] == "h" and out["voice_available"] is False and out["mmsis"] == [244000001]


def test_route_unknown_ship_404(monkeypatch):
    with pytest.raises(HTTPException) as e:
        run(endpoint(make_app(monkeypatch), "/briefing")(BriefingRequest(mmsis=[5])))
    assert e.value.status_code == 404


def test_request_limits():
    for bad in ([], list(range(gather.MAX_SHIPS + 1))):
        with pytest.raises(ValueError):
            BriefingRequest(mmsis=bad)


def test_speech_503_without_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(HTTPException) as e:
        run(endpoint(make_app(monkeypatch), "/briefing/speech")(SpeechRequest(text="hello")))
    assert e.value.status_code == 503


def test_speech_returns_audio(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "E")
    monkeypatch.setattr(voice, "_post", lambda t, k, v: b"mp3bytes")
    r = run(endpoint(make_app(monkeypatch), "/briefing/speech")(SpeechRequest(text="hello")))
    assert r.body == b"mp3bytes" and r.media_type == "audio/mpeg"


def test_route_requires_login():
    from types import SimpleNamespace

    def deny():
        raise HTTPException(401)
    router = make_router(SimpleNamespace(live=make_live()), deny)
    assert all(d.dependency is deny for d in router.dependencies)


def test_origin_reaches_the_facts_and_the_prompt():
    origins = {244000001: {"kind": "system", "reasons": ["gap_in_coverage"], "risk_p": 0.4},
               244000002: {"kind": "user", "added_by": "Aiden"}}
    f = gather.gather(make_live(), [244000001, 244000002, 636000003], NOW, origins)
    assert [s["origin"] for s in f["ships"]] == [origins[244000001], origins[244000002], None]
    assert "flagged by the model" in gemini.SYSTEM and "added by <name>" in gemini.SYSTEM


def test_request_accepts_origins_by_mmsi_and_rejects_bad_ones():
    r = BriefingRequest.model_validate({"mmsis": [1], "origins": {"1": {"kind": "user", "added_by": "you"}}})
    assert r.origins[1].added_by == "you"
    assert BriefingRequest.model_validate({"mmsis": [1]}).origins == {}
    with pytest.raises(ValueError):
        BriefingRequest.model_validate({"mmsis": [1], "origins": {"1": {"kind": "bot"}}})
