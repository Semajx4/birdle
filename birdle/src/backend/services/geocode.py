"""Place-name -> coordinates, via OpenStreetMap's Nominatim, cached in
the geocode_cache table so each name is looked up once.

Only public place names (recording locations) and ISO country codes are
sent; nothing about players. Nominatim's usage policy: at most 1 request
per second, a descriptive User-Agent, results cached. Both are done here.

CLI (inside the app container):
    python -m services.geocode            # look up recording locations not yet cached
    python -m services.geocode --retry    # also redo not-found and approximate ones
"""

import logging
import math
import re
import sys
import threading
import time

import requests

from models.models import GeocodeCache, SessionLocal

log = logging.getLogger("birdle.geocode")

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "birdle-admin-map/1.0 (self-hosted)"
# Recordings are all from New Zealand or the Cook Islands; restricting the
# search stops a vague name matching somewhere overseas.
RECORDING_COUNTRIES = "nz,ck"

# Places OSM's search doesn't find by these names. Approximate centres.
MANUAL = {
    "Snares Island": (-48.02, 166.60),
    "on flats between Lake Tekapo and Lake Alexandrina (western shore)": (-43.97, 170.44),
    "Mapara Forest Reserve": (-38.62, 175.34),
}

_lock = threading.Lock()
_last_call = 0.0


def _search(params: dict):
    global _last_call
    with _lock:
        wait = 1.1 - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            r = requests.get(
                NOMINATIM,
                params={**params, "format": "jsonv2", "limit": 1},
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
        finally:
            _last_call = time.monotonic()
    r.raise_for_status()
    data = r.json()
    return data[0] if data else None


def _candidates(location: str):
    """Most specific first: the full name (without parentheses), the first
    part, the first two parts, then ever-shorter tails ("X, District,
    Region" -> "District, Region" -> "Region")."""
    clean = " ".join(re.sub(r"\([^)]*\)", " ", location).split()).strip(" ,")
    parts = [p.strip() for p in clean.split(",") if p.strip()]
    out = [clean]
    if parts:
        out.append(parts[0])
    if len(parts) > 2:
        out.append(", ".join(parts[:2]))
    for i in range(1, len(parts)):
        out.append(", ".join(parts[i:]))
    seen, uniq = set(), []
    for c in out:
        if c and c.lower() not in seen:
            seen.add(c.lower())
            uniq.append(c)
    return uniq


def _store(db, key, hit=None, matched=None, approx=False, latlon=None):
    row = db.get(GeocodeCache, key) or GeocodeCache(query=key)
    if latlon:
        row.lat, row.lon = latlon
    elif hit:
        row.lat, row.lon = float(hit["lat"]), float(hit["lon"])
    else:
        row.lat = row.lon = None
    row.matched = matched
    row.display_name = hit.get("display_name") if hit else None
    row.approx = approx
    db.merge(row)
    db.commit()
    return row


def _km(a, b):
    """Great-circle distance between two (lat, lon) points."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


# A specific match must be this close to the place's broad region (the last
# part of the name), so "Shag Rock, ..., Chatham Island" can't land on a
# different Shag Rock in Southland.
MAX_KM_FROM_REGION = 150
COUNTRY_NAMES = {"new zealand", "cook islands"}


def locate_place(db, location: str, retry: bool = False):
    """Cached coordinates for a recording location (looked up if needed)."""
    row = db.get(GeocodeCache, location)
    if row is not None and not (retry and (row.lat is None or (row.approx and row.matched != "manual"))):
        return row
    if location in MANUAL:
        return _store(db, location, matched="manual", approx=True, latlon=MANUAL[location])
    cands = _candidates(location)
    # The region is the broadest part of the name, unless that's a whole
    # country (the Cook Islands span ~1000 km of ocean); then the next part up.
    region_q = cands[-1] if len(cands) > 1 else None
    if region_q and region_q.lower() in COUNTRY_NAMES and len(cands) > 2:
        region_q = cands[-2]
    elif region_q and region_q.lower() in COUNTRY_NAMES:
        region_q = None
    region_hit = _search({"q": region_q, "countrycodes": RECORDING_COUNTRIES}) if region_q else None
    region = (float(region_hit["lat"]), float(region_hit["lon"])) if region_hit else None
    for i, cand in enumerate(cands):
        if cand == region_q and region_hit:
            hit = region_hit
        else:
            hit = _search({"q": cand, "countrycodes": RECORDING_COUNTRIES})
        if not hit:
            continue
        if region and _km(region, (float(hit["lat"]), float(hit["lon"]))) > MAX_KM_FROM_REGION:
            log.info("rejected %r for %r: too far from %r", cand, location, region_q)
            continue
        return _store(db, location, hit, matched=cand, approx=i > 0)
    log.info("no coordinates found for %r", location)
    return _store(db, location)


def locate_country(db, code: str):
    """Cached centre point for an ISO country code (looked up if needed)."""
    key = f"country:{code.upper()}"
    row = db.get(GeocodeCache, key)
    if row is not None:
        return row
    hit = _search({"country": code})
    if not hit:   # territories such as Hong Kong aren't "countries" in OSM
        hit = _search({"q": code, "featuretype": "country"})
    return _store(db, key, hit, matched=code if hit else None)


def main(argv):
    from sqlalchemy import distinct

    from db import init_db
    from models.models import Media

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    retry = "--retry" in argv   # also redo not-found and approximate (non-manual) places
    init_db()
    db = SessionLocal()
    try:
        places = [p for (p,) in db.query(distinct(Media.location)).filter(Media.kind == "audio", Media.location.isnot(None))]
        found = approx = missing = 0
        for loc in sorted(places):
            row = locate_place(db, loc, retry=retry)
            if row.lat is None:
                missing += 1
                print(f"  not found: {loc}")
            else:
                found += 1
                approx += bool(row.approx)
        print(f"{len(places)} places: {found} located ({approx} approximate), {missing} not found")

        from models.analytics import RoundStat
        codes = [c for (c,) in db.query(distinct(RoundStat.country)).filter(RoundStat.country.isnot(None))]
        if retry:
            db.query(GeocodeCache).filter(GeocodeCache.query.like("country:%"), GeocodeCache.lat.is_(None)).delete(synchronize_session=False)
            db.commit()
        located = sum(locate_country(db, c).lat is not None for c in codes)
        print(f"{len(codes)} player countries: {located} located")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1:])
