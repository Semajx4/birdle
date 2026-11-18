"""Internal admin UI (served on ADMIN_HOSTNAME behind Cloudflare Access).

The page is a single self-contained HTML file in ``admin_ui/`` — no build
step, and it is not part of the public frontend bundle. It is guarded by the
same Cloudflare check as the stats API, so off the admin hostname it 404s.
"""

from pathlib import Path

import mimetypes
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse

from api.stats import _check_access, birds as bird_stats, came_via_cloudflare, require_access
from models.models import BirdRecording, SessionLocal
from services.game import AUDIO_DIR, IMAGE_DIR, game_today, get_birds_for_game, pick_bird_for_date


def page_access(request: Request) -> None:
    """The page itself holds no data (it fetches /internal/stats, which is
    fully guarded). Through Cloudflare it still needs the admin hostname +
    Access JWT; a direct local request gets the page so it can ask for the
    stats token."""
    if came_via_cloudflare(request):
        _check_access(request, None, None)


router = APIRouter(dependencies=[Depends(page_access)])

_UI_DIR = Path(__file__).resolve().parent.parent / "admin_ui"
_NO_STORE = {"Cache-Control": "no-store"}


@router.get("", include_in_schema=False)
def admin_root():
    return RedirectResponse(url="/internal/admin/", status_code=307)


@router.get("/", include_in_schema=False)
def admin_index():
    return FileResponse(_UI_DIR / "index.html", media_type="text/html", headers=_NO_STORE)


# ---------------------------------------------------------------------------
# Admin data API (fully guarded: Access JWT via Cloudflare, token locally)
# ---------------------------------------------------------------------------

api_router = APIRouter(dependencies=[Depends(require_access)])

_PRIVATE_CACHE = {"Cache-Control": "private, max-age=3600"}


def _history_by_bird() -> dict:
    """bird_id -> all-time play stats (dates, rounds, finished, wins, ...)."""
    return {str(b["bird_id"]): b for b in bird_stats(start=None, end=None)}


def _get_record(bird_id: str) -> BirdRecording:
    db = SessionLocal()
    try:
        rec = db.query(BirdRecording).filter(BirdRecording.id == bird_id).first()
    finally:
        db.close()
    if rec is None:
        raise HTTPException(status_code=404, detail="unknown bird")
    return rec


def _media_file(base, name: str | None):
    """Resolve a stored media filename inside its directory (no traversal)."""
    if not name:
        return None
    base = base.resolve()
    path = (base / name).resolve()
    if base not in path.parents or not path.is_file():
        return None
    return path


@api_router.get("/bird/{bird_id}")
def bird_detail(bird_id: str):
    r = _get_record(bird_id)
    hist = _history_by_bird().get(str(r.id))
    return {
        "bird_id": r.id,
        "common_name": r.common_name,
        "scientific_name": " ".join(p for p in (r.genus, r.species) if p) or None,
        "genus": r.genus,
        "species": r.species,
        "family": r.family,
        "order": r.order,
        "country": r.country,
        "location": r.location,
        "recorded_on": r.date,
        "quality": r.quality,
        "ebird_species_code": r.ebird_species_code,
        "enabled": r.enabled is not False,
        "has_audio": _media_file(AUDIO_DIR, r.audio_path) is not None,
        "has_image": _media_file(IMAGE_DIR, r.image_path) is not None,
        "history": hist,
    }


@api_router.get("/bird/{bird_id}/audio")
def bird_audio(bird_id: str):
    path = _media_file(AUDIO_DIR, _get_record(bird_id).audio_path)
    if path is None:
        raise HTTPException(status_code=404, detail="no audio for this bird")
    return FileResponse(path, media_type="audio/mpeg", headers=_PRIVATE_CACHE)


@api_router.get("/bird/{bird_id}/image")
def bird_image(bird_id: str):
    path = _media_file(IMAGE_DIR, _get_record(bird_id).image_path)
    if path is None:
        raise HTTPException(status_code=404, detail="no image for this bird")
    media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return FileResponse(path, media_type=media_type, headers=_PRIVATE_CACHE)


@api_router.get("/upcoming")
def upcoming(days: int = Query(default=14, ge=1, le=60)):
    """The next daily picks, starting today (NZ), from the same deterministic
    pick the game uses. Only valid while the bird list stays unchanged:
    adding/removing birds reshuffles every future (and past) day."""
    birds = get_birds_for_game()
    hist = _history_by_bird()
    today = game_today()
    out = []
    for i in range(days):
        day = today + timedelta(days=i)
        b = pick_bird_for_date(birds, day)
        h = hist.get(str(b.id)) or {}
        prior = [d for d in h.get("dates", []) if d < day.isoformat()]
        out.append(
            {
                "date": day.isoformat(),
                "bird_id": b.id,
                "common_name": b.common_name,
                "scientific_name": b.scientific_name,
                "times_picked_before": len(prior),
                "last_picked": prior[0] if prior else None,
                "all_time_finished": h.get("finished", 0),
                "all_time_wins": h.get("wins", 0),
                "all_time_win_rate": h.get("win_rate"),
            }
        )
    return out
