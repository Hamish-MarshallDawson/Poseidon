"""ElevenLabs text-to-speech (stdlib only). Optional: with no ELEVENLABS_API_KEY the briefing just has no voice."""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request

from dvm import config  # noqa: F401  (loads the root .env)
from dvm.briefing.gemini import BriefingError

DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"   # ElevenLabs premade "George"; override with ELEVENLABS_VOICE_ID
MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5")
MAX_CHARS = 1500


def available() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY"))


def _post(text: str, key: str, voice: str) -> bytes:
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_64",
        json.dumps({"text": text, "model_id": MODEL}).encode(),
        {"Content-Type": "application/json", "xi-api-key": key, "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise BriefingError(f"ElevenLabs returned HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise BriefingError("ElevenLabs is unreachable or timed out") from None


async def speak(text: str) -> bytes:
    key = os.getenv("ELEVENLABS_API_KEY", "")
    if not key:
        raise BriefingError("voice not configured", 503)
    text = text.strip()
    if not text or len(text) > MAX_CHARS:
        raise BriefingError(f"text must be 1 to {MAX_CHARS} characters", 422)
    return await asyncio.to_thread(_post, text, key, os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE))
