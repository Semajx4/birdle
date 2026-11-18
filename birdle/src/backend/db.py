"""Database engine + session factory shared by the game, analytics and admin.

Env vars:
  DATABASE_URL - SQLAlchemy URL. Production uses PostgreSQL, e.g.
                 postgresql+psycopg://birdle:<password>@db:5432/birdle
                 Defaults to a local SQLite file for development/tests.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/birdle.db")

_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}
    _file = DATABASE_URL.split("///", 1)[-1]
    if _file and _file != ":memory:":
        Path(_file).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(DATABASE_URL, **_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


def init_db() -> None:
    """Create any missing tables. Import the model modules first so they are
    registered on Base."""
    import models.analytics  # noqa: F401
    import models.models  # noqa: F401

    Base.metadata.create_all(engine)
