#!/usr/bin/env bash
# mt-access evidence fetcher, 2026-11-07.
# Fetches the *public* MarineTraffic/Kpler documentation pages used in mt-access.md
# and prints their text. Does NOT touch www.marinetraffic.com product pages (403 Cloudflare,
# and bypassing that is out of scope for the wave), any private map endpoint, or any login.
# Usage: bash fetch_mt_pages.sh [outdir]
set -u
OUT=${1:-/tmp/mt-access-pages}
mkdir -p "$OUT"
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'

urls=(
  "https://servicedocs.marinetraffic.com/"
  "https://servicedocs.marinetraffic.com/tag/Balances/"
  "https://support.marinetraffic.com/en/articles/9552658-marinetraffic-online-plans"
  "https://support.marinetraffic.com/en/articles/9552679-how-to-purchase-a-plan"
  "https://support.marinetraffic.com/en/articles/12578604-how-to-start-a-free-trial-for-a-plan"
  "https://support.marinetraffic.com/en/articles/9552899-how-can-i-export-data"
  "https://support.marinetraffic.com/en/articles/9552907-how-can-i-activate-satellite-tracking-sat-flex-in-my-online-plan"
  "https://support.marinetraffic.com/en/articles/14594297-how-was-the-vessel-s-position-received-terrestrial-or-satellite"
  "https://support.marinetraffic.com/en/articles/9552976-what-benefits-do-i-get-as-an-ais-partner"
  "https://support.marinetraffic.com/en/articles/9552990-as-an-active-ais-partner-can-i-get-ais-data"
  "https://support.marinetraffic.com/en/articles/10248814-marinetraffic-roaming-data-partnership"
  "https://support.marinetraffic.com/en/articles/10442248-22-january-2025-we-re-removing-add-ons-and-credits-from-marinetraffic"
  "https://www.kpler.com/company/terms-of-use"
  "https://www.kpler.com/product/maritime/data-services"
)

for u in "${urls[@]}"; do
  f="$OUT/$(echo "$u" | md5sum | cut -c1-8).html"
  code=$(curl -sSL --compressed -A "$UA" --max-time 30 -o "$f" -w '%{http_code}' "$u")
  echo "== $code $u -> $f"
done

# servicedocs renders its OpenAPI spec from a JS bundle; the spec text (and the
# "100 requests/minute per key" note) lives there.
curl -sSL --compressed -A "$UA" --max-time 40 "https://servicedocs.marinetraffic.com/" -o "$OUT/servicedocs.html"
spec=$(grep -oE 'src="redocly-state-[a-f0-9]+\.js"' "$OUT/servicedocs.html" | sed 's/src="//;s/"//')
[ -n "$spec" ] && curl -sSL --compressed -A "$UA" --max-time 40 "https://servicedocs.marinetraffic.com/$spec" -o "$OUT/state.js" \
  && echo "spec bundle -> $OUT/state.js"

python3 -I - "$OUT" <<'PY'
import re, html, sys, glob, os
out = sys.argv[1]
for f in sorted(glob.glob(os.path.join(out, '*.html'))):
    s = open(f, encoding='utf-8', errors='replace').read()
    if f.endswith('state.js'):
        continue
    m = re.search(r'(?is)<main.*?</main>', s)
    s = m.group(0) if m else s
    s = re.sub(r'(?is)<(script|style|svg|nav|footer)[^>]*>.*?</\1>', ' ', s)
    s = re.sub(r'(?s)<[^>]+>', '\n', s)
    s = html.unescape(s)
    s = re.sub(r'[ \t\xa0]+', ' ', s)
    s = re.sub(r'\n\s*\n+', '\n', s)
    print('=' * 20, os.path.basename(f))
    print(s.strip()[:2000])
PY
