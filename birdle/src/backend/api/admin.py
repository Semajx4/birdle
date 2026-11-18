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
from sqlalchemy.orm import selectinload

from models.models import Bird, DailyPick, SessionLocal
from services.game import AUDIO_DIR, IMAGE_DIR, bird_for_date, game_today


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


def _get_bird(bird_id: str) -> Bird:
    db = SessionLocal()
    try:
        bird = (
            db.query(Bird)
            .options(selectinload(Bird.media))
            .filter(Bird.id == bird_id)
            .first()
        )
    finally:
        db.close()
    if bird is None:
        raise HTTPException(status_code=404, detail="unknown bird")
    return bird


def _media_file(base, name: str | None):
    """Resolve a stored media filename inside its directory (no traversal)."""
    if not name:
        return None
    base = base.resolve()
    path = (base / name).resolve()
    if base not in path.parents or not path.is_file():
        return None
    return path


def _media_json(m, base):
    return {
        "id": m.id,
        "kind": m.kind,
        "filename": m.filename,
        "source": m.source,
        "source_ref": m.source_ref,
        "credit": m.credit,
        "licence": m.licence,
        "country": m.country,
        "location": m.location,
        "recorded_on": m.recorded_on,
        "quality": m.quality,
        "enabled": bool(m.enabled),
        "file_present": _media_file(base, m.filename) is not None,
    }


@api_router.get("/bird/{bird_id}")
def bird_detail(bird_id: str):
    b = _get_bird(bird_id)
    audio, image = b.primary("audio"), b.primary("image")
    hist = _history_by_bird().get(str(b.id))
    return {
        "bird_id": b.id,
        "common_name": b.common_name,
        "scientific_name": b.scientific_name,
        "genus": b.genus,
        "species": b.species,
        "family": b.family,
        "order": b.order,
        # Recording details come from the primary recording.
        "country": audio.country if audio else None,
        "location": audio.location if audio else None,
        "recorded_on": audio.recorded_on if audio else None,
        "quality": audio.quality if audio else None,
        "ebird_species_code": b.ebird_species_code,
        "enabled": bool(b.enabled),
        "notes": b.notes,
        "has_audio": bool(audio and _media_file(AUDIO_DIR, audio.filename)),
        "has_image": bool(image and _media_file(IMAGE_DIR, image.filename)),
        "media": [_media_json(m, AUDIO_DIR if m.kind == "audio" else IMAGE_DIR) for m in b.media],
        "history": hist,
    }


def _primary_file(bird_id: str, kind: str):
    m = _get_bird(bird_id).primary(kind)
    return _media_file(AUDIO_DIR if kind == "audio" else IMAGE_DIR, m.filename) if m else None


@api_router.get("/bird/{bird_id}/audio")
def bird_audio(bird_id: str):
    path = _primary_file(bird_id, "audio")
    if path is None:
        raise HTTPException(status_code=404, detail="no audio for this bird")
    return FileResponse(path, media_type="audio/mpeg", headers=_PRIVATE_CACHE)


@api_router.get("/bird/{bird_id}/image")
def bird_image(bird_id: str):
    path = _primary_file(bird_id, "image")
    if path is None:
        raise HTTPException(status_code=404, detail="no image for this bird")
    media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return FileResponse(path, media_type=media_type, headers=_PRIVATE_CACHE)


@api_router.get("/upcoming")
def upcoming(days: int = Query(default=14, ge=1, le=60)):
    """The next daily picks, starting today (NZ). Days already served are
    pinned; later days use the deterministic pick, which shifts if birds are
    added or removed (disabling one only moves that bird's own days)."""
    hist = _history_by_bird()
    today = game_today()
    db = SessionLocal()
    try:
        pinned = {p.game_date for p in db.query(DailyPick.game_date).filter(DailyPick.game_date >= today.isoformat())}
    finally:
        db.close()
    out = []
    for i in range(days):
        day = today + timedelta(days=i)
        b = bird_for_date(day)
        h = hist.get(str(b.id)) or {}
        prior = [d for d in h.get("dates", []) if d < day.isoformat()]
        out.append(
            {
                "date": day.isoformat(),
                "pinned": day.isoformat() in pinned,
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
