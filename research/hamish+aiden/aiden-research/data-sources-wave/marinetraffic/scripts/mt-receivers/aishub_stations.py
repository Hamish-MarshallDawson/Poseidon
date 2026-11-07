"""Read AISHub's public station directory (aishub.net/stations, 50 rows/page), 1.5 s apart.
Caches each page; writes a JSON summary of stations by country."""
import json, re, sys, time, urllib.request, pathlib

OUT = pathlib.Path("/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/mt-receivers")
CACHE = OUT / "aishub_pages"
CACHE.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (hacktheburgh research; feasibility check)"
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)

def get(page):
    f = CACHE / f"p{page}.html"
    if f.exists() and f.stat().st_size > 1000:
        return f.read_text(encoding="utf-8", errors="replace")
    url = f"https://www.aishub.net/stations?page={page}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        h = r.read().decode("utf-8", errors="replace")
    f.write_text(h, encoding="utf-8")
    time.sleep(1.5)
    return h

def cells(row):
    return [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td.*?>(.*?)</td>", row, re.S)]

rows = []
pages = int(sys.argv[1]) if len(sys.argv) > 1 else 36
for p in range(1, pages + 1):
    h = get(p)
    for r in ROW.findall(h):
        c = cells(r)
        if len(c) >= 7 and "+" not in c[0] and c[0].isdigit() is False:
            pass
        if len(c) >= 7 and re.fullmatch(r"\d{3,4}", c[0] or ""):
            rows.append({"id": int(c[0]), "uptime": c[1], "country": c[2], "location": c[3],
                         "ships": c[4], "distinct": c[5], "contributor": c[6] if len(c) > 6 else ""})
    print("page", p, "rows", len(rows), flush=True)

(OUT / "aishub_stations.json").write_text(json.dumps(rows, indent=1))
print("total", len(rows))
