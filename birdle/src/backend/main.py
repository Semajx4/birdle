import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random
import uuid

from fastapi.responses import JSONResponse
from requests import Session
from models import get_all_birds
app = FastAPI()

# Allow frontend (localhost:5173) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
bird_list = get_all_birds()


class Bird():
    def __init__(self, bird_recording):
        self.id = bird_recording.id
        self.common_name = bird_recording.common_name
        self.scientific_name = bird_recording.genus + " "+ bird_recording.species
        self.genus = bird_recording.genus
        self.order = bird_recording.order
        self.family = bird_recording.family
        self.audio_path = bird_recording.audio_path
    def to_dict(self):
        return {
            "id": self.id,
            "common_name": self.common_name,
            "scientific_name": self.scientific_name,
            "order": self.order,
            "family": self.family,
            "genus": self.genus,
            "audio_path": self.audio_path,
        }


@app.get("/api/bird/random")
def get_random_bird():
    bird = Bird(random.choice(bird_list))
    print(bird.to_dict())
    return bird.to_dict()

@app.get("/api/bird/all")
def get_all_birds():
    return [Bird(bird) for bird in bird_list]
