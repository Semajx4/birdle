import logging
import os
import random
import threading
import uuid
from pathlib import Path

from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from models.models import Bird, DailyPick, Media, SessionLocal
from schemas import GuessResponse, Hints, FullBird, RoundState
from services.analytics import record_round_started, record_round_finished, record_guess

from PIL import Image, ImageFilter
from io import BytesIO

logger = logging.getLogger("birdle.game")

blur_cache = {}


# Media files live under MEDIA_ROOT (a persistent volume in production).
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "datasets"))
AUDIO_DIR = MEDIA_ROOT / "audio"
IMAGE_DIR = MEDIA_ROOT / "bird_images"
MAX_GUESSES = 5


daily_cache = {
        "bird": None,
        "date": None,
        }

active_rounds = {}

# Ordered list of every bird (enabled or not), as FullBird, by pick_order.
bird_cache = None
_cache_lock = threading.Lock()


def invalidate_bird_cache():
    """Call after any edit to birds/media so the game picks it up. Today's
    bird is pinned in daily_picks, so it is not affected by edits."""
    global bird_cache
    with _cache_lock:
        bird_cache = None
        daily_cache["bird"] = None
        daily_cache["date"] = None
    blur_cache.clear()


def _load_birds():
    db = SessionLocal()
    try:
        rows = (
            db.query(Bird)
            .options(selectinload(Bird.media))
            .order_by(Bird.pick_order)
            .all()
        )
        return [FullBird.from_bird(b) for b in rows]
    finally:
        db.close()


def get_birds_for_game():
    global bird_cache
    birds = bird_cache
    if birds is not None:
        return birds
    with _cache_lock:
        if bird_cache is None:
            bird_cache = _load_birds()
        return bird_cache


def get_bird_by_id(id: str):
    for b in get_birds_for_game():
        if b.id == id:
            return b
    return None


def get_all_birds():
    """The guess list: enabled birds only."""
    return [b.to_public() for b in get_birds_for_game() if b.enabled]


def _pickable(bird) -> bool:
    return bool(bird.enabled and bird.audio_path)


def pick_bird_for_date(birds, day):
    # Deterministic per-day pick: seed a shuffle with the date so every
    # worker/process derives the same bird independently, without needing
    # to share cache state.
    #
    # The shuffle is over ALL birds in pick_order (disabled included) and the
    # first enabled one with a recording wins. Disabling a bird therefore
    # only changes the days it would have been picked (they fall to the next
    # bird in that day's shuffle); every other day keeps its bird. Adding or
    # deleting birds changes the list, which reshuffles future days, but days
    # already served are pinned in daily_picks.
    shuffled = birds[:]
    random.Random(day.isoformat()).shuffle(shuffled)
    for bird in shuffled:
        if _pickable(bird):
            return bird
    raise RuntimeError("no enabled birds to pick from")


# The daily bird rolls over at midnight New Zealand time. The frontend's
# todayKey() (lib/progress.ts) must use the same zone.
GAME_TZ = ZoneInfo("Pacific/Auckland")


def game_today():
    return datetime.now(GAME_TZ).date()


def _pinned_bird(db, day_key: str):
    """FullBird for a pinned day (with the media it was served with), or None."""
    pick = db.get(DailyPick, day_key)
    if pick is None:
        return None
    bird = (
        db.query(Bird).options(selectinload(Bird.media)).filter(Bird.id == pick.bird_id).first()
    )
    if bird is None:
        return None
    audio = db.get(Media, pick.audio_media_id) if pick.audio_media_id else None
    image = db.get(Media, pick.image_media_id) if pick.image_media_id else None
    return FullBird.from_bird(bird, audio=audio, image=image)


def bird_for_date(day: date, pin: bool = False):
    """The bird for a game day: the pinned one if the day has been served,
    otherwise the deterministic pick. With ``pin=True`` an unpinned day is
    pinned (used when a round actually starts)."""
    key = day.isoformat()
    db = SessionLocal()
    try:
        pinned = _pinned_bird(db, key)
        if pinned is not None:
            return pinned

        bird = pick_bird_for_date(get_birds_for_game(), day)
        if pin:
            db.add(DailyPick(
                game_date=key,
                bird_id=bird.id,
                audio_media_id=bird.audio_media_id,
                image_media_id=bird.image_media_id,
                source="served",
            ))
            try:
                db.commit()
                logger.info("pinned daily bird %s for %s", bird.id, key)
            except IntegrityError:
                # Another request pinned it first; use theirs.
                db.rollback()
                return _pinned_bird(db, key) or bird
        return bird
    finally:
        db.close()


