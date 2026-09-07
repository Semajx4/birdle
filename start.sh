#!/usr/bin/env bash
set -euo pipefail

# Analytics config (see birdle/src/backend/ANALYTICS.md):
#   STATS_TOKEN   - required to use the /internal/stats API. Unset => API disabled.
#   GEOIP_DB_PATH - set automatically below if a GeoLite2-Country.mmdb is found
#                   next to this script, either loose or inside an extracted
#                   MaxMind "GeoLite2-Country_YYYYMMDD/" directory. It gets
#                   mounted read-only into the container.
# Put STATS_TOKEN in a .env file next to this script (KEY=value per line); it is
# git-ignored. The named volume "birdle-data" keeps analytics.db + the IP salt
# across redeploys.
#
# BIND_ADDR - host address the container port is published on. Defaults to
#             127.0.0.1 so the app is only reachable via the Cloudflare Tunnel
#             (cloudflared runs on this host). Set to 0.0.0.0 to expose it on
#             the LAN / public interfaces directly.

ENV_FILE_ARG=()
[ -f .env ] && ENV_FILE_ARG=(--env-file .env)

BIND_ADDR="${BIND_ADDR:-127.0.0.1}"

# Locate a GeoLite2 Country database: prefer a loose file, else the newest
# extracted MaxMind release directory.
GEOIP_MMDB=""
if [ -f GeoLite2-Country.mmdb ]; then
  GEOIP_MMDB="$PWD/GeoLite2-Country.mmdb"
else
  for d in $(ls -d GeoLite2-Country_*/ 2>/dev/null | sort -r); do
    if [ -f "${d}GeoLite2-Country.mmdb" ]; then
      GEOIP_MMDB="$PWD/${d}GeoLite2-Country.mmdb"
      break
    fi
  done
fi

GEOIP_ARG=()
if [ -n "$GEOIP_MMDB" ]; then
  echo "GeoIP database: $GEOIP_MMDB"
  GEOIP_ARG=(
    -v "$GEOIP_MMDB:/app/data/GeoLite2-Country.mmdb:ro"
    -e GEOIP_DB_PATH=/app/data/GeoLite2-Country.mmdb
  )
else
  echo "GeoIP database: none found; country lookups disabled"
fi

docker build -f Dockerfile.prod -t birdle .
docker rm -f birdle 2>/dev/null || true
docker run -d --restart unless-stopped \
  -p "${BIND_ADDR}:8000:8000" \
  -v birdle-data:/app/data \
  "${ENV_FILE_ARG[@]}" \
  "${GEOIP_ARG[@]}" \
  --name birdle birdle
