import random
import uuid
from pathlib import Path

from datetime import datetime
from fastapi.responses import FileResponse, StreamingResponse

from models.models import SessionLocal, BirdRecording
from schemas import GuessResponse, Hints, FullBird, RoundState

from PIL import Image, ImageFilter
from io import BytesIO

blur_cache = {}



AUDIO_DIR = Path("datasets/audio")
IMAGE_DIR = Path("datasets/bird_images")
MAX_GUESSES = 5


daily_cache = {
        "bird": None,
        "date": None,
        }

active_rounds = {}

bird_cache = None


def get_bird_by_id(id: str):
    db = SessionLocal()

    try:
        return (
                db.query(BirdRecording)
                .filter(BirdRecording.id == id)
                .first()
                )

    finally:
        db.close()


def get_birds_for_game():
    global bird_cache

    if bird_cache is not None:
        return bird_cache

    db = SessionLocal()

    try:
        records = db.query(BirdRecording).all()

        bird_cache = [FullBird.from_orm_record(r) for r in records]

        return bird_cache

    finally:
        db.close()


def get_all_birds():
    return [b.to_public() for b in get_birds_for_game()]

def pick_bird_for_date(birds, day):
    # Deterministic per-day pick: seed a shuffle with the date so every
    # worker/process derives the same bird independently, without needing
    # to share cache state.
    shuffled = birds[:]
    random.Random(day.isoformat()).shuffle(shuffled)
    return shuffled[0]


def get_random_bird():
    today = datetime.utcnow().date()

    # If cached for today, reuse it
    if daily_cache["bird"] is not None and daily_cache["date"] == today:
        return daily_cache["bird"]

    # Otherwise (re)derive deterministically from the date
    birds = get_birds_for_game()
    bird = pick_bird_for_date(birds, today)

    daily_cache["bird"] = bird
    daily_cache["date"] = today

    return bird

def create_round():
    bird = get_random_bird()

    round_id = str(uuid.uuid4())

    active_rounds[round_id] = RoundState(bird)        
    return {
            "round_id": round_id,
            }


def resolve_audio_path(round_id: str):
    round_state = active_rounds.get(round_id)

    if not round_state:
        return {"error": "invalid round"}

    bird = round_state.bird

    path = AUDIO_DIR / bird.audio_path
    print(path)
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

    return GuessResponse(
            correct=correct,
            hints=Hints(order=order, family=family, genus=genus),
            finished=finished
            )


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
