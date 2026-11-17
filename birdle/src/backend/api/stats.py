"""Internal analytics API.

These endpoints are NOT meant to be public.

Requests that arrive through Cloudflare (``CF-Connecting-IP`` or a
``Cf-Access-Jwt-Assertion`` header present) are only served on
``ADMIN_HOSTNAME`` (e.g. admin.birdle2.nz) and only with a valid Cloudflare
Access JWT (see services/cf_access.py); anything else via Cloudflare gets 404.

Direct/local requests are gated two ways:

1.  A shared secret. Set ``STATS_TOKEN`` and send it as ``X-Stats-Token``
    (or ``Authorization: Bearer <token>``). If ``STATS_TOKEN`` is unset the
    whole router returns 503 — it is disabled by default.
2.  A caller-IP allowlist. ``STATS_ALLOWED_NETWORKS`` (comma-separated CIDRs)
    defaults to loopback + RFC1918, so only something on the same host/LAN
    can reach it.

The allowlist is evaluated against the *effective* client IP: if a
``CF-Connecting-IP`` header is present (Cloudflare / Cloudflare Tunnel, which
strips client-supplied copies at the edge) that real visitor IP is used, so a
request arriving through the tunnel is judged on the visitor's public IP and
denied. A request made directly on the host (e.g. ``curl localhost:8000``) has
no such header and is judged on the loopback/bridge peer address, so it passes.

Belt and braces: also keep your Cloudflare Tunnel ingress from routing
``/internal/*`` at all (see ANALYTICS.md), and bind the published port to
loopback so the only path in is the tunnel.
"""

import ipaddress
import os

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import Integer, cast, distinct, func

from models.analytics import AnalyticsSession, RoundStat
from models.models import BirdRecording, SessionLocal
from services import cf_access
from services.analytics import extract_client_ip

_DEFAULT_NETWORKS = "127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7"


def _allowed_networks():
    raw = os.environ.get("STATS_ALLOWED_NETWORKS", _DEFAULT_NETWORKS)
    nets = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            pass
    return nets


def _host(request: Request) -> str:
    host = (request.headers.get("host") or "").strip().lower()
    if host.startswith("["):  # IPv6 literal, e.g. [::1]:8000
        return host.split("]")[0] + "]"
    return host.split(":")[0]


def came_via_cloudflare(request: Request) -> bool:
    return bool(request.headers.get("cf-connecting-ip") or request.headers.get(cf_access.HEADER))


