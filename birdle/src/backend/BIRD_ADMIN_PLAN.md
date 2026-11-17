# Bird management — plan & notes

Status: **not started** (notes written 2026-11-02). This file collects the
context needed to pick the work back up.

## Goals

1. **Admin interface.** An access-gated endpoint + web UI to browse every bird
   in the DB, add new birds and edit existing ones. Today adding or updating
   birds is awkward (see *Current state*), and this is meant to fix that.
2. **Own media.** Upload my own recordings and photos where I have them,
   alongside the ones sourced from xeno-canto / Macaulay.
3. **Multiple examples per bird.** Several images and recordings per bird, so a
   repeated daily bird doesn't mean a repeated puzzle.

Explicitly **not** a goal for now: preventing the same bird coming up close
together (see *Daily bird selection*).

## Current state

### Data model

`models/models.py` has a single table, `bird_recordings` (`BirdRecording`):
one row per **recording**, with species info repeated on every row.

| column | notes |
|---|---|
| `id` | primary key; the recording id (e.g. `925263`), also used as the bird id in game + analytics |
| `common_name`, `genus`, `order`, `family`, `species` | taxonomy, used for guess hints |
| `country`, `location`, `date`, `quality` | recording metadata |
| `audio_path` | relative to `datasets/audio/` |
| `image_path` | relative to `datasets/bird_images/` |
| `ebird_species_code` | used to look up a photo on Macaulay |

There is one audio file and one image per row, and nowhere to record
attribution or whether the media is mine.

### How birds get in today

- `util/bird_api_fetcher.py` queries the xeno-canto v3 API (`XENO_API_KEY`)
  for NZ recordings, downloads the mp3s and saves rows.
- `util/bird_image_fetcher.py` scrapes a photo from Macaulay Library
  (media.ebird.org) with Playwright, using `ebird_species_code`.
- `fix_bird_audio.py` is a one-off migration script for audio file names.
- These scripts' imports look stale (e.g. `from bird_recording import ...`,
  `from models import save_to_db`, `from src.backend import models`), so they
  probably need fixing before they'll run again.

### Where the data lives (important)

- `birds.db` (SQLite, `sqlite:///birds.db` relative to the working directory)
  is **committed to git**.
- `datasets/audio/*.mp3` and `datasets/bird_images/*.jpg` are **git-ignored**
  (`*.mp3` / `*.jpg`), so they only exist on the deploy machine.
- `Dockerfile.prod` does `COPY birdle/src/backend/ .`, which **bakes `birds.db`
  and `datasets/` into the image**.
- Only `/app/data` is persistent (the `birdle-data` volume, which holds
  `analytics.db` and the IP salt).

So anything an admin UI writes to `birds.db` or `datasets/` inside the
container would be **wiped on the next `start.sh` rebuild**.

### Caching

- `services/game.py` keeps `bird_cache`, the full bird list loaded once per
  process and never refreshed. Edits won't show up until a restart unless this
  is invalidated.
- `daily_cache` holds today's bird.

### Daily bird selection

`pick_bird_for_date()` in `services/game.py` shuffles the **whole bird list**
with `random.Random(date.isoformat())` and takes element 0. The day rolls
over at midnight NZ time (`GAME_TZ = Pacific/Auckland`).

Consequences:
- Each day is independent, so repeats happen (89 birds; e.g. `110970` was the
  bird on both 2026-10-22 and 2026-10-29, and there are about 55 repeats between
  7 Sep and 4 Jan). This is **accepted for now**.
- The result depends on the list's order and contents. `get_birds_for_game()`
  queries with **no `order_by`**, so **adding or removing a bird changes the
  pick for every day, including today's**. This matters as soon as birds can
  be edited live.

## Proposed plan

### 1. Move bird data onto the persistent volume

- Store the bird DB and media under `/app/data` (e.g. `/app/data/birds.db`,
  `/app/data/media/...`), configurable by env var like `GEOIP_DB_PATH`.
- On first start, if they're missing, seed them from the copies baked into the
  image.
- Decide whether `birds.db` stays in git as the seed or gets exported some
  other way (e.g. a CSV/JSON dump) for backups.
- Backups: the volume becomes the source of truth for bird data, so it needs
  backing up.

### 2. Make the daily pick stable when the bird list changes

Do this before birds can be added or removed live. Options:
- **Record each day's pick** once it's made (a `daily_bird` table keyed by
  date). Past days stay fixed, and today stays fixed once anyone has played.
