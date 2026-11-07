"""Parse cached AISHub station-directory pages (no network) into a station list by country."""
import json, re, collections, pathlib
D = pathlib.Path("/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/mt-receivers")
rows = []
for f in sorted((D / "aishub_pages").glob("p*.html"), key=lambda p: int(p.stem[1:])):
    h = f.read_text(encoding="utf-8", errors="replace")
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
        c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td.*?>(.*?)</td>", r, re.S)]
        c = [re.sub(r"\s+", " ", x.replace("&nbsp;", " ")).strip() for x in c]
        if len(c) >= 7 and re.fullmatch(r"\d{3,4}", c[0] or ""):
            rows.append(dict(id=int(c[0]), status=c[1], uptime=c[2], country=c[3],
                             location=c[4], ships=c[5], distinct=c[6],
                             contributor=c[7] if len(c) > 7 else ""))
(D / "aishub_stations.json").write_text(json.dumps(rows, indent=1))
print("total", len(rows))
c = collections.Counter(r["country"] for r in rows)
print("countries", len(c))
print("\nTop 12 countries:")
for k, v in c.most_common(12):
    print(f"  {k:26s}{v}")
GULF = ["United Arab Emirates","Oman","Qatar","Saudi Arabia","Kuwait","Bahrain","Iraq","Iran","Yemen","Egypt","Israel","Jordan"]
SEA = ["Singapore","Malaysia","Indonesia","Thailand","Vietnam","Philippines","India","Sri Lanka","Bangladesh","Pakistan","China","Taiwan","Japan","South Korea","Hong Kong"]
print("\nGulf + Red Sea:")
g = 0
for k in GULF:
    if c.get(k): print(f"  {k:26s}{c[k]}"); g += c[k]
print("  TOTAL", g)
print("\nSE/E Asia:")
s = 0
for k in SEA:
    if c.get(k): print(f"  {k:26s}{c[k]}"); s += c[k]
print("  TOTAL", s)
print("\nReference (Baltic + NW Europe + UK):")
for k in ["United Kingdom","Ireland","Norway","Sweden","Denmark","Finland","Estonia","Latvia","Lithuania","Poland","Germany","Netherlands","Russia"]:
    print(f"  {k:26s}{c.get(k,0)}")
print("\nGulf station rows:")
for r in rows:
    if r["country"] in GULF:
        print(f"  {r['id']} {r['country']} | {r['location']} | ships {r['ships']} | unique {r['distinct']} | uptime {r['uptime']}")
print("\nUK+Ireland station rows:")
for r in rows:
    if r["country"] in ("United Kingdom","Ireland"):
        print(f"  {r['id']} {r['country']} | {r['location']} | ships {r['ships']} | unique {r['distinct']} | uptime {r['uptime']}")
