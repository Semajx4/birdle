"""Bird data: species (``birds``), their media files (``media``) and the
bird served on each game day (``daily_picks``).

Media files stay on disk (``MEDIA_ROOT``, see services/game.py); rows store
the filename relative to the kind's directory (audio/ or bird_images/).
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from db import Base, SessionLocal  # noqa: F401  (SessionLocal re-exported)


def _now():
    return datetime.now(timezone.utc)


class Bird(Base):
    """One row per bird the game can use.

    ``id`` is the original xeno-canto recording id for birds migrated from
    the old ``bird_recordings`` table. It is the id the frontend guesses with
    and analytics stores, so it must never change.
    """

    __tablename__ = "birds"

    id = Column(String, primary_key=True)
    common_name = Column(String, nullable=False)
    genus = Column(String)
    species = Column(String)
    family = Column(String)
    order = Column("taxon_order", String)
    ebird_species_code = Column(String)
    # False = never the daily bird and hidden from the guess list.
    enabled = Column(Boolean, nullable=False, default=True)
    # Fixed position in the daily-pick shuffle (see services/game.py). Kept
    # explicit so the schedule never depends on row/storage order.
    pick_order = Column(Integer, nullable=False, unique=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    media = relationship(
        "Media",
        back_populates="bird",
        cascade="all, delete-orphan",
        order_by="(Media.position, Media.id)",
    )

    @property
    def scientific_name(self):
        return " ".join(p for p in (self.genus, self.species) if p) or None

    def primary(self, kind: str):
        """First enabled media of a kind ('audio' / 'image'), or None."""
        for m in self.media:
            if m.kind == kind and m.enabled:
                return m
        return None


class Media(Base):
    """A recording or photo of a bird. Many per bird."""

    __tablename__ = "media"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bird_id = Column(String, ForeignKey("birds.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(10), nullable=False)          # 'audio' | 'image'
    filename = Column(String, nullable=False)          # relative to the kind's directory
    source = Column(String)                            # 'xeno-canto' | 'macaulay' | 'own' | ...
    source_ref = Column(String)                        # e.g. xeno-canto recording id
    credit = Column(String)
    licence = Column(String)
    country = Column(String)
    location = Column(String)
    recorded_on = Column(String)
    quality = Column(String)
    enabled = Column(Boolean, nullable=False, default=True)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)

    bird = relationship("Bird", back_populates="media")


class DailyPick(Base):
    """The bird actually served on a game day, pinned the first time the day
    is played. Later edits to the bird list can't change it."""

    __tablename__ = "daily_picks"

    game_date = Column(String(10), primary_key=True)   # NZ date, YYYY-MM-DD
    bird_id = Column(String, ForeignKey("birds.id"), nullable=False, index=True)
    audio_media_id = Column(Integer, ForeignKey("media.id", ondelete="SET NULL"))
    image_media_id = Column(Integer, ForeignKey("media.id", ondelete="SET NULL"))
    source = Column(String, nullable=False, default="served")   # 'served' | 'backfill'
    picked_at = Column(DateTime(timezone=True), default=_now)


class GeocodeCache(Base):
    """Coordinates looked up for a place name (recording locations) or a
    country code (players), so each is only ever looked up once. A row with
    no lat/lon means the lookup found nothing."""

    __tablename__ = "geocode_cache"

    query = Column(String, primary_key=True)        # location text, or "country:NZ"
    lat = Column(Float)
    lon = Column(Float)
    matched = Column(String)                        # the query text that matched
    display_name = Column(String)
    approx = Column(Boolean, nullable=False, default=False)
    looked_up_at = Column(DateTime(timezone=True), default=_now)
