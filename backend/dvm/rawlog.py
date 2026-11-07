"""Append-only raw log, the replay source (06 section 4.1): data/raw/<src>/<UTC hour>.jsonl, gzipped on rotation."""
from __future__ import annotations

import gzip
import json
import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


def _gzip(path: Path) -> None:
    with path.open("rb") as src, gzip.open(path.with_suffix(".jsonl.gz"), "wb") as dst:
        shutil.copyfileobj(src, dst)
    path.unlink()


class RawLog:
    def __init__(self, root: Path):
        self.root = root
        self.files: dict[str, tuple[str, object]] = {}   # src -> (hour, open file)

    def write(self, src: str, recv_ts: int, raw: object) -> None:
        hour = datetime.fromtimestamp(recv_ts / 1000, timezone.utc).strftime("%Y-%m-%dT%H")
        cur = self.files.get(src)
        if not cur or cur[0] != hour:
            if cur:
                self._rotate(cur[1])
            d = self.root / "raw" / src
            d.mkdir(parents=True, exist_ok=True)
            cur = self.files[src] = (hour, (d / f"{hour}.jsonl").open("a", encoding="utf-8"))
        cur[1].write(json.dumps({"v": 1, "src": src, "recv_ts": recv_ts, "raw": raw}, separators=(",", ":")) + "\n")

    def _rotate(self, f) -> None:
        f.close()
        threading.Thread(target=_gzip, args=(Path(f.name),), daemon=True).start()

    def flush(self) -> None:
        for _, f in self.files.values():
            f.flush()

    def close(self) -> None:
        # shortcut: the current hour stays plain .jsonl on shutdown; replay should read both .jsonl and .jsonl.gz.
        for _, f in self.files.values():
            f.close()
        self.files.clear()
