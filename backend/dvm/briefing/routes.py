"""POST /briefing and POST /briefing/speech. Mount with: app.include_router(make_router(hub, require_login))."""
from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from dvm.briefing import gather, gemini, voice


class Origin(BaseModel):
    """Why a ship is in the briefing: `system` (the prediction model flagged it, with reason codes and risk p),
    `user` (a person added it; `added_by` is their name, or "you"), `selected` (just the open ship window)."""
    kind: Literal["system", "user", "selected"]
    reasons: list[str] = Field(default=[], max_length=10)
    risk_p: float | None = Field(None, ge=0, le=1)
    added_by: str | None = Field(None, max_length=80)


class BriefingRequest(BaseModel):
    mmsis: list[int] = Field(min_length=1, max_length=gather.MAX_SHIPS)
    origins: dict[int, Origin] = {}   # optional, keyed by mmsi


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=voice.MAX_CHARS)


def make_router(hub, require_login) -> APIRouter:
    """`hub` has .live (a dvm.live.Live); `require_login` is app.py's dependency. Passed in so this module never imports app."""
    router = APIRouter(dependencies=[Depends(require_login)])

    @router.post("/briefing")
    async def briefing(req: BriefingRequest) -> dict:
        now = int(time.time() * 1000)
        try:
            facts = gather.gather(hub.live, req.mmsis, now, {m: o.model_dump(exclude_none=True) for m, o in req.origins.items()})
        except KeyError as e:
            raise HTTPException(404, f"ship {e.args[0]} is not in the live picture")
        try:
            summary = await gemini.summarise(facts)
        except gemini.BriefingError as e:
            raise HTTPException(e.status, str(e))
        return {"generated_at": now, "model": gemini.MODEL, "mmsis": [s["vessel"]["mmsi"] for s in facts["ships"]],
                "facts": facts, "summary": summary.model_dump(), "voice_available": voice.available()}

    @router.post("/briefing/speech")
    async def speech(req: SpeechRequest) -> Response:
        try:
            audio = await voice.speak(req.text)
        except gemini.BriefingError as e:
            raise HTTPException(e.status, str(e))
        return Response(audio, media_type="audio/mpeg")

    return router