- At minimum add `order_by(id)` to the query, but that still reshuffles every
  day whenever the list changes.
- If repeats ever start to matter: a "shuffle bag" (days since a fixed epoch,
  split into cycles the size of the bird list; seed one shuffle per cycle)
  gives each bird once per cycle. It's deterministic, needs no shared state,
  and could be combined with the table above. Pick the start date so the day
  it's deployed keeps its current bird, or deploy just before NZ midnight.

### 3. Split the schema: birds and media

Something like:

- `birds`: one row per species. Stable id (could be the eBird species code),
  common/scientific name, order, family, genus, enabled flag.
- `media`: many rows per bird. `bird_id`, `kind` (audio/image), file path,
  `source` (`own` / `xeno-canto` / `macaulay` / ...), source id/URL,
  author/credit, licence, recorded date/location, quality, enabled flag.

Then the daily pick chooses a **bird** and uses a date seed to choose one
**audio** and one **image** of that bird. That's what makes repeated birds
feel different.

Migration: build `birds` from the distinct species in `bird_recordings` and
turn each existing row into one audio + one image `media` row. Check what
references the old ids:
- Analytics `RoundStat.bird_id` (keep the old recording id or map it).
- The frontend's guess list / `get_all_birds()` and `check_guess` (guesses
  compare `id`).
- Saved progress in the browser (`lib/progress.ts`), which may store ids.

### 4. Admin API + UI

- Mount under `/internal/...` and reuse the guard from `api/stats.py`
  (`STATS_TOKEN`-style shared secret + `STATS_ALLOWED_NETWORKS` IP allowlist,
  using `CF-Connecting-IP` when present). Possibly a separate `ADMIN_TOKEN`.
- Keep the Cloudflare Tunnel ingress from routing `/internal/*` (as described
  in `ANALYTICS.md`). Reach it via `localhost:8000` on the host, or an SSH
  tunnel / Cloudflare Access if remote access is wanted.
- Features:
  - Browse/search birds with their media (play audio, view image).
  - Add or edit a bird's taxonomy and names.
  - Upload media (mp3 / jpg). Validate the type and size; maybe transcode or
    resize and enforce the existing "under one minute" audio rule
    (`util/utils.py: is_under_one_minute`).
  - Mark media as own vs sourced, and set credit/licence.
  - Enable/disable a bird or a single media item without deleting it.
  - Optionally: import from xeno-canto by recording id (reusing the fetcher
    logic) and pull a Macaulay photo by species code.
- After any write, invalidate `bird_cache` (and `blur_cache` entries for
  replaced images).
- Never let an edit change **today's** bird mid-day (see step 2).

### 5. Stats page (same admin UI)

Requested 2026-11-18: a stats page in the admin UI, showing the same views
that were put together by hand from the `/internal/stats` API:

- **Summary tiles:** rounds started, distinct players, finished %, wins /
  losses / win rate, average guesses in finished rounds (also for wins only).
- **Week view (Mon–Sun, NZ time):** totals for the selected week, with
  previous/next week navigation and a comparison to the week before.
- **Daily round history table:** one row per day, showing the date, the bird
  (common + scientific name, joined from `birds.db` by `bird_id`), rounds,
  finished and wins. Clicking a day shows its individual rounds (guesses,
  won/lost/unfinished, country, device).
- **Per-bird difficulty:** win rate and average guesses per bird across every
  day it has appeared, to spot birds that are too hard (e.g. Atiu Swiftlet:
  0 wins, recorded in the Cook Islands).
- **Breakdowns:** country, device (iOS / Android / other), referrer.

Notes:
- Most of this can come from the existing `/summary`, `/daily`, `/countries`
  and `/rounds` endpoints. Add a date-range filter (`/daily` currently seems
  to ignore `days=`) and a per-bird endpoint, or do the aggregation in SQL.
- Bird names need a join between `analytics.db` (`RoundStat.bird_id`) and
  `birds.db`. Keep that working through the step 3 id migration.

## Open questions

- Should the guess list contain every bird in the DB, or only enabled ones?
- Attribution: does the game need to show credits for sourced media (licence
  terms of xeno-canto / Macaulay recordings and photos)?
- Is SQLite fine for concurrent admin writes and game reads? (Probably yes at
  this traffic level; WAL mode would help.)
- Where should uploaded originals vs processed (resized/trimmed) files live?
