#!/usr/bin/env bash
set -euo pipefail

# Analytics config (see birdle/src/backend/ANALYTICS.md):
#   STATS_TOKEN  - required to use the /internal/stats API. Unset => API disabled.
#   GEOIP_DB_PATH - optional MaxMind GeoLite2-Country.mmdb for the country column.
# Put these in a .env file next to this script (KEY=value per line); it is
# git-ignored. The named volume "birdle-data" keeps analytics.db + the IP salt
# across redeploys.

ENV_FILE_ARG=()
[ -f .env ] && ENV_FILE_ARG=(--env-file .env)

docker build -f Dockerfile.prod -t birdle .
docker rm -f birdle 2>/dev/null || true
docker run -d --restart unless-stopped \
  -p 8000:8000 \
  -v birdle-data:/app/data \
  "${ENV_FILE_ARG[@]}" \
  --name birdle birdle
