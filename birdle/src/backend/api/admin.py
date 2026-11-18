"""Internal admin UI (served on ADMIN_HOSTNAME behind Cloudflare Access).

The page is a single self-contained HTML file in ``admin_ui/`` — no build
step, and it is not part of the public frontend bundle. It is guarded by the
same Cloudflare check as the stats API, so off the admin hostname it 404s.
"""

import logging
import mimetypes
import shutil
import subprocess
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import distinct, func
from sqlalchemy.orm import selectinload

from api.stats import StartQ, EndQ, _check_access, _in_range, birds as bird_stats, came_via_cloudflare, require_access
from models.models import Bird, DailyPick, GeocodeCache, Media, SessionLocal
from models.analytics import RoundStat
from services import geocode
from services.game import AUDIO_DIR, IMAGE_DIR, bird_for_date, game_today, invalidate_bird_cache

log = logging.getLogger("birdle.admin")


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


_VENDOR_DIR = (_UI_DIR / "vendor").resolve()


@router.get("/vendor/{path:path}", include_in_schema=False)
def admin_vendor(path: str):
    """Third-party files bundled with the admin page (Leaflet), served from
    here rather than a CDN."""
    f = (_VENDOR_DIR / path).resolve()
    if _VENDOR_DIR not in f.parents or not f.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(f, headers={"Cache-Control": "public, max-age=86400"})


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
        "added": m.created_at.isoformat() if m.created_at else None,
    }


