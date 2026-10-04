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
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

AnalyticsBase = declarative_base()


class RoundStat(AnalyticsBase):
    __tablename__ = "round_stats"

    round_id = Column(String, primary_key=True)
    game_date = Column(String, index=True)   # NZ date the puzzle belongs to
    bird_id = Column(String)
    ip_hash = Column(String, index=True)     # salted SHA-256 of client IP
    country = Column(String, index=True)     # ISO country code, or NULL
    user_agent = Column(String)
    referrer = Column(String, index=True)    # referring host, NULL = direct/unknown
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

# create_all() won't add columns to an existing table, so patch in any that
# were added after the DB was first created.
_existing = {c["name"] for c in inspect(analytics_engine).get_columns("round_stats")}
with analytics_engine.begin() as _conn:
    if "referrer" not in _existing:
        _conn.execute(text("ALTER TABLE round_stats ADD COLUMN referrer VARCHAR"))
        _conn.execute(text("CREATE INDEX IF NOT EXISTS ix_round_stats_referrer ON round_stats (referrer)"))

AnalyticsSession = sessionmaker(bind=analytics_engine)
