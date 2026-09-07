"""Analytics storage — kept in its own SQLite file, separate from birds.db.

One row per game round. IPs are never stored raw: only a salted SHA-256 hash
(for counting distinct players / repeat plays) plus an optional country code.

Env vars:
  ANALYTICS_DB_URL  - SQLAlchemy URL, default sqlite:///data/analytics.db
"""

import os
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

AnalyticsBase = declarative_base()


class RoundStat(AnalyticsBase):
    __tablename__ = "round_stats"

    round_id = Column(String, primary_key=True)
    game_date = Column(String, index=True)   # UTC date the puzzle belongs to
    bird_id = Column(String)
    ip_hash = Column(String, index=True)     # salted SHA-256 of client IP
    country = Column(String, index=True)     # ISO country code, or NULL
    user_agent = Column(String)
    guesses = Column(Integer, default=0)
    won = Column(Boolean, default=False)
    finished = Column(Boolean, default=False, index=True)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


_DB_URL = os.environ.get("ANALYTICS_DB_URL", "sqlite:///data/analytics.db")

if _DB_URL.startswith("sqlite:///"):
    _db_file = Path(_DB_URL[len("sqlite:///"):])
    if _db_file.parent and not _db_file.parent.exists():
        _db_file.parent.mkdir(parents=True, exist_ok=True)

analytics_engine = create_engine(
    _DB_URL, connect_args={"check_same_thread": False}
)
AnalyticsBase.metadata.create_all(analytics_engine)

AnalyticsSession = sessionmaker(bind=analytics_engine)
