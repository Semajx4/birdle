from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random
import uuid

app = FastAPI()

# Allow frontend (localhost:5173) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dummy birds data
birds = [
    {
        "uuid": str(uuid.uuid4()),
        "common_name": "Bellbird",
        "scientific_name": "Anthornis melanura",
        "audio_path": "/audio/bellbird.mp3",
        "image_path": "/images/bellbird.jpg",
    },
    {
        "uuid": str(uuid.uuid4()),
        "common_name": "Kea",
        "scientific_name": "Nestor notabilis",
        "audio_path": "/audio/kea.mp3",
        "image_path": "/images/kea.jpg",
    },
    # add more birds here
]

@app.get("/api/bird/random")
def get_random_bird():
    return random.choice(birds)
