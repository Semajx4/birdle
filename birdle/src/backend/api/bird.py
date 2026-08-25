from fastapi import APIRouter
from services.game import create_round, get_all_birds, check_guess, resolve_audio_path, resolve_image_path, get_answer_if_game_over, get_round_status
from schemas import GuessRequest

router = APIRouter()

@router.get("/start")
def random_bird():
    return create_round()

@router.get("/audio/{round_id}")
def read_audio(round_id: str):
    return resolve_audio_path(round_id)

@router.get("/image/{round_id}")
def read_image(round_id: str):
    return resolve_image_path(round_id)

@router.get("/all")
def get_birds():
    return get_all_birds()

@router.get("/reveal/{round_id}")
def get_anwer(round_id: str):
    return get_answer_if_game_over(round_id)

@router.get("/status/{round_id}")
def round_status(round_id: str):
    return get_round_status(round_id)

@router.post("/guess")
def guess(req: GuessRequest):
    return check_guess(req)
