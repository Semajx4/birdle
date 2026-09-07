# Analytics & logging

## What gets recorded

One row per game round in a **separate** SQLite database (`data/analytics.db`,
never mixed with `birds.db`). Table `round_stats`:

| column        | meaning                                                        |
|---------------|---------------------------------------------------------------|
| `round_id`    | UUID of the round (primary key)                               |
| `game_date`   | UTC date of the puzzle the round belongs to                   |
| `bird_id`     | the answer bird                                               |
| `ip_hash`     | salted SHA-256 of the client IP — **never the raw IP**        |
| `country`     | ISO country code from GeoIP, or `NULL` if lookup disabled     |
| `user_agent`  | request User-Agent (truncated to 500 chars)                   |
| `guesses`     | number of guesses made (final, when finished)                 |
| `won`         | did the player get it                                         |
| `finished`    | did the round reach an end (win or 5 guesses)                 |
| `started_at`  | UTC timestamp the round was created                           |
| `finished_at` | UTC timestamp the round ended (`NULL` if abandoned)           |

Derived answers:

* **people who played** = `COUNT(DISTINCT ip_hash)`
* **rounds started** = `COUNT(*)`
* **rounds finished** = `COUNT(*) WHERE finished`
* **scores** = `guesses` / `won` per row, or aggregate `AVG(guesses)`, win rate

### Why hashed IPs

Raw IP addresses are personal data under GDPR/UK GDPR and similar laws. The hash
still lets you count distinct visitors and spot repeat/abuse patterns without
holding PII. The salt lives in `data/analytics_salt.txt` (auto-generated once,
persisted so hashes stay comparable across restarts) or `ANALYTICS_IP_SALT`.
`country` is resolved from the IP *in memory* at request time; the address
itself is never written anywhere.

Consider purging old rows periodically, e.g.
`DELETE FROM round_stats WHERE started_at < date('now','-90 days');`

## Logging

`util/logging_config.py` sets up a console handler + a rotating file handler at
`logs/birdle.log` (5 MB × 5). Loggers:

* `birdle.request` — one line per HTTP request: method, path, status, duration
* `birdle.analytics` — `round_started` / `round_finished` events, salt/GeoIP init

Env: `LOG_LEVEL` (default `INFO`), `LOG_DIR` (default `logs`).

## The internal stats API

Router mounted at `/internal/stats`. **Not for public use** — gated two ways:

1. **Shared secret.** Set `STATS_TOKEN`. Send it as `X-Stats-Token: <token>` or
   `Authorization: Bearer <token>`. If `STATS_TOKEN` is unset the whole router
   returns `503` (disabled by default).
2. **Caller-IP allowlist.** `STATS_ALLOWED_NETWORKS`, comma-separated CIDRs.
   Default: loopback + RFC1918 + ULA. Set it to an empty string to disable the
   check (dev only).

   The allowlist is checked against the **effective** client IP, not the raw
   peer: if a `CF-Connecting-IP` header is present (Cloudflare / Cloudflare
   Tunnel sets it to the real visitor and strips forged copies at the edge)
   that public IP is used — so a request that comes **through the tunnel** is
   judged on the visitor's public address and rejected. A request made on the
   host itself (`curl localhost:8000/...`) carries no such header and is judged
   on the loopback/bridge peer, so it passes.

### Cloudflare Tunnel deployment

This app is served through a Cloudflare Tunnel (`cloudflared` on the host).
Recommended setup so `/internal/` is genuinely unreachable from outside:

1. **Bind the port to loopback.** `start.sh` publishes on `127.0.0.1:8000` by
   default (override with `BIND_ADDR`). `cloudflared`, running on the same
   host, still reaches it; nothing on the LAN / public interface does.
2. **Don't route `/internal/` through the tunnel.** In your tunnel config add a
   path rule that refuses it before the catch-all:

   ```yaml
   ingress:
     - hostname: birdle.example.com
       path: ^/internal/
       service: http_status:404
     - hostname: birdle.example.com
       service: http://localhost:8000
     - service: http_status:404
   ```

   (Dashboard-managed tunnel: add a public-hostname entry for the same host
   with path `/internal/*` pointing at an HTTP 404 / block, ordered above the
   main one. Or protect that path with a Cloudflare Access policy.)
3. **Read the stats from the host** — SSH in and
   `curl -H "X-Stats-Token: $STATS_TOKEN" http://localhost:8000/internal/stats/summary`,
   or point your future local GUI at an SSH tunnel to `localhost:8000`.

With all three, `/internal/` has no public path in, the allowlist rejects any
that slips through, and the token is the last line.

### Endpoints

| method & path                | returns                                              |
|------------------------------|-----------------------------------------------------|
| `GET /internal/stats/summary`| totals: rounds, distinct players, finished, wins, win rate, avg guesses |
| `GET /internal/stats/daily`  | per `game_date`: rounds, players, finished, wins    |
| `GET /internal/stats/countries` | rounds + players grouped by country              |
| `GET /internal/stats/rounds` | raw rows; query params `limit` (≤1000), `offset`, `finished`, `game_date` |

Example:

```sh
curl -H "X-Stats-Token: $STATS_TOKEN" http://localhost:8000/internal/stats/summary
```

## Deployment notes

* `start.sh` mounts a named volume `birdle-data` at `/app/data` so the analytics
  DB and IP salt survive redeploys. Put `STATS_TOKEN=...` in a git-ignored
  `.env` file next to `start.sh`. It publishes the port on `127.0.0.1` only
  (`BIND_ADDR` to change) — see the Cloudflare Tunnel section above.
* For GeoIP, download the free MaxMind **GeoLite2 Country** database (account
  required) and put it next to `start.sh` — either the loose
  `GeoLite2-Country.mmdb` or the extracted `GeoLite2-Country_YYYYMMDD/`
  directory as-is. `start.sh` finds it (newest release wins), mounts it
  read-only into the container, and sets `GEOIP_DB_PATH` automatically. Without
  it, `country` stays `NULL` and everything else still works. (`docker compose`
  dev: set `GEOIP_DB_PATH` yourself and add a matching volume mount.)
* `geoip2` is in `requirements.txt`; rebuild the image after pulling this change
  (`./start.sh`, or `docker compose build backend`).
