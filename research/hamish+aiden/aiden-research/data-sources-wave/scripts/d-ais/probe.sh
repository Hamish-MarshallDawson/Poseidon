#!/bin/bash
# d-ais: reachability probe of candidate AIS sources, no credentials used.
# Prints: name | http_code | bytes | time | content-type | first 180 chars of body
OUT=/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/d-ais/probe-results.txt
: > "$OUT"

probe() {
  local name="$1" url="$2"; shift 2
  local body code size time ctype
  body=$(curl -sS -L --max-time 15 "$@" -o /tmp/_probe_body -w '%{http_code}|%{size_download}|%{time_total}|%{content_type}' "$url" 2>/tmp/_probe_err) || true
  IFS='|' read -r code size time ctype <<< "$body"
  local snippet
  snippet=$(head -c 200 /tmp/_probe_body 2>/dev/null | tr '\n\r\t' '   ')
  local err; err=$(head -c 120 /tmp/_probe_err 2>/dev/null | tr '\n\r\t' '   ')
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$code" "$size" "$time" "$ctype" "$snippet" "$err" >> "$OUT"
  printf '%-28s %s %sB %ss %s\n' "$name" "$code" "$size" "$time" "${snippet:0:90}"
}

H='Digitraffic-User: hacktheburgh/feasibility'
UA='-A Mozilla/5.0 (feasibility-test; hacktheburgh)'

probe "digitraffic-vessels"   "https://meri.digitraffic.fi/api/ais/v1/vessels" -H "$H"
probe "digitraffic-locations" "https://meri.digitraffic.fi/api/ais/v1/locations" -H "$H"
probe "barentswatch-sse"      "https://live.ais.barentswatch.no/live" --max-time 8
probe "barentswatch-bwapi"    "https://www.barentswatch.no/bwapi/open/api/v1/ais/ais"
probe "kystverket-ais"        "https://www.kystverket.no/"
probe "irish-marine-atlas"    "https://atlas.marine.ie/arcgis/rest/services?f=pjson"
probe "irish-ais-layer"       "https://atlas.marine.ie/arcgis/rest/services/AIS/MapServer?f=pjson"
probe "noaa-marinecadastre"   "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/index.html"
probe "noaa-ais-pds"          "https://noaa-ais-pds.s3.amazonaws.com/?list-type=2&max-keys=5"
probe "aishub-ws"             "https://data.aishub.net/ws.php?format=1&output=json&compress=0"
probe "aisstream-docs"        "https://aisstream.io/documentation"
probe "marinetraffic-api"     "https://services.marinetraffic.com/api/exportvessels/v:8/"
probe "vesselfinder-api"      "https://api.vesselfinder.com/vessels"
probe "datalastic-api"        "https://api.datalastic.com/api/v0/vessel"
probe "fleetmon-api"          "https://api.fleetmon.com/vault/api/v1/apikeys/"
probe "myshiptracking-api"    "https://api.myshiptracking.com/api/v2/vessels"
probe "gfw-vessels"           "https://gateway.api.globalfishingwatch.org/v3/vessels/search?query=tanker&limit=1"
probe "dma-ais-dk"            "http://aisdata.ais.dk/aisdk-2026-11-01.zip" --max-time 12 -r 0-1000
probe "emodnet-ha"            "https://www.emodnet-humanactivities.eu/"
probe "seavision"             "https://seavision.space/"
probe "indo-kkp-vms"          "https://vms.kkp.go.id/"
probe "indo-fishnet"          "https://fishnet.kkp.go.id/"
probe "chile-sernapesca"      "https://www.sernapesca.cl/"
probe "peru-imarpe"           "https://www.gob.pe/imarp"
probe "panama-amp"            "https://amp.gob.pa/"
probe "taiwan-motc-ais"       "https://ais.motc.gov.tw/"
probe "korea-datagokr"        "https://www.data.go.kr/data/15057041/fileData.do"
probe "japan-jcg"             "https://www.kaiho.mlit.go.jp/"
probe "singapore-mpa"         "https://www.mpa.gov.sg/"
probe "malaysia-marine"       "https://www.marine.gov.my/"
probe "thailand-md"           "https://www.md.go.th/"
probe "vietnam-vinamarine"    "https://vinamarine.gov.vn/"
probe "philippines-pcg"       "https://www.coastguard.gov.ph/"
probe "india-dgshipping"      "https://www.dgshipping.gov.in/"
probe "australia-amsa"        "https://www.amsa.gov.au/"
probe "canada-open-ais"       "https://open.canada.ca/data/en/dataset?q=AIS"
probe "onc-ais"               "https://data.oceannetworks.ca/api/locations?method=get&token=&locationCode=CF247"
probe "spire-maritime"        "https://spire.com/maritime/"
echo "--- done, results in $OUT"