@api_router.get("/bird/{bird_id}")
def bird_detail(bird_id: str):
    b = _get_bird(bird_id)
    audio, image = b.primary("audio"), b.primary("image")
    hist = _history_by_bird().get(str(b.id))
    db = SessionLocal()
    try:
        todays = db.get(DailyPick, game_today().isoformat())
    finally:
        db.close()
    return {
        "bird_id": b.id,
        "is_today": bool(todays and todays.bird_id == b.id),
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


# ---------------------------------------------------------------------------
# Bird editor
# ---------------------------------------------------------------------------

def _dir_for(kind: str):
    return AUDIO_DIR if kind == "audio" else IMAGE_DIR


@api_router.get("/birds")
def list_birds():
    """Every bird (enabled or not) with what the editor list needs."""
    hist = _history_by_bird()
    today = game_today().isoformat()
    db = SessionLocal()
    try:
        rows = db.query(Bird).options(selectinload(Bird.media)).order_by(Bird.common_name).all()
        todays = db.get(DailyPick, today)
    finally:
        db.close()
    out = []
    for b in rows:
        audio, image = b.primary("audio"), b.primary("image")
        h = hist.get(str(b.id)) or {}
        out.append({
            "bird_id": b.id,
            "common_name": b.common_name,
            "scientific_name": b.scientific_name,
            "genus": b.genus,
            "species": b.species,
            "family": b.family,
            "order": b.order,
            "enabled": bool(b.enabled),
            "notes": b.notes,
            "country": audio.country if audio else None,
            "location": audio.location if audio else None,
            "has_audio": bool(audio and _media_file(AUDIO_DIR, audio.filename)),
            "has_image": bool(image and _media_file(IMAGE_DIR, image.filename)),
            "audio_media_id": audio.id if audio else None,
            "media_count": len(b.media),
            "times_picked": len(h.get("dates", [])),
            "last_picked": (h.get("dates") or [None])[0],
            "finished": h.get("finished", 0),
            "wins": h.get("wins", 0),
            "win_rate": h.get("win_rate"),
            "is_today": bool(todays and todays.bird_id == b.id),
            "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        })
    return out


class BirdPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


@api_router.patch("/bird/{bird_id}")
def update_bird(bird_id: str, patch: BirdPatch):
    """Switch a bird on/off for daily picks and the guess list."""
    db = SessionLocal()
    try:
        bird = db.get(Bird, bird_id)
        if bird is None:
            raise HTTPException(status_code=404, detail="unknown bird")
        if not patch.enabled:
            others = db.query(Bird).filter(Bird.enabled.is_(True), Bird.id != bird_id).count()
            if others == 0:
                raise HTTPException(status_code=409, detail="can't disable the last enabled bird")
        changed = bool(bird.enabled) != patch.enabled
        bird.enabled = patch.enabled
        db.commit()
    finally:
        db.close()
    if changed:
        log.info("bird %s %s", bird_id, "enabled" if patch.enabled else "disabled")
        invalidate_bird_cache()
    return bird_detail(bird_id)


# --- uploads -----------------------------------------------------------------

_MAX_UPLOAD = {"image": 25 * 1024 * 1024, "audio": 30 * 1024 * 1024}
_IMAGE_MAX_SIDE = 1600


async def _read_body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=413, detail=f"file too large (max {limit // (1024 * 1024)} MB)")
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > limit:
            raise HTTPException(status_code=413, detail=f"file too large (max {limit // (1024 * 1024)} MB)")
    if not buf:
        raise HTTPException(status_code=400, detail="empty upload")
    return bytes(buf)


def _process_image(data: bytes) -> bytes:
    """Decode, apply EXIF rotation, cap the size and re-encode as JPEG.
    Re-encoding drops all EXIF metadata (including GPS)."""
    from io import BytesIO

    from PIL import Image, ImageOps, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = 80_000_000
    try:
        img = Image.open(BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(status_code=415, detail="not an image this server can read (use JPEG, PNG or WebP)")
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((_IMAGE_MAX_SIDE, _IMAGE_MAX_SIDE), Image.LANCZOS)
    out = BytesIO()
    img.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


def _looks_like_mp3(data: bytes) -> bool:
    if data[:3] == b"ID3":
        return True
    # MPEG audio frame sync: 11 set bits.
    return len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


def _write_atomic(directory: Path, name: str, data: bytes) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f".{name}.tmp"
    tmp.write_bytes(data)
    tmp.replace(directory / name)


@api_router.post("/bird/{bird_id}/upload")
async def upload_media(bird_id: str, request: Request, kind: str = Query(pattern="^(audio|image)$")):
    """Add your own photo/recording (raw file in the request body). It
    becomes the one in use; earlier ones stay listed so you can switch back.
    A day already served keeps the media it was played with."""
    data = await _read_body(request, _MAX_UPLOAD[kind])
    if kind == "image":
        data = _process_image(data)
        ext, directory = "jpg", IMAGE_DIR
    else:
        if not _looks_like_mp3(data):
            raise HTTPException(status_code=415, detail="recordings must be MP3 files")
        ext, directory = "mp3", AUDIO_DIR

    db = SessionLocal()
    try:
        bird = db.get(Bird, bird_id)
        if bird is None:
            raise HTTPException(status_code=404, detail="unknown bird")
        name = f"own-{uuid.uuid4()}.{ext}"
        _write_atomic(directory, name, data)
        lowest = min((m.position for m in bird.media if m.kind == kind), default=0)
        db.add(Media(bird_id=bird_id, kind=kind, filename=name, source="own",
                     enabled=True, position=lowest - 1))
        db.commit()
    finally:
        db.close()
    log.info("bird %s: uploaded %s %s (%d bytes)", bird_id, kind, name, len(data))
    invalidate_bird_cache()
    return bird_detail(bird_id)


@api_router.post("/media/{media_id}/use")
def use_media(media_id: int):
    """Make this photo/recording the one in use for its bird."""
    db = SessionLocal()
    try:
        m = db.get(Media, media_id)
        if m is None:
            raise HTTPException(status_code=404, detail="unknown media")
        if _media_file(_dir_for(m.kind), m.filename) is None:
            raise HTTPException(status_code=409, detail="that file is missing")
        siblings = db.query(Media).filter(Media.bird_id == m.bird_id, Media.kind == m.kind).all()
        m.position = min(x.position for x in siblings) - 1
        m.enabled = True
        bird_id = m.bird_id
        db.commit()
    finally:
        db.close()
    log.info("bird %s: now using media %s", bird_id, media_id)
    invalidate_bird_cache()
    return bird_detail(bird_id)


class TrimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: float = Field(ge=0, le=3600)
    end: float = Field(gt=0, le=3600)


def _cut_wav(src_wav: Path, dst_wav: Path, start: float, end: float) -> float:
    """Copy [start, end) seconds of a 16-bit PCM WAV with short fades at
    both ends (avoids clicks). Returns the kept length in seconds."""
    import array
    import wave

    with wave.open(str(src_wav), "rb") as w:
        nch, width, rate, total = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if width != 2:
            raise HTTPException(status_code=500, detail="unexpected audio format")
        f0 = min(total, int(round(start * rate)))
        f1 = min(total, int(round(end * rate)))
        if f1 - f0 < rate:   # under a second left (range past the end?)
            raise HTTPException(status_code=422, detail="less than a second left after trimming (is the range past the end?)")
        w.setpos(f0)
        pcm = array.array("h")
        pcm.frombytes(w.readframes(f1 - f0))
    frames = f1 - f0
    fade_in = min(int(0.05 * rate), frames // 4)
    fade_out = min(int(0.3 * rate), frames // 4)
    for f in range(fade_in):
        g = f / fade_in
        for c in range(nch):
            pcm[f * nch + c] = int(pcm[f * nch + c] * g)
    for k in range(fade_out):
        f = frames - fade_out + k
        g = 1 - (k + 1) / fade_out
        for c in range(nch):
            pcm[f * nch + c] = int(pcm[f * nch + c] * g)
    with wave.open(str(dst_wav), "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return frames / rate


@api_router.post("/media/{media_id}/trim")
def trim_media(media_id: int, req: TrimRequest):
    """Cut a recording to [start, end] seconds as a NEW recording, which
    becomes the one in use. The original is kept. Decodes with mpg123,
    cuts and fades in Python, re-encodes with lame (VBR ~190 kbps)."""
    mpg123, lame = shutil.which("mpg123"), shutil.which("lame")
    if not (mpg123 and lame):
        raise HTTPException(status_code=501, detail="trimming isn't available (mpg123/lame not installed)")
    if req.end - req.start < 1.0:
        raise HTTPException(status_code=422, detail="keep at least 1 second")

    db = SessionLocal()
    try:
        m = db.get(Media, media_id)
        if m is None or m.kind != "audio":
            raise HTTPException(status_code=404, detail="unknown recording")
        src = _media_file(AUDIO_DIR, m.filename)
        if src is None:
            raise HTTPException(status_code=409, detail="that file is missing")

        name = f"trim-{uuid.uuid4()}.mp3"
        with tempfile.TemporaryDirectory() as td:
            wav_in, wav_out, mp3_out = Path(td, "in.wav"), Path(td, "out.wav"), Path(td, "out.mp3")
            try:
                subprocess.run([mpg123, "-q", "-w", str(wav_in), str(src)], check=True, timeout=120, capture_output=True)
                kept = _cut_wav(wav_in, wav_out, req.start, req.end)
                subprocess.run([lame, "--quiet", "-V", "2", str(wav_out), str(mp3_out)], check=True, timeout=120, capture_output=True)
            except subprocess.TimeoutExpired:
                raise HTTPException(status_code=500, detail="trimming took too long")
            except subprocess.CalledProcessError as exc:
                log.warning("trim failed for media %s: %s", media_id, exc.stderr.decode(errors="replace")[-500:])
                raise HTTPException(status_code=500, detail="couldn't decode or encode this recording")
            _write_atomic(AUDIO_DIR, name, mp3_out.read_bytes())

        siblings = db.query(Media).filter(Media.bird_id == m.bird_id, Media.kind == "audio").all()
        base_source = (m.source or "unknown").removesuffix(" (trimmed)")
        db.add(Media(
            bird_id=m.bird_id, kind="audio", filename=name,
            source=f"{base_source} (trimmed)", source_ref=m.source_ref,
            credit=m.credit, licence=m.licence, country=m.country, location=m.location,
            recorded_on=m.recorded_on, quality=m.quality,
            enabled=True, position=min(x.position for x in siblings) - 1,
        ))
        bird_id = m.bird_id
        db.commit()
    finally:
        db.close()
    log.info("bird %s: trimmed media %s to %.2f-%.2fs (%.1fs) as %s", bird_id, media_id, req.start, req.end, kept, name)
    invalidate_bird_cache()
    return bird_detail(bird_id)


@api_router.get("/media/{media_id}/file")
def media_file(media_id: int):
    db = SessionLocal()
    try:
        m = db.get(Media, media_id)
    finally:
        db.close()
    if m is None:
        raise HTTPException(status_code=404, detail="unknown media")
    path = _media_file(_dir_for(m.kind), m.filename)
    if path is None:
        raise HTTPException(status_code=404, detail="file missing")
    media_type = "audio/mpeg" if m.kind == "audio" else (mimetypes.guess_type(path.name)[0] or "image/jpeg")
    return FileResponse(path, media_type=media_type, headers=_PRIVATE_CACHE)


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

@api_router.get("/map/recordings")
def map_recordings():
    """Where each bird's recording in use was made. Coordinates come from the
    geocode cache only (no lookups here); see /map/locate."""
    db = SessionLocal()
    try:
        birds = db.query(Bird).options(selectinload(Bird.media)).all()
        cache = {g.query: g for g in db.query(GeocodeCache).filter(~GeocodeCache.query.like("country:%"))}
    finally:
        db.close()
    points, unlocated = [], []
    for b in birds:
        audio = b.primary("audio")
        loc = audio.location if audio else None
        g = cache.get(loc) if loc else None
        item = {
            "bird_id": b.id, "common_name": b.common_name, "scientific_name": b.scientific_name,
            "enabled": bool(b.enabled), "location": loc,
        }
        if g is not None and g.lat is not None:
            points.append({**item, "lat": g.lat, "lon": g.lon, "approx": bool(g.approx), "matched": g.matched})
        else:
            unlocated.append({**item, "looked_up": g is not None})
    return {"points": points, "unlocated": unlocated}


@api_router.post("/map/locate")
def map_locate(limit: int = Query(default=10, ge=1, le=20)):
    """Look up coordinates for recording locations not yet tried (about a
    second each, so this does a few per call)."""
    db = SessionLocal()
    try:
        tried = {q for (q,) in db.query(GeocodeCache.query)}
        places = [p for (p,) in db.query(distinct(Media.location)).filter(Media.kind == "audio", Media.location.isnot(None))]
        todo = [p for p in sorted(places) if p not in tried][:limit]
        found = 0
        for p in todo:
            try:
                found += geocode.locate_place(db, p).lat is not None
            except Exception as exc:   # network/service trouble: stop, try again later
                log.warning("geocoding stopped at %r: %s", p, exc)
                break
        remaining = len([p for p in places if p not in tried]) - len(todo)
    finally:
        db.close()
    return {"looked_up": len(todo), "found": found, "remaining": max(0, remaining)}


@api_router.get("/map/players")
def map_players(start: str | None = StartQ, end: str | None = EndQ):
    """Rounds and players per country (all we store is a country code),
    placed at each country's centre."""
    db = SessionLocal()
    try:
        rows = (
            _in_range(
                db.query(RoundStat.country, func.count(RoundStat.round_id), func.count(distinct(RoundStat.ip_hash))),
                start, end,
            )
            .filter(RoundStat.country.isnot(None))
            .group_by(RoundStat.country)
            .all()
        )
        out = []
        for code, n_rounds, n_players in rows:
            try:
                g = geocode.locate_country(db, code)
            except Exception as exc:
                log.warning("couldn't locate country %s: %s", code, exc)
                g = None
            out.append({
                "country": code, "rounds": n_rounds, "players": n_players,
                "lat": g.lat if g else None, "lon": g.lon if g else None,
                "name": (g.display_name if g and g.display_name else code),
            })
        unknown = _in_range(db.query(func.count(RoundStat.round_id)), start, end).filter(RoundStat.country.is_(None)).scalar() or 0
        pts = (
            _in_range(
                db.query(RoundStat.lat, RoundStat.lon, RoundStat.city, RoundStat.region, RoundStat.country,
                         func.count(RoundStat.round_id), func.count(distinct(RoundStat.ip_hash))),
                start, end,
            )
            .filter(RoundStat.lat.isnot(None), RoundStat.lon.isnot(None))
            .group_by(RoundStat.lat, RoundStat.lon, RoundStat.city, RoundStat.region, RoundStat.country)
            .all()
        )
        first_city = _in_range(db.query(func.min(RoundStat.game_date)), start, end).filter(RoundStat.lat.isnot(None)).scalar()
    finally:
        db.close()
    out.sort(key=lambda r: -r["rounds"])
    points = [
        {"lat": la, "lon": lo, "city": ci, "region": rg, "country": co, "rounds": n, "players": pl}
        for la, lo, ci, rg, co, n, pl in pts
    ]
    return {"countries": out, "unknown_rounds": unknown, "points": points, "points_since": first_city}
