# models.py
from sqlalchemy import Column, String, Float, Integer, Boolean
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


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup DB
engine = create_engine("sqlite:///birds.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

def save_to_db(recording, audio_path):
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
    session.merge(bird)  # merge avoids duplicates based on primary key
    session.commit()

def update_bird_taxa(id: str, species_code: str, order: str, family: str):
    bird = session.query(BirdRecording).filter_by(id=id).first()
    
    if bird:
        bird.order = order
        bird.family = family
        bird.ebird_species_code
        session.commit()

def get_all_birds():
    return session.query(BirdRecording).all()


def update_bird_species_code(id, species_code):
    bird = session.query(BirdRecording).filter_by(id=id).first()

    if bird:
        bird.ebird_species_code = species_code
        session.commit()