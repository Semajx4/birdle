"""Recording side of analytics: turn requests into RoundStat rows.

Everything here is best-effort — a failure to record must never break gameplay,
so the public helpers swallow and log their own exceptions.

Env vars:
  ANALYTICS_IP_SALT   - salt for hashing IPs. If unset, a random salt is
                        generated once and persisted to ANALYTICS_SALT_FILE
                        (default data/analytics_salt.txt) so hashes stay
                        comparable across restarts.
  ANALYTICS_SALT_FILE - where to persist the generated salt.
  GEOIP_DB_PATH        - path to a MaxMind GeoLite2-Country.mmdb. If unset or
                        unreadable, country is left NULL.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from models.analytics import AnalyticsSession, RoundStat

logger = logging.getLogger("birdle.analytics")


# --------------------------------------------------------------------------- #
# IP handling
# --------------------------------------------------------------------------- #
def _load_salt() -> str:
    env = os.environ.get("ANALYTICS_IP_SALT")
    if env:
        return env

    path = Path(os.environ.get("ANALYTICS_SALT_FILE", "data/analytics_salt.txt"))
    try:
        if path.exists():
            return path.read_text().strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        salt = secrets.token_hex(16)
        path.write_text(salt)
        logger.info("generated new analytics IP salt at %s", path)
        return salt
    except OSError:
        logger.warning("could not persist IP salt; using an ephemeral one")
        return secrets.token_hex(16)


_SALT = _load_salt()


def extract_client_ip(request) -> str:
    """Best guess at the real client IP, honouring common proxy headers.

    ``CF-Connecting-IP`` is checked first: Cloudflare (Tunnel included) sets it
    to the real visitor IP and strips any client-supplied copy at the edge, so
    it is trustworthy. ``X-Forwarded-For`` / ``X-Real-IP`` are only as
    trustworthy as whatever set them.
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return ""


def hash_ip(ip: str):
    if not ip:
        return None
    return hashlib.sha256((_SALT + ip).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# GeoIP (optional)
# --------------------------------------------------------------------------- #
_geoip_reader = None
_geoip_tried = False


def _get_geoip_reader():
    global _geoip_reader, _geoip_tried
    if _geoip_tried:
        return _geoip_reader
    _geoip_tried = True

    db_path = os.environ.get("GEOIP_DB_PATH")
    if not db_path or not Path(db_path).exists():
        return None
    try:
        import geoip2.database

        _geoip_reader = geoip2.database.Reader(db_path)
        logger.info("GeoIP lookups enabled (%s)", db_path)
    except Exception:
        logger.exception("failed to open GeoIP db at %s", db_path)
        _geoip_reader = None
    return _geoip_reader


def lookup_country(ip: str):
    reader = _get_geoip_reader()
    if not reader or not ip:
        return None
    try:
        return reader.country(ip).country.iso_code
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Public recording helpers
# --------------------------------------------------------------------------- #
def record_round_started(round_id: str, bird_id: str, game_date: str, request) -> None:
    try:
        ip = extract_client_ip(request)
        row = RoundStat(
            round_id=round_id,
            bird_id=bird_id,
            game_date=game_date,
            ip_hash=hash_ip(ip),
            country=lookup_country(ip),
            user_agent=(request.headers.get("user-agent") or "")[:500],
            guesses=0,
            won=False,
            finished=False,
            started_at=datetime.now(timezone.utc),
        )
        session = AnalyticsSession()
        try:
            session.merge(row)
            session.commit()
        finally:
            session.close()
        logger.info(
            "round_started round_id=%s game_date=%s bird_id=%s country=%s",
            round_id, game_date, bird_id, row.country,
        )
    except Exception:
        logger.exception("failed to record round_started for %s", round_id)


def record_round_finished(round_id: str, guesses: int, won: bool) -> None:
    try:
        session = AnalyticsSession()
        try:
            row = session.get(RoundStat, round_id)
            if row is None:
                # Round began before analytics existed / row was lost.
                row = RoundStat(
                    round_id=round_id, started_at=datetime.now(timezone.utc)
                )
                session.add(row)
            row.guesses = guesses
            row.won = won
            row.finished = True
            row.finished_at = datetime.now(timezone.utc)
            session.commit()
        finally:
            session.close()
        logger.info(
            "round_finished round_id=%s guesses=%s won=%s", round_id, guesses, won
        )
    except Exception:
        logger.exception("failed to record round_finished for %s", round_id)
