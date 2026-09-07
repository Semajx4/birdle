# birdle

Listen to a bird song and guess the bird.

## Dev

```sh
docker compose up --build
```

Frontend on http://localhost:5173, backend on http://localhost:8000.

## Prod

```sh
./start.sh
```

`start.sh` builds `Dockerfile.prod` (Svelte build + FastAPI, served together on
port 8000) and runs it as a container named `birdle` with
`--restart unless-stopped`. It also:

- mounts the named volume `birdle-data` at `/app/data` so the analytics DB and
  the IP-hash salt survive redeploys;
- loads a `.env` file next to `start.sh` if present (git-ignored), e.g. for
  `STATS_TOKEN`;
- if a MaxMind GeoLite2 Country database sits next to `start.sh` (loose
  `GeoLite2-Country.mmdb` or an extracted `GeoLite2-Country_YYYYMMDD/` dir),
  mounts it into the container and enables GeoIP country lookups automatically;
- publishes the port on `127.0.0.1` only (set `BIND_ADDR=0.0.0.0` to expose it
  directly). Public access is expected to go through a Cloudflare Tunnel
  (`cloudflared` on the host) — see ANALYTICS.md for keeping `/internal/` off
  the tunnel.

App is then on http://localhost:8000 (host-local).

## Analytics

Per-round metrics (players, rounds finished, scores) are recorded to a separate
SQLite DB, with **hashed** client IPs and an optional GeoIP country code. Full
details, schema, and env vars: [`birdle/src/backend/ANALYTICS.md`](birdle/src/backend/ANALYTICS.md).

Read them through the internal stats API. It is disabled until `STATS_TOKEN` is
set, and by default only accepts callers from loopback / private networks.

```sh
# put STATS_TOKEN=... in .env next to start.sh, then:
export STATS_TOKEN=your-token

# overall totals
curl -s -H "X-Stats-Token: $STATS_TOKEN" \
  http://localhost:8000/internal/stats/summary | jq

# per-day breakdown
curl -s -H "X-Stats-Token: $STATS_TOKEN" \
  http://localhost:8000/internal/stats/daily | jq

# by country
curl -s -H "X-Stats-Token: $STATS_TOKEN" \
  http://localhost:8000/internal/stats/countries | jq

# raw rows (params: limit<=1000, offset, finished=true|false, game_date=YYYY-MM-DD)
curl -s -H "X-Stats-Token: $STATS_TOKEN" \
  "http://localhost:8000/internal/stats/rounds?limit=20&finished=true" | jq
```

`Authorization: Bearer $STATS_TOKEN` works instead of the `X-Stats-Token` header.
In dev (`docker compose`) the token defaults to `dev-token` and the caller-IP
allowlist is disabled.

In prod, run these **on the host** (SSH in). `/internal/` should not be routed
through the Cloudflare Tunnel, and the allowlist rejects requests that arrive
with a public `CF-Connecting-IP` even if they carry the token.
