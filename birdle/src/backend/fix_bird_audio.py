import uuid
import shutil
from pathlib import Path
from models.models import SessionLocal, BirdRecording

AUDIO_DIR = Path("datasets/bird_images")

def migrate_audio_names():
    db = SessionLocal()

    birds = db.query(BirdRecording).all()

    for bird in birds:

        old_path = AUDIO_DIR / f"{bird.ebird_species_code}.jpg" 
        if not old_path.exists():
            continue

        new_name = f"{uuid.uuid4()}.jpg"
        new_path = AUDIO_DIR  / new_name

        # shutil.move(old_path, new_path)
        print(new_path)

        # bird.image_path = new_name
        print(new_name)

    db.commit()
    db.close()


if __name__ == "__main__":
    migrate_audio_names()
