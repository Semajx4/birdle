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
# Networking:
#   NETWORK   - Docker network to attach to. Default "cloudflare_default" (the
#               cloudflared compose stack) so the tunnel reaches the app as
#               http://birdle:8000 without any published port. Set to "" to skip.
#   BIND_ADDR - host address to also publish the port on. Default 127.0.0.1:
#               lets you `curl localhost:8000` on the host (e.g. for the stats
#               API) without exposing anything to the LAN / internet. Set to
#               0.0.0.0 to expose it directly, or "" to publish nothing.

ENV_FILE_ARG=()
[ -f .env ] && ENV_FILE_ARG=(--env-file .env)

NETWORK="${NETWORK-cloudflare_default}"
BIND_ADDR="${BIND_ADDR-127.0.0.1}"

NETWORK_ARG=()
[ -n "$NETWORK" ] && NETWORK_ARG=(--network "$NETWORK")

PORT_ARG=()
[ -n "$BIND_ADDR" ] && PORT_ARG=(-p "${BIND_ADDR}:8000:8000")

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
  "${PORT_ARG[@]}" \
  "${NETWORK_ARG[@]}" \
  -v birdle-data:/app/data \
  "${ENV_FILE_ARG[@]}" \
  "${GEOIP_ARG[@]}" \
  --name birdle birdle
