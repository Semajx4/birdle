"""Cloudflare Access JWT verification.

When a request reaches us through a Cloudflare Access-protected hostname
(e.g. ``admin.birdle2.nz``), Access adds a ``Cf-Access-Jwt-Assertion`` header:
an RS256-signed JWT describing who logged in. Verifying it here means the
internal routes do not rely on the tunnel/Access config alone — a request that
did not pass Access (routing mistake, Access app removed, another container on
the Docker network calling ``http://birdle:8000`` directly) has no valid token
and is refused.

Config (environment):
    CF_ACCESS_TEAM_DOMAIN   e.g. ``semajx3.cloudflareaccess.com``
    CF_ACCESS_AUD           the Access application's AUD tag
    CF_ACCESS_ALLOWED_EMAILS  optional, comma-separated; if set, the token's
                              ``email`` claim must be one of these
If the team domain or AUD is unset, Access verification is disabled and every
token is rejected.
"""

import logging
import os
from functools import lru_cache

import jwt
from jwt import PyJWKClient

log = logging.getLogger("birdle.cf_access")

HEADER = "cf-access-jwt-assertion"


class AccessDenied(Exception):
    pass


def _team_domain() -> str | None:
    raw = (os.environ.get("CF_ACCESS_TEAM_DOMAIN") or "").strip().lower()
    raw = raw.removeprefix("https://").rstrip("/")
    return raw or None


def _audience() -> str | None:
    return (os.environ.get("CF_ACCESS_AUD") or "").strip() or None


def _allowed_emails() -> set[str]:
    raw = os.environ.get("CF_ACCESS_ALLOWED_EMAILS") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_configured() -> bool:
    return bool(_team_domain() and _audience())


@lru_cache(maxsize=4)
def _jwks_client(team_domain: str) -> PyJWKClient:
    # Caches the signing keys; unknown `kid`s (key rotation) trigger a refetch.
    return PyJWKClient(
        f"https://{team_domain}/cdn-cgi/access/certs",
        cache_keys=True,
        lifespan=3600,
        timeout=5,
    )


def verify_request(request) -> dict:
    """Return the verified claims, or raise AccessDenied."""
    team, aud = _team_domain(), _audience()
    if not (team and aud):
        raise AccessDenied("Cloudflare Access verification not configured")

    token = request.headers.get(HEADER)
    if not token:
        raise AccessDenied("missing Cloudflare Access token")

    try:
        key = _jwks_client(team).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=aud,
            issuer=f"https://{team}",
            leeway=30,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWKClientError as exc:
        log.warning("could not load Access signing keys: %s", exc)
        raise AccessDenied("could not verify Cloudflare Access token") from exc
    except jwt.InvalidTokenError as exc:
        raise AccessDenied(f"invalid Cloudflare Access token: {exc}") from exc

    allowed = _allowed_emails()
    if allowed:
        email = (claims.get("email") or "").lower()
        if email not in allowed:
            raise AccessDenied("Cloudflare Access identity not allowed")

    return claims
