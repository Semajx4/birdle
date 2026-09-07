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
   Default: `127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` —
   i.e. only something on the same host/LAN (or another container) can reach it.
   Set it to an empty string to disable the check (dev only).

> If you run the app behind a reverse proxy that forwards every path, the peer
> address is always the proxy, so the allowlist can't distinguish callers — keep
> the proxy from forwarding `/internal/` and rely on the token, or don't proxy
> that prefix at all.

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
  `.env` file next to `start.sh`.
* For GeoIP, download the free MaxMind **GeoLite2 Country** database (account
  required) and put it next to `start.sh` — either the loose
  `GeoLite2-Country.mmdb` or the extracted `GeoLite2-Country_YYYYMMDD/`
  directory as-is. `start.sh` finds it (newest release wins), mounts it
  read-only into the container, and sets `GEOIP_DB_PATH` automatically. Without
  it, `country` stays `NULL` and everything else still works. (`docker compose`
  dev: set `GEOIP_DB_PATH` yourself and add a matching volume mount.)
* `geoip2` is in `requirements.txt`; rebuild the image after pulling this change
  (`./start.sh`, or `docker compose build backend`).