def _check_access(request: Request, token_header, auth_header) -> None:
    # Path 1: arrived via Cloudflare (tunnel). Only the admin hostname may reach
    # /internal, and only with a valid Cloudflare Access token. Everything else
    # through Cloudflare gets a plain 404 so the routes don't advertise
    # themselves on the public site.
    if came_via_cloudflare(request):
        admin_host = (os.environ.get("ADMIN_HOSTNAME") or "").strip().lower()
        if not admin_host or _host(request) != admin_host or not cf_access.is_configured():
            raise HTTPException(status_code=404, detail="Not Found")
        try:
            cf_access.verify_request(request)
        except cf_access.AccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        return

    # Path 2: direct/local call (e.g. `curl localhost:8000` on the host):
    # shared token + caller-IP allowlist.
    expected = os.environ.get("STATS_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="stats API disabled (STATS_TOKEN unset)")

    provided = token_header
    if not provided and auth_header and auth_header.lower().startswith("bearer "):
        provided = auth_header[7:].strip()
    if not provided or not secrets_equal(provided, expected):
        raise HTTPException(status_code=401, detail="bad or missing stats token")

    nets = _allowed_networks()
    if nets:
        caller = extract_client_ip(request)
        try:
            addr = ipaddress.ip_address(caller)
        except ValueError:
            raise HTTPException(status_code=403, detail="caller not in allowlist")
        if not any(addr in net for net in nets):
            raise HTTPException(status_code=403, detail="caller not in allowlist")


def secrets_equal(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a, b)


def require_access(
    request: Request,
    x_stats_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """FastAPI dependency guarding every /internal route (stats + admin UI)."""
    _check_access(request, x_stats_token, authorization)


router = APIRouter(dependencies=[Depends(require_access)])

# Optional inclusive date range on game_date (NZ dates, YYYY-MM-DD; string
# comparison is correct for that format).
_DATE = r"^\d{4}-\d{2}-\d{2}$"
StartQ = Query(default=None, pattern=_DATE, description="first game_date, inclusive")
EndQ = Query(default=None, pattern=_DATE, description="last game_date, inclusive")


def _in_range(q, start: str | None, end: str | None):
    if start:
        q = q.filter(RoundStat.game_date >= start)
    if end:
        q = q.filter(RoundStat.game_date <= end)
    return q


def _bird_info(bird_ids) -> dict:
    """bird_id -> {common_name, scientific_name, country, location} from birds.db."""
    ids = {str(b) for b in bird_ids if b}
    if not ids:
        return {}
    db = SessionLocal()
    try:
        rows = db.query(BirdRecording).filter(BirdRecording.id.in_(ids)).all()
        return {
            r.id: {
                "common_name": r.common_name,
                "scientific_name": " ".join(p for p in (r.genus, r.species) if p) or None,
                "country": r.country,
                "location": r.location,
            }
            for r in rows
        }
    finally:
        db.close()


_NO_BIRD = {"common_name": None, "scientific_name": None, "country": None, "location": None}


def _device(user_agent: str | None) -> str:
    ua = (user_agent or "").lower()
    if not ua:
        return "unknown"
    if any(k in ua for k in ("bot", "crawler", "spider", "headless", "curl", "python-requests")):
        return "bot"
    if "iphone" in ua or "ipad" in ua or "ipod" in ua:
        return "iOS"
    if "android" in ua:
        return "Android"
    if "windows" in ua:
        return "Windows"
    if "macintosh" in ua or "mac os x" in ua:
        return "Mac"
    if "cros" in ua:
        return "ChromeOS"
    if "linux" in ua:
        return "Linux"
    return "other"


@router.get("/summary")
def summary(start: str | None = StartQ, end: str | None = EndQ):
    session = AnalyticsSession()
    try:
        row = _in_range(
            session.query(
                func.count(RoundStat.round_id),
                func.count(distinct(RoundStat.ip_hash)),
                func.sum(cast(RoundStat.finished, Integer)),
                func.sum(cast(RoundStat.won, Integer)),
            ),
            start,
            end,
        ).one()
        total_rounds, distinct_players = row[0] or 0, row[1] or 0
        finished_rounds, wins = int(row[2] or 0), int(row[3] or 0)

        avg_finished = _in_range(
            session.query(func.avg(RoundStat.guesses)).filter(RoundStat.finished.is_(True)),
            start,
            end,
        ).scalar()
        avg_won = _in_range(
            session.query(func.avg(RoundStat.guesses)).filter(RoundStat.won.is_(True)),
            start,
            end,
        ).scalar()
        return {
            "start": start,
            "end": end,
            "total_rounds": total_rounds,
            "distinct_players": distinct_players,
            "finished_rounds": finished_rounds,
            "unfinished_rounds": total_rounds - finished_rounds,
            "wins": wins,
            "losses": finished_rounds - wins,
            "win_rate": round(wins / finished_rounds, 4) if finished_rounds else None,
            "avg_guesses_when_finished": round(avg_finished, 2) if avg_finished is not None else None,
            "avg_guesses_when_won": round(avg_won, 2) if avg_won is not None else None,
        }
    finally:
        session.close()


@router.get("/daily")
def daily(start: str | None = StartQ, end: str | None = EndQ):
    """One row per game_date (newest first) with that day's bird."""
    session = AnalyticsSession()
    try:
        rows = (
            _in_range(
                session.query(
                    RoundStat.game_date,
                    func.count(RoundStat.round_id),
                    func.count(distinct(RoundStat.ip_hash)),
                    func.sum(cast(RoundStat.finished, Integer)),
                    func.sum(cast(RoundStat.won, Integer)),
                    func.max(RoundStat.bird_id),
                ),
                start,
                end,
            )
            .group_by(RoundStat.game_date)
            .order_by(RoundStat.game_date.desc())
            .all()
        )
        birds = _bird_info(r[5] for r in rows)
        return [
            {
                "game_date": r[0],
                "rounds": r[1] or 0,
                "players": r[2] or 0,
                "finished": int(r[3] or 0),
                "wins": int(r[4] or 0),
                "bird_id": r[5],
                **birds.get(str(r[5]), _NO_BIRD),
            }
            for r in rows
        ]
    finally:
        session.close()


@router.get("/birds")
def birds(start: str | None = StartQ, end: str | None = EndQ):
    """Per-bird difficulty across every day the bird was the daily pick."""
    session = AnalyticsSession()
    try:
        rows = _in_range(
            session.query(
                RoundStat.bird_id,
                RoundStat.game_date,
                RoundStat.finished,
                RoundStat.won,
                RoundStat.guesses,
            ),
            start,
            end,
        ).all()
    finally:
        session.close()

    agg = defaultdict(lambda: {"dates": set(), "rounds": 0, "finished": 0, "wins": 0, "guesses": 0})
    for bird_id, game_date, finished, won, guesses in rows:
        a = agg[bird_id]
        a["dates"].add(game_date)
        a["rounds"] += 1
        if finished:
            a["finished"] += 1
            a["guesses"] += guesses or 0
        if won:
            a["wins"] += 1

    info = _bird_info(agg.keys())
    out = []
    for bird_id, a in agg.items():
        out.append(
            {
                "bird_id": bird_id,
                **info.get(str(bird_id), _NO_BIRD),
                "dates": sorted(a["dates"], reverse=True),
                "rounds": a["rounds"],
                "finished": a["finished"],
                "wins": a["wins"],
                "losses": a["finished"] - a["wins"],
                "win_rate": round(a["wins"] / a["finished"], 4) if a["finished"] else None,
                "avg_guesses_when_finished": round(a["guesses"] / a["finished"], 2) if a["finished"] else None,
            }
        )
    out.sort(key=lambda b: b["dates"][0] if b["dates"] else "", reverse=True)
    return out


@router.get("/breakdowns")
def breakdowns(start: str | None = StartQ, end: str | None = EndQ):
    """Rounds and distinct players by country, device and referrer."""
    session = AnalyticsSession()
    try:
        rows = _in_range(
            session.query(RoundStat.country, RoundStat.user_agent, RoundStat.referrer, RoundStat.ip_hash),
            start,
            end,
        ).all()
    finally:
        session.close()

    def group(key_fn):
        rounds, players = Counter(), defaultdict(set)
        for r in rows:
            k = key_fn(r)
            rounds[k] += 1
            if r.ip_hash:
                players[k].add(r.ip_hash)
        return [
            {"key": k, "rounds": n, "players": len(players[k])}
            for k, n in rounds.most_common()
        ]

    return {
        "countries": group(lambda r: r.country or "unknown"),
        "devices": group(lambda r: _device(r.user_agent)),
        "referrers": group(lambda r: r.referrer or "direct / unknown"),
    }


@router.get("/countries")
def countries(start: str | None = StartQ, end: str | None = EndQ):
    session = AnalyticsSession()
    try:
        rows = (
            _in_range(
                session.query(
                    RoundStat.country,
                    func.count(RoundStat.round_id),
                    func.count(distinct(RoundStat.ip_hash)),
                ),
                start,
                end,
            )
            .group_by(RoundStat.country)
            .order_by(func.count(RoundStat.round_id).desc())
            .all()
        )
        return [
            {"country": r[0] or "unknown", "rounds": r[1] or 0, "players": r[2] or 0}
            for r in rows
        ]
    finally:
        session.close()


@router.get("/rounds")
def rounds(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    finished: bool | None = Query(default=None),
    game_date: str | None = Query(default=None, pattern=_DATE),
    start: str | None = StartQ,
    end: str | None = EndQ,
):
    session = AnalyticsSession()
    try:
        q = _in_range(session.query(RoundStat), start, end)
        if finished is not None:
            q = q.filter(RoundStat.finished.is_(finished))
        if game_date:
            q = q.filter(RoundStat.game_date == game_date)
        q = q.order_by(RoundStat.started_at.desc()).limit(limit).offset(offset)
        return [
            {
                "round_id": r.round_id,
                "game_date": r.game_date,
                "bird_id": r.bird_id,
                "ip_hash": r.ip_hash,
                "country": r.country,
                "user_agent": r.user_agent,
                "device": _device(r.user_agent),
                "referrer": r.referrer,
                "guesses": r.guesses,
                "won": r.won,
                "finished": r.finished,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in q.all()
        ]
    finally:
        session.close()
