#!/bin/sh
# mt-gulf-feeds probe log, 7 Nov 2026. Read-only GETs, no auth, no bypass attempts.
UA='Mozilla/5.0 (research; hacktheburgh feasibility)'
# Thai Marine Dept public Esri layers (returned US MarineCadastre 2022 sample data)
curl -sSL -A "$UA" "https://esrith-bd.cdg.co.th/server/rest/services?f=json"
curl -sSL -A "$UA" "https://esrith-bd.cdg.co.th/server/rest/services/Hosted?f=json"
curl -sSL -A "$UA" "https://esrith-bd.cdg.co.th/server/rest/services/MD?f=json"   # -> 499 Token Required
BASE="https://esrith-bd.cdg.co.th/server/rest/services/Hosted/%E0%B8%82%E0%B9%89%E0%B8%AD%E0%B8%A1%E0%B8%B9%E0%B8%A5%E0%B9%80%E0%B8%A3%E0%B8%B7%E0%B8%AD_2/FeatureServer/2"
curl -sSL -A "$UA" "$BASE/query?where=1%3D1&returnCountOnly=true&f=json"          # -> {"count":2030}
# Indonesia KKP dashboard (data plane needs OAuth to api.integrated-voyage.com)
curl -sSL -A "$UA" "https://vtc.kkp.go.id/" | grep -oE "client_credential|/modules/webservice/rest/"
# Others
curl -sSL -A "$UA" "https://nsw.md.go.th/mxdataservice/" | head -c 300          # React shell, API-KEY by request
curl -sSL -A "$UA" "https://hpradar.com/api" | sed -e 's/<[^>]*>//g' | grep -i "ais\|request"  # email request
curl -sSL -A "$UA" "https://api.data.gov.my/data-catalogue"                     # 400, 'id' required
curl -sSL -A "$UA" "https://data.gov.sg/api/action/package_search?q=vessel"     # 404, v1 retired
curl -sSL -A "$UA" "https://www.suezcanal.gov.eg/English/Navigation/Pages/NavigationStatistics.aspx"
curl -sSL -A "$UA" "https://zenodo.org/api/records?q=%22automatic+identification+system%22+malacca&type=dataset&size=6"
curl -sSL -A "$UA" "https://zenodo.org/api/records/19571058"
curl -sSL -A "$UA" "https://www.sjofartsverket.se/sv/tjanster/sjokortsprodukter/digital-data/ais-data/"
