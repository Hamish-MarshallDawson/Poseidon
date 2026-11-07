"""AISStream client. The reader only stamps and enqueues: AISStream drops slow readers, and drops look like dark ships.

Canonical reference, check it before changing AISStream code: https://aisstream.io/documentation#reference
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time

import websockets

from dvm.normalise import SUBSCRIBED_TYPES

log = logging.getLogger(__name__)


def now_ms() -> int:
    return time.time_ns() // 1_000_000


class Feed:
    def __init__(self):
        self.state = "down"           # up | down
        self.received = 0
        self.dropped = 0              # queue full: our own stall
        self.last_error: str | None = None


def subscription(api_key: str, bbox_lonlat: list) -> dict:
    """bbox is (lon, lat) corners as in 06; AISStream wants (lat, lon)."""
    (lon1, lat1), (lon2, lat2) = bbox_lonlat
    return {"APIKey": api_key, "BoundingBoxes": [[[lat1, lon1], [lat2, lon2]]], "FilterMessageTypes": SUBSCRIBED_TYPES}


async def run_aisstream(url: str, api_key: str, bbox: list, queue: asyncio.Queue, feed: Feed) -> None:
    backoff = 1.0
    while True:
        started = time.monotonic()
        try:
            # compression="deflate" is permessage-deflate (the websockets default, kept explicit).
            async with websockets.connect(url, compression="deflate", open_timeout=10, max_size=2**22) as ws:
                await ws.send(json.dumps(subscription(api_key, bbox)))   # must arrive within 3 s of connecting
                log.info("AISStream connected, bbox (lon, lat) %s; waiting for SubscriptionConfirmation", bbox)
                async for msg in ws:
                    try:
                        queue.put_nowait((now_ms(), msg))
                        feed.received += 1
                    except asyncio.QueueFull:
                        feed.dropped += 1
        except asyncio.CancelledError:
            raise
        except Exception as e:  # network, handshake, server close: always reconnect
            feed.last_error = f"{type(e).__name__}: {e}"
            log.warning("AISStream disconnected: %s", feed.last_error)
        feed.state = "down"
        if time.monotonic() - started > 60:
            backoff = 1.0   # it was healthy for a while: reconnect quickly
        await asyncio.sleep(backoff / 2 + random.uniform(0, backoff / 2))   # backoff with jitter
        backoff = min(backoff * 2, 60.0)
