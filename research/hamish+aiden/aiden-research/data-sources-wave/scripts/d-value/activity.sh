#!/bin/bash
# commit activity for candidate prior-art repos, last 90 days
since=$(date -u -d '90 days ago' +%Y-%m-%dT%H:%M:%SZ)
for r in esamoun/dark-vessel-detection gSulpizio/sat_tracker kelu124/OrmuzOsint FormerLab/shadow-fleet-tracker-light allenai/rslearn_projects GlobalFishingWatch/gfw-api-python-client; do
  n=$(curl -s -m 30 "https://api.github.com/repos/$r/commits?since=$since&per_page=100" | jq 'if type=="array" then length else -1 end')
  last=$(curl -s -m 30 "https://api.github.com/repos/$r/commits?per_page=1" | jq -r '.[0].commit.author.date // "none"')
  auth=$(curl -s -m 30 "https://api.github.com/repos/$r/commits?per_page=20" | jq -r '[.[].author.login] | unique | length' )
  echo -e "$r\tcommits_90d=$n\tlast=$last\tdistinct_authors_last20=$auth"
  sleep 1
done
