"""Analytics storage: one row per game round, in the main database.

IPs are never stored raw: only a salted SHA-256 hash (for counting distinct
players / repeat plays) plus an optional country code.
"""

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from db import Base, SessionLocal


class RoundStat(Base):
    __tablename__ = "round_stats"

    round_id = Column(String, primary_key=True)
    game_date = Column(String(10), index=True)   # NZ date the puzzle belongs to
    bird_id = Column(String, index=True)
    ip_hash = Column(String, index=True)         # salted SHA-256 of client IP
    country = Column(String, index=True)         # ISO country code, or NULL
    # From GeoLite2-City when available (rounds from 2026-11-18 on). lat/lon
    # are MaxMind's city-level estimate rounded to ~1 km, never precise.
    region = Column(String)
    city = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    user_agent = Column(String)
    referrer = Column(String, index=True)        # referring host, NULL = direct/unknown
    guesses = Column(Integer, default=0)
    won = Column(Boolean, default=False)
    finished = Column(Boolean, default=False, index=True)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))


# Kept as an alias so existing callers don't change.
AnalyticsSession = SessionLocal
