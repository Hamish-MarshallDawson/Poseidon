#!/bin/bash
W=/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave
OUT=$W/data/d-ais/probe2-results.txt
: > "$OUT"
p() { local n="$1" u="$2"; shift 2
  local r; r=$(curl -sS --max-time 20 "$@" -o /tmp/_b2 -w '%{http_code}|%{size_download}|%{time_total}|%{content_type}' "$u" 2>/tmp/_e2) || true
  printf '%s\t%s\t%s\n' "$n" "$r" "$(head -c 300 /tmp/_b2 | tr '\n\r\t' '   ')" >> "$OUT"
  printf '%-24s %s\n   %s\n' "$n" "$r" "$(head -c 160 /tmp/_b2 | tr '\n\r\t' '   ')"
}
H='Digitraffic-User: hacktheburgh/feasibility'
p digitraffic-vessels-gz "https://meri.digitraffic.fi/api/ais/v1/vessels" -H "$H" -H 'Accept-Encoding: gzip' --compressed
p digitraffic-loc-gz "https://meri.digitraffic.fi/api/ais/v1/locations" -H "$H" -H 'Accept-Encoding: gzip' --compressed
p noaa-cmsp-2024 "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/index.html"
p noaa-cmsp-2025 "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2025/index.html"
p bw-live-root "https://live.ais.barentswatch.no/"
p bw-live-api "https://live.ais.barentswatch.no/api/ais"
p bw-open "https://www.barentswatch.no/bwapi/open/"
p bw-ais-v2 "https://www.barentswatch.no/bwapi/v2/ais/live/ais"
p irish-folders "https://atlas.marine.ie/arcgis/rest/services?f=pjson"
p ckan-fr "https://www.data.gouv.fr/api/1/datasets/?q=AIS%20navire&page_size=3"
p ckan-ie "https://data.gov.ie/api/3/action/package_search?q=AIS&rows=3"
p ckan-us "https://catalog.data.gov/api/3/action/package_search?q=AIS+vessel&rows=3"
p ckan-au "https://data.gov.au/data/api/3/action/package_search?q=AIS&rows=3"
p ckan-ca "https://open.canada.ca/data/api/3/action/package_search?q=AIS&rows=3"
p ckan-nz "https://catalogue.data.govt.nz/api/3/action/package_search?q=AIS&rows=3"
p bsh-ais "https://www.bsh.de/EN/DATA/Data-Products/data-products_node.html"
p emodnet-ais "https://emodnet.ec.europa.eu/geoviewer/"
p gfw-docs "https://globalfishingwatch.org/our-apis/documentation"
