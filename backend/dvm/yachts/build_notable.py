"""Rebuild notable.json from Wikipedia's "List of motor yachts by length" (CC BY-SA 4.0). Run by hand, not by the server:

    python -m dvm.yachts.build_notable

Takes name, length, the owner as listed and the yacht's article URL from the table, and the IMO number from each
linked article's infobox. Rows without a valid IMO are dropped (we match by IMO only).
"""
from __future__ import annotations

import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import quote, unquote

import httpx

from dvm.yachts.ref import NOTABLE_PATH, imo_of

API = "https://en.wikipedia.org/w/api.php"
PAGE = "List_of_motor_yachts_by_length"
UA = {"User-Agent": "DarkVesselMonitor/0.1 (https://github.com/Hamish-MarshallDawson/Hedged-Bets-hacktheburgh) httpx"}


class Table(HTMLParser):
    """Rows of the first wikitable: per cell, its text (citations removed) and its first /wiki/ link."""

    def __init__(self):
        super().__init__()
        self.rows, self.cell, self.depth, self.sup, self.done = [], None, 0, 0, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.done:
            return
        if tag == "table" and "wikitable" in (a.get("class") or ""):
            self.depth += 1
        elif self.depth and tag == "tr":
            self.rows.append([])
        elif self.depth and tag == "td":
            self.cell = {"text": "", "href": None}
            self.rows[-1].append(self.cell)
        elif tag == "sup":
            self.sup += 1
        elif tag == "a" and self.cell is not None and self.cell["href"] is None and not self.sup:
            h = a.get("href") or ""
            if h.startswith("/wiki/") and ":" not in h:
                self.cell["href"] = h

    def handle_endtag(self, tag):
        if tag == "sup":
            self.sup = max(0, self.sup - 1)
        elif tag == "td":
            self.cell = None
        elif tag == "table" and self.depth:
            self.depth, self.done = 0, True

    def handle_data(self, data):
        if self.cell is not None and not self.sup:
            self.cell["text"] += data


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def main() -> None:
    with httpx.Client(headers=UA, timeout=30) as c:
        page = c.get(API, params={"action": "parse", "page": PAGE, "prop": "text|revid",
                                  "format": "json", "formatversion": 2}).json()["parse"]
        t = Table()
        t.feed(page["text"])
        rows = []
        for r in t.rows:
            if len(r) < 5 or not r[1]["href"]:
                continue
            m = re.match(r"([\d.]+)\s*m", clean(r[2]["text"]))
            rows.append({"name": clean(r[1]["text"]), "length_m": float(m.group(1)) if m else None,
                         "owner": clean(r[4]["text"]) or None, "title": unquote(r[1]["href"][len("/wiki/"):]).split("#")[0]})
        imos: dict[str, int | None] = {}
        titles = sorted({r["title"] for r in rows})
        for i in range(0, len(titles), 50):
            q = c.get(API, params={"action": "query", "titles": "|".join(titles[i:i + 50]), "prop": "revisions",
                                   "rvprop": "content", "rvslots": "main", "redirects": 1,
                                   "format": "json", "formatversion": 2}).json()["query"]
            back = {x["to"]: x["from"] for x in q.get("redirects", []) + q.get("normalized", [])}
            for p in q["pages"]:
                text = (p.get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content", "")
                # infobox: "| Ship identification = IMO number: 1011185" or "{{IMO Number|1011185}}"
                text = re.sub(r"\{\{\s*IMO\s*Number\s*\|\s*(\d{7})", r"IMO \1", text, flags=re.I)
                text = re.sub(r"IMO\s*(?:number|no\.?)?\s*:?\s*(\d{7})", r"IMO \1", text, flags=re.I)
                key = p["title"]
                while key in back:
                    key = back[key]
                imos[key.replace(" ", "_")] = imo_of(text)
            time.sleep(0.5)
    yachts = []
    for r in rows:
        imo = imos.get(r["title"])
        if imo:
            yachts.append({"imo": imo, "name": r["name"], "length_m": r["length_m"], "owner": r["owner"],
                           "url": "https://en.wikipedia.org/wiki/" + quote(r["title"], safe="()'_,.!-")})
    out = {"source": f"https://en.wikipedia.org/wiki/{PAGE}", "revision": page["revid"],
           "license": "CC BY-SA 4.0", "attribution": "Wikipedia contributors, \"List of motor yachts by length\"",
           "fetched": time.strftime("%Y-%m-%d", time.gmtime()), "yachts": yachts}
    NOTABLE_PATH.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} rows with an article, {len(yachts)} with a valid IMO -> {NOTABLE_PATH}")


if __name__ == "__main__":
    main()
