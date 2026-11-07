"""AISStream rate rules: the ONE place they live, and the code that enforces them.

AISStream bans clients for what they *send* (connections, reconnects, subscription updates), not for the
messages they push to us. Sources:
- DOC, section 05 "Limits and operational considerations": https://aisstream.io/documentation#reference
- Ban reports at https://github.com/aisstream/issues: #256 and #287 (IP banned with 429 after reconnect loops
  capped at 2 and 5 min), #302 (account-level 429 that survived key rotation), #292 (ghost connections kept
  the 3-connection quota full, so every new connect got 429).

Breaking a rule raises RateRuleBreach. The caller logs it loudly and stops; it never retries around it.
State is saved to disk, so restarting the backend does not reset the backoff or the hourly count.
"""
from __future__ import annotations

import json
import logging
import random
import socket
import time
from collections import deque
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

DOC = "https://aisstream.io/documentation#reference"

# Their cap is 3 subscribed connections per account and 3 open per IP (DOC, Limits). We hold at most 1, so a
# ghost connection (#292) or a teammate on the same network never takes us over the cap.
MAX_CONNECTIONS = 1
# One backend process per machine holds the connection: a second one fails to bind this localhost port.
HOST_LOCK_PORT = 47821
# DOC: "send one complete JSON subscription within three seconds" or the connection closes. We send it at once.
SUBSCRIBE_DEADLINE_S = 3.0
# DOC: "Subscription updates: 1 per second per connection. A faster update closes the connection." Margin added.
MIN_SUBSCRIPTION_INTERVAL_S = 2.0
# DOC: uncompressed connections are bandwidth-limited and drop messages. permessage-deflate, always.
COMPRESSION = "deflate"
# Reconnect backoff: doubles from 5 s, jitter up to +50 %, cap 30 min (#256 and #287 were banned at 2 and 5 min caps).
BACKOFF_MIN_S = 5.0
BACKOFF_MAX_S = 1800.0
# A connection that stayed up this long counts as healthy and resets the backoff.
HEALTHY_AFTER_S = 300.0
# Ceiling on connection attempts in any rolling hour, across restarts.
MAX_CONNECTS_PER_HOUR = 12
# After HTTP 429/401/403 at the handshake, an error message from the server, or a policy close (1008):
# stand down for an hour (#302: an account was still blocked after backing off 5 min per 429).
PENALTY_S = 3600.0
PENALTY_HTTP = (401, 403, 429)
PENALTY_CLOSE_CODES = (1008,)
# DOC: "Read continuously ... the service drops messages" from slow readers. The reader only enqueues into this
# queue and never waits; if the queue is ever full we drop locally and count it, rather than slow the socket.
QUEUE_MAX = 100_000


class RateRuleBreach(RuntimeError):
    """Something tried to break an AISStream rate rule. Never retry around it."""


class AisLimiter:
    def __init__(self, state_path: Path | None = None, clock: Callable[[], float] = time.time,
                 rand: Callable[[], float] = random.random):
        self.path, self.clock, self.rand = state_path, clock, rand
        self.open = 0
        self.connects: deque[float] = deque()   # start times of connection attempts, last hour
        self.backoff = BACKOFF_MIN_S
        self.not_before = 0.0
        self.connected_at = 0.0
        self.last_subscription: float | None = None
        self.penalty_reason: str | None = None
        self._lock_sock: socket.socket | None = None
        if self.path and self.path.exists():
            s = json.loads(self.path.read_text())
            self.connects = deque(s["connects"])
            self.backoff, self.not_before, self.penalty_reason = s["backoff"], s["not_before"], s.get("penalty_reason")

    def _save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"connects": list(self.connects), "backoff": self.backoff,
                                             "not_before": self.not_before, "penalty_reason": self.penalty_reason}))

    def _trim(self, now: float) -> None:
        while self.connects and self.connects[0] <= now - 3600:
            self.connects.popleft()

    def _breach(self, why: str) -> None:
        log.critical("AISSTREAM RATE RULE BREACH REFUSED: %s (rules: dvm/limits.py, %s)", why, DOC)
        raise RateRuleBreach(why)

    def acquire_host_lock(self) -> None:
        """Only one process per machine may talk to AISStream."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", HOST_LOCK_PORT))
        except OSError:
            s.close()
            self._breach("another backend on this machine already holds the AISStream connection")
        self._lock_sock = s

    def delay(self) -> float:
        """Seconds until the next connection attempt is allowed (backoff, penalty and hourly ceiling)."""
        now = self.clock()
        self._trim(now)
        wait = self.not_before - now
        if len(self.connects) >= MAX_CONNECTS_PER_HOUR:
            wait = max(wait, self.connects[0] + 3600 - now)
        return max(0.0, wait)

    def open_connection(self, compression: str) -> None:
        """Call right before connecting. Raises instead of breaking a rule."""
        now = self.clock()
        self._trim(now)
        if compression != COMPRESSION:
            self._breach(f"compression {compression!r}; permessage-deflate is mandatory")
        if self.open >= MAX_CONNECTIONS:
            self._breach(f"a connection is already open (max {MAX_CONNECTIONS})")
        if now < self.not_before:
            self._breach(f"connecting {self.not_before - now:.0f} s before the backoff allows it")
        if len(self.connects) >= MAX_CONNECTS_PER_HOUR:
            self._breach(f"{len(self.connects)} connects in the last hour (max {MAX_CONNECTS_PER_HOUR})")
        self.open += 1
        self.connects.append(now)
        self.connected_at = now
        self.last_subscription = None
        self._save()

    def subscribe(self) -> None:
        """Call right before sending a subscription on the open connection."""
        now = self.clock()
        if self.open < 1:
            self._breach("subscription sent with no open connection")
        if self.last_subscription is not None and now - self.last_subscription < MIN_SUBSCRIPTION_INTERVAL_S:
            self._breach(f"subscription update {now - self.last_subscription:.2f} s after the last one "
                         f"(min {MIN_SUBSCRIPTION_INTERVAL_S} s)")
        self.last_subscription = now

    def closed(self, penalty: str | None = None) -> None:
        """The connection is over: schedule the next attempt with backoff and jitter, or the long penalty."""
        now = self.clock()
        self.open = max(0, self.open - 1)
        if now - self.connected_at >= HEALTHY_AFTER_S:
            self.backoff = BACKOFF_MIN_S
        if penalty:
            self.not_before = now + PENALTY_S
            self.penalty_reason = penalty
            log.critical("AISStream PENALTY: %s. No connection for %.0f min. Check the account at https://aisstream.io "
                         "before restarting.", penalty, PENALTY_S / 60)
        else:
            self.not_before = now + self.backoff * (1 + self.rand() / 2)
            self.backoff = min(self.backoff * 2, BACKOFF_MAX_S)
        self._save()

    def status(self) -> dict:
        now = self.clock()
        self._trim(now)
        return {"open": self.open, "connects_last_hour": len(self.connects), "next_connect_in_s": round(self.delay()),
                "penalty_reason": self.penalty_reason if now < self.not_before else None}
