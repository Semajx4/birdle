"""Internal analytics API.

These endpoints are NOT meant to be public. They are gated two ways:

1.  A shared secret. Set ``STATS_TOKEN`` and send it as ``X-Stats-Token``
    (or ``Authorization: Bearer <token>``). If ``STATS_TOKEN`` is unset the
    whole router returns 503 — it is disabled by default.
2.  A caller-IP allowlist. ``STATS_ALLOWED_NETWORKS`` (comma-separated CIDRs)
    defaults to loopback + RFC1918 + the Docker bridge, so on a normal
    deployment only something running on the same host/LAN can reach it.

Note: if you sit the app behind a reverse proxy that forwards every path,
the peer address is always the proxy, so the allowlist can't tell callers
apart — keep the proxy from forwarding ``/internal/`` and rely on the token.
"""

import ipaddress
import os

from fastapi import APIRouter, Header, HTTPException, Query, Request
from sqlalchemy import distinct, func

from models.analytics import AnalyticsSession, RoundStat

router = APIRouter()

_DEFAULT_NETWORKS = "127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"


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


def _check_access(request: Request, token_header, auth_header) -> None:
    expected = os.environ.get("STATS_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="stats API disabled (STATS_TOKEN unset)")

    provided = token_header
    if not provided and auth_header and auth_header.lower().startswith("bearer "):
        provided = auth_header[7:].strip()
    if not provided or not secrets_equal(provided, expected):
        raise HTTPException(status_code=401, detail="bad or missing stats token")

    peer = request.client.host if request.client else ""
    nets = _allowed_networks()
    if nets:
        try:
            addr = ipaddress.ip_address(peer)
        except ValueError:
            raise HTTPException(status_code=403, detail="caller not in allowlist")
        if not any(addr in net for net in nets):
            raise HTTPException(status_code=403, detail="caller not in allowlist")


def secrets_equal(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a, b)


def _guard(request: Request, x_stats_token, authorization):
    _check_access(request, x_stats_token, authorization)


@router.get("/summary")
def summary(
    request: Request,
    x_stats_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    _guard(request, x_stats_token, authorization)

    session = AnalyticsSession()
    try:
        total_rounds = session.query(func.count(RoundStat.round_id)).scalar() or 0
        distinct_players = (
            session.query(func.count(distinct(RoundStat.ip_hash)))
            .filter(RoundStat.ip_hash.isnot(None))
            .scalar()
            or 0
        )
        finished_rounds = (
            session.query(func.count(RoundStat.round_id))
            .filter(RoundStat.finished.is_(True))
            .scalar()
            or 0
        )
        wins = (
            session.query(func.count(RoundStat.round_id))
            .filter(RoundStat.won.is_(True))
            .scalar()
            or 0
        )
        avg_guesses = (
            session.query(func.avg(RoundStat.guesses))
            .filter(RoundStat.finished.is_(True))
            .scalar()
        )
        return {
            "total_rounds": total_rounds,
            "distinct_players": distinct_players,
            "finished_rounds": finished_rounds,
            "unfinished_rounds": total_rounds - finished_rounds,
            "wins": wins,
            "losses": finished_rounds - wins,
            "win_rate": round(wins / finished_rounds, 4) if finished_rounds else None,
            "avg_guesses_when_finished": round(avg_guesses, 2) if avg_guesses is not None else None,
        }
    finally:
        session.close()


@router.get("/daily")
def daily(
    request: Request,
    x_stats_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    _guard(request, x_stats_token, authorization)

    session = AnalyticsSession()
    try:
        rows = (
            session.query(
                RoundStat.game_date,
                func.count(RoundStat.round_id),
                func.count(distinct(RoundStat.ip_hash)),
                func.sum(RoundStat.finished),
                func.sum(RoundStat.won),
            )
            .group_by(RoundStat.game_date)
            .order_by(RoundStat.game_date.desc())
            .all()
        )
        return [
            {
                "game_date": r[0],
                "rounds": r[1] or 0,
                "players": r[2] or 0,
                "finished": int(r[3] or 0),
                "wins": int(r[4] or 0),
            }
            for r in rows
        ]
    finally:
        session.close()


@router.get("/countries")
def countries(
    request: Request,
    x_stats_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    _guard(request, x_stats_token, authorization)

    session = AnalyticsSession()
    try:
        rows = (
            session.query(
                RoundStat.country,
                func.count(RoundStat.round_id),
                func.count(distinct(RoundStat.ip_hash)),
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
    request: Request,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    finished: bool | None = Query(default=None),
    game_date: str | None = Query(default=None),
    x_stats_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    _guard(request, x_stats_token, authorization)

    session = AnalyticsSession()
    try:
        q = session.query(RoundStat)
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
