# models.py
from sqlalchemy import Column, String, Float, Integer, Boolean, inspect, text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class BirdRecording(Base):
    __tablename__ = "bird_recordings"
    id = Column(String, primary_key=True)
    common_name = Column(String)
    genus = Column(String)
    order = Column(String)
    family = Column(String)
    species = Column(String)
    country = Column(String)
    location = Column(String)
    audio_path = Column(String)  # local or remote path to saved audio
    image_path = Column(String)
    date = Column(String)
    quality = Column(String)
    ebird_species_code = Column(String)
    # False = never picked as the daily bird and hidden from the guess list.
    # Kept in the table (and in the pick shuffle, see services/game.py) so
    # toggling one bird doesn't reshuffle every other day.
    enabled = Column(Boolean, nullable=False, default=True, server_default="1")


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup DB
engine = create_engine("sqlite:///birds.db")
Base.metadata.create_all(engine)

# create_all() won't add columns to an existing table.
if "enabled" not in {c["name"] for c in inspect(engine).get_columns("bird_recordings")}:
    with engine.begin() as _conn:
        _conn.execute(text("ALTER TABLE bird_recordings ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1"))

from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_to_db(recording, audio_path):
    db = SessionLocal()
    try:
        bird = BirdRecording(
            id=recording["id"],
            common_name=recording["en"],
            genus=recording["gen"],
            order=None,
            family=None,
            species=recording["sp"],
            country=recording["cnt"],
            location=recording["loc"],
            audio_path=audio_path,
            date=recording["date"],
            quality=recording["q"],
            ebird_species_code=None,
        )
        db.merge(bird)  # merge avoids duplicates based on primary key
        db.commit()
    finally:
        db.close()

def update_bird_taxa(id: str, species_code: str, order: str, family: str):
    db = SessionLocal()
    try:
        bird = db.query(BirdRecording).filter_by(id=id).first()
        
        if bird:
            bird.order = order
            bird.family = family
            bird.ebird_species_code
            db.commit()
    finally:
        db.close()

def get_all_birds():
    db = SessionLocal()
    try:
        return db.query(BirdRecording).all()
    finally:
        db.close()


def update_bird_species_code(id, species_code):
    db = SessionLocal()
    try:
        bird = db.query(BirdRecording).filter_by(id=id).first()

        if bird:
            bird.ebird_species_code = species_code
            db.commit()
    finally:
        db.close()