def get_random_bird():
    today = game_today()

    # If cached for today, reuse it
    if daily_cache["bird"] is not None and daily_cache["date"] == today:
        return daily_cache["bird"]

    bird = bird_for_date(today, pin=True)

    daily_cache["bird"] = bird
    daily_cache["date"] = today

    return bird

def create_round(request=None, referrer=None):
    bird = get_random_bird()

    round_id = str(uuid.uuid4())

    active_rounds[round_id] = RoundState(bird)

    if request is not None:
        game_date = game_today().isoformat()
        record_round_started(round_id, bird.id, game_date, request, referrer)

    return {
            "round_id": round_id,
            }


def resolve_audio_path(round_id: str):
    round_state = active_rounds.get(round_id)

    if not round_state:
        return {"error": "invalid round"}

    bird = round_state.bird

    if not bird.audio_path:
        return {"error": "no audio"}
    path = AUDIO_DIR / bird.audio_path
    return FileResponse(path, media_type="audio/mpeg")

def blur_for_stage(stage: int) -> int:
    if stage >= MAX_GUESSES:
        return 0

    return (MAX_GUESSES - stage) * 3

def get_blurred_image(path: str, blur_radius: int):
    key = (path, blur_radius)

    if key in blur_cache:
        return blur_cache[key]

    img = Image.open(path)

    if blur_radius > 0:
        img = img.filter(ImageFilter.GaussianBlur(blur_radius))

    buf = BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    data = buf.getvalue()
    blur_cache[key] = data

    return data

def resolve_image_path(round_id: str):
    round_state = active_rounds.get(round_id)

    if not round_state:
        return {"error": "invalid round"}

    bird = round_state.bird

    stage = MAX_GUESSES if round_state.won else min(round_state.guesses, MAX_GUESSES)
    blur_radius = blur_for_stage(stage)

    if not bird.image_path:
        return {"error": "no image"}
    path = IMAGE_DIR / bird.image_path

    img_bytes = get_blurred_image(str(path), blur_radius)

    return StreamingResponse(
           BytesIO(img_bytes),
           media_type="image/jpeg"
           )

def check_guess(req):
    round_state = active_rounds.get(req.round_id)

    if not round_state:
        return {"error": "invalid round"}

    if round_state.guesses >= MAX_GUESSES:
        return {"error": "max guesses reached"}

    guess_bird = get_bird_by_id(req.guess_id)
    if not guess_bird:
        return {"error": "invalid bird"}

    correct = guess_bird.id == round_state.bird.id

    order = guess_bird.order == round_state.bird.order
    family = guess_bird.family == round_state.bird.family
    genus = guess_bird.genus == round_state.bird.genus

    # increment FIRST, but treat it as authoritative
    round_state.guesses += 1

    finished = correct or round_state.guesses >= MAX_GUESSES

    if finished:
        round_state.finished = True
        round_state.reveal_ready = True  # important: separate from deletion

    if correct:
        round_state.won = True

    if finished:
        record_round_finished(req.round_id, round_state.guesses, round_state.won)
    else:
        record_guess(req.round_id, round_state.guesses)

    return GuessResponse(
            correct=correct,
            hints=Hints(order=order, family=family, genus=genus),
            finished=finished
            )


def get_round_status(round_id: str):
    round_state = active_rounds.get(round_id)

    if not round_state:
        return {"error": "invalid round"}

    return {
            "guesses": round_state.guesses,
            "finished": round_state.finished,
            "won": round_state.won,
            }


def get_answer_if_game_over(round_id: str):
    round_state = active_rounds.get(round_id)

    if not round_state:
        return {"error": "invalid round"}

    if not getattr(round_state, "finished", False):
        return {"error": "Game not finished"}

    bird = round_state.bird
    return {
            "id": bird.id,
            "common_name": bird.common_name,
            "scientific_name": bird.scientific_name,
            "order": bird.order,
            "family": bird.family,
            "genus": bird.genus,
            }
