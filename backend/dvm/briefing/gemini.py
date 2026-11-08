"""Gemini summary over the REST API (stdlib only). The key comes from GEMINI_API_KEY in the root .env."""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Literal

from pydantic import BaseModel, ValidationError

from dvm import config  # noqa: F401  (loads the root .env)

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
# The Interactions API: generateContent is closed to this key's older models, and gemini-3.8-flash hung in testing.
URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
TIMEOUT_S = 60


class BriefingError(Exception):
    def __init__(self, msg: str, status: int = 502):
        super().__init__(msg)
        self.status = status


class PerVessel(BaseModel):
    mmsi: int
    name: str | None = None
    risk: Literal["low", "medium", "high", "unknown"]
    findings: list[str]
    caveats: list[str] = []


class Correlation(BaseModel):
    found: bool
    strength: Literal["none", "weak", "moderate", "strong"]
    links: list[str] = []
    explanation: str


class Summary(BaseModel):
    headline: str
    overview: str
    per_vessel: list[PerVessel]
    correlation: Correlation
    speech_script: str


SYSTEM = """You write a short intelligence-style briefing for a maritime dark-vessel monitor.
Rules:
- Use ONLY the JSON facts supplied. Never invent positions, behaviour, ownership or intent.
- Where a field is listed in data_not_available, say it is not available; do not guess it.
- A ship going silent on AIS is not proof of wrongdoing: receiver coverage holes are common. Say so when gaps appear.
- Correlation: judge it only from the supplied "pairs" facts (distance, course and speed difference, shared destination/flag/type, gap overlap). If the facts do not support a link, set found=false, strength="none" and say plainly that no correlation was found; that is a valid result. With a single ship set found=false, strength="none" and explain that correlation needs two or more ships.
- risk is your qualitative reading of the supplied facts (use the supplied risk score if present), "unknown" if there is too little data.
- speech_script: 60 to 120 words of plain spoken English with no markdown, bullets or ship numbers read digit by digit; say ship names where known, otherwise 'the vessel with MMSI ending in' the last 4 digits."""

SCHEMA = {"type": "object", "required": ["headline", "overview", "per_vessel", "correlation", "speech_script"],
          "properties": {
              "headline": {"type": "string"}, "overview": {"type": "string"}, "speech_script": {"type": "string"},
              "per_vessel": {"type": "array", "items": {"type": "object", "required": ["mmsi", "risk", "findings"], "properties": {
                  "mmsi": {"type": "integer"}, "name": {"type": "string"},
                  "risk": {"type": "string", "enum": ["low", "medium", "high", "unknown"]},
                  "findings": {"type": "array", "items": {"type": "string"}},
                  "caveats": {"type": "array", "items": {"type": "string"}}}}},
              "correlation": {"type": "object", "required": ["found", "strength", "explanation"], "properties": {
                  "found": {"type": "boolean"},
                  "strength": {"type": "string", "enum": ["none", "weak", "moderate", "strong"]},
                  "links": {"type": "array", "items": {"type": "string"}},
                  "explanation": {"type": "string"}}}}}


def _post(payload: dict, key: str) -> dict:
    req = urllib.request.Request(URL, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise BriefingError(f"Gemini returned HTTP {e.code}") from None   # never echo the body: it can carry the key
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise BriefingError("Gemini is unreachable or timed out") from None


async def _ask(system: str, facts: dict, schema: dict, parse, key: str | None):
    """One structured Gemini call; `parse(text)` raises ValidationError/ValueError on a bad answer (one retry)."""
    key = key or os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise BriefingError("Gemini is not configured (GEMINI_API_KEY)", 503)
    payload = {"model": MODEL, "system_instruction": system, "input": json.dumps(facts, default=str),
               "response_format": {"type": "text", "mime_type": "application/json", "schema": schema}}
    for attempt in (1, 2):
        data = await asyncio.to_thread(_post, payload, key)
        try:
            out = [st for st in data["steps"] if st.get("type") == "model_output"][-1]
            return parse("".join(c["text"] for c in out["content"] if c.get("type") == "text"))
        except (KeyError, IndexError, TypeError, ValueError):   # pydantic's ValidationError is a ValueError
            if attempt == 2:
                raise BriefingError("Gemini returned an unusable answer") from None
    raise AssertionError


async def summarise(facts: dict, key: str | None = None) -> Summary:
    return await _ask(SYSTEM, facts, SCHEMA, Summary.model_validate_json, key)


SESSION_SYSTEM = """You write the end-of-session summary of a shared maritime investigation, for the team that ran it.
Rules:
- Use ONLY the JSON facts supplied: the session notes, the saved briefings, and the tracked ships with their statuses. Never invent positions, behaviour, ownership or intent.
- Neutral wording. A flag, a gap in AIS or a ranking is a prompt to review, never an accusation, and a silent ship is not proof of wrongdoing.
- Cover: what the team looked at, what they noted (name the author), which ships are open, reviewed or no action, and what remains to check.
- Plain text only, no markdown, at most 2500 characters. Say so plainly if there is little to summarise."""

SESSION_SCHEMA = {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}


def _session_text(text: str) -> str:
    out = json.loads(text)["summary"].strip()
    if not out:
        raise ValueError("empty summary")
    return out


async def summarise_session(facts: dict, key: str | None = None) -> str:
    return await _ask(SESSION_SYSTEM, facts, SESSION_SCHEMA, _session_text, key)
