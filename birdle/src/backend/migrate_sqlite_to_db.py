"""One-off migration: old SQLite files -> the main database (DATABASE_URL).

Copies
  birds.db      bird_recordings  -> birds (+ one audio and one image media row each)
  analytics.db  round_stats      -> round_stats
and backfills daily_picks from the bird each past game day was played with.

pick_order follows the old table's rowid order, which is the order the old
code shuffled, so the daily schedule is unchanged.

Usage (inside the app container, DATABASE_URL set):
  python migrate_sqlite_to_db.py --birds-db birds.db --analytics-db data/analytics.db
Refuses to run if the target already has birds unless --replace is given
(which deletes birds, media, daily_picks and round_stats first).
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from db import DATABASE_URL, SessionLocal, init_db
from models.analytics import RoundStat
from models.models import Bird, DailyPick, Media


def _ts(value):
    """Old SQLite timestamps are naive UTC strings."""
    if not value:
        return None
    dt = datetime.fromisoformat(str(value))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _bool(value):
    return bool(int(value)) if value is not None else False


def copy_birds(db, src_b):
    """Copy legacy bird_recordings rows into birds + media (no commit).
    Returns (rows, {bird_id: (audio Media, image Media)})."""
    cols = {r[1] for r in src_b.execute("PRAGMA table_info(bird_recordings)")}
    rows = src_b.execute("SELECT rowid AS _rowid, * FROM bird_recordings ORDER BY rowid").fetchall()
    media_by_bird = {}
    for pos, r in enumerate(rows):
        bird = Bird(
            id=str(r["id"]),
            common_name=r["common_name"] or "Unknown",
            genus=r["genus"],
            species=r["species"],
            family=r["family"],
            order=r["order"],
            ebird_species_code=r["ebird_species_code"],
            enabled=_bool(r["enabled"]) if "enabled" in cols else True,
            pick_order=pos,
        )
        db.add(bird)
        audio = image = None
        if r["audio_path"]:
            audio = Media(
                bird=bird, kind="audio", filename=r["audio_path"],
                source="xeno-canto", source_ref=str(r["id"]),
                country=r["country"], location=r["location"],
                recorded_on=r["date"], quality=r["quality"], position=0,
            )
            db.add(audio)
        if r["image_path"]:
            image = Media(bird=bird, kind="image", filename=r["image_path"], source="macaulay", position=0)
            db.add(image)
        media_by_bird[bird.id] = (audio, image)
    db.flush()   # assign media ids
    return rows, media_by_bird


def seed_birds_if_empty(legacy_path="birds.db") -> bool:
    """Dev convenience: if the birds table is empty and the committed legacy
    birds.db exists, copy its birds in. Returns True if it seeded."""
    import logging
    from pathlib import Path

    if not Path(legacy_path).is_file():
        return False
    db = SessionLocal()
    try:
        if db.scalar(select(func.count()).select_from(Bird)):
            return False
        src = sqlite3.connect(legacy_path)
        src.row_factory = sqlite3.Row
        try:
            rows, _ = copy_birds(db, src)
        finally:
            src.close()
        db.commit()
        logging.getLogger("birdle.db").warning("seeded %d birds from %s (birds table was empty)", len(rows), legacy_path)
        return True
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--birds-db", required=True)
    ap.add_argument("--analytics-db", required=True)
    ap.add_argument("--replace", action="store_true")
    args = ap.parse_args()

    print(f"target: {DATABASE_URL.split('@')[-1]}")
    init_db()

    src_b = sqlite3.connect(args.birds_db)
    src_b.row_factory = sqlite3.Row
    src_a = sqlite3.connect(args.analytics_db)
    src_a.row_factory = sqlite3.Row

    db = SessionLocal()
    try:
        existing = db.scalar(select(func.count()).select_from(Bird))
        if existing and not args.replace:
            sys.exit(f"target already has {existing} birds; use --replace to overwrite")
        if args.replace:
            for model in (DailyPick, Media, RoundStat, Bird):
                db.execute(delete(model))
            db.flush()

        rows, media_by_bird = copy_birds(db, src_b)

        # --- round_stats ---------------------------------------------------
        n_rounds = 0
        for r in src_a.execute("SELECT * FROM round_stats"):
            keys = r.keys()
            db.add(RoundStat(
                round_id=r["round_id"],
                game_date=r["game_date"],
                bird_id=r["bird_id"],
                ip_hash=r["ip_hash"],
                country=r["country"],
                user_agent=r["user_agent"],
                referrer=r["referrer"] if "referrer" in keys else None,
                guesses=r["guesses"],
                won=_bool(r["won"]),
                finished=_bool(r["finished"]),
                started_at=_ts(r["started_at"]),
                finished_at=_ts(r["finished_at"]),
            ))
            n_rounds += 1

        # --- daily_picks backfill -----------------------------------------
        n_picks, skipped = 0, []
        for game_date, bird_id in src_a.execute(
            "SELECT game_date, MIN(bird_id) FROM round_stats WHERE game_date IS NOT NULL GROUP BY game_date"
        ):
            if bird_id not in media_by_bird:
                skipped.append((game_date, bird_id))
                continue
            audio, image = media_by_bird[bird_id]
            db.add(DailyPick(
                game_date=game_date, bird_id=bird_id,
                audio_media_id=audio.id if audio else None,
                image_media_id=image.id if image else None,
                source="backfill",
            ))
            n_picks += 1

        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()

    n_media = sum((a is not None) + (i is not None) for a, i in media_by_bird.values())
    print(f"birds: {len(rows)}  media: {n_media}  round_stats: {n_rounds}  daily_picks: {n_picks}")
    if skipped:
        print(f"skipped daily_picks for unknown birds: {skipped}")


if __name__ == "__main__":
    main()
