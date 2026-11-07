"""AISStream client. Every connect, subscription and reconnect goes through dvm/limits.py (the rate rules).

Canonical reference, check it before changing AISStream code: https://aisstream.io/documentation#reference
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

import websockets

from dvm import limits
from dvm.normalise import SUBSCRIBED_TYPES

log = logging.getLogger(__name__)


def now_ms() -> int:
    return time.time_ns() // 1_000_000


class Feed:
    def __init__(self):
        self.state = "down"           # up (after SubscriptionConfirmation) | down
        self.received = 0
        self.dropped = 0              # our queue was full: dropped locally rather than slow the socket
        self.last_error: str | None = None


def subscription(api_key: str, bbox_lonlat: list) -> dict:
    """bbox is (lon, lat) corners as in 06; AISStream wants (lat, lon)."""
    (lon1, lat1), (lon2, lat2) = bbox_lonlat
    return {"APIKey": api_key, "BoundingBoxes": [[[lat1, lon1], [lat2, lon2]]], "FilterMessageTypes": SUBSCRIBED_TYPES}


def enqueue(queue: asyncio.Queue, msg, feed: Feed) -> None:
    """The reader never waits: AISStream drops slow readers, and drops look like dark ships."""
    try:
        queue.put_nowait((now_ms(), msg))
        feed.received += 1
    except asyncio.QueueFull:
        feed.dropped += 1
        if feed.dropped % 1000 == 1:
            log.error("Ingest queue full (%d): consumer is too slow, dropped %d messages", queue.maxsize, feed.dropped)


def is_server_error(msg) -> bool:
    """AISStream reports a bad key and similar as {"error": "..."} before closing."""
    head = msg[:40]
    return (b'"error"' if isinstance(head, bytes) else '"error"') in head


async def run_aisstream(url: str, api_key: str, bbox: list, queue: asyncio.Queue, feed: Feed,
                        limiter: limits.AisLimiter) -> None:
    try:
        limiter.acquire_host_lock()
        while True:
            wait = limiter.delay()
            if wait > 0:
                feed.state = "down"
                log.info("AISStream: next connection allowed in %.0f s (dvm/limits.py)", wait)
                await asyncio.sleep(min(wait, 60))   # wake up to re-check, never to connect early
                continue
            limiter.open_connection(limits.COMPRESSION)
            penalty, why = None, "AISStream ended the stream"
            try:
                async with websockets.connect(url, compression=limits.COMPRESSION, open_timeout=10, close_timeout=5,
                                              max_size=2**22) as ws:
                    limiter.subscribe()
                    await asyncio.wait_for(ws.send(json.dumps(subscription(api_key, bbox))), limits.SUBSCRIBE_DEADLINE_S)
                    log.info("AISStream connected, bbox (lon, lat) %s; waiting for SubscriptionConfirmation", bbox)
                    async for msg in ws:
                        enqueue(queue, msg, feed)   # the consumer logs and stores it, including any error
                        if is_server_error(msg):
                            penalty = "AISStream sent an error message (bad key or account problem)"
                            break
            except websockets.InvalidStatus as e:
                code = e.response.status_code
                why = f"HTTP {code} at handshake"
                if code in limits.PENALTY_HTTP:
                    penalty = why
            except websockets.ConnectionClosed as e:
                why = f"closed: {e}"
                if e.rcvd and e.rcvd.code in limits.PENALTY_CLOSE_CODES:
                    penalty = f"closed by AISStream with code {e.rcvd.code}"
            except limits.RateRuleBreach:
                raise
            except asyncio.CancelledError:
                limiter.closed()   # shutting down: the async with above already sent a clean close frame
                raise
            except Exception as e:  # network or handshake trouble: back off and try again
                why = f"{type(e).__name__}: {e}"
            feed.state, feed.last_error = "down", penalty or why
            log.warning("AISStream disconnected: %s", feed.last_error)
            limiter.closed(penalty)
    except limits.RateRuleBreach as e:
        feed.state, feed.last_error = "down", f"rate rule breach, ingest stopped: {e}"   # refuse, never retry
