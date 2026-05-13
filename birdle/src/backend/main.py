import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random
import uuid
import os
from fastapi.responses import JSONResponse
from requests import Session
from models import get_all_birds
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        )

bird_list = get_all_birds()

class Bird():
    def __init__(self, bird_recording):
        self.id = bird_recording.id
        self.common_name = bird_recording.common_name
        self.scientific_name = bird_recording.genus + " " + bird_recording.species
        self.genus = bird_recording.genus
        self.order = bird_recording.order
        self.family = bird_recording.family
        self.audio_path = bird_recording.audio_path
        self.image_path = bird_recording.ebird_species_code + ".jpg" if bird_recording.ebird_species_code else None

    def to_dict(self):
        return {
                "id": self.id,
                "common_name": self.common_name,
                "scientific_name": self.scientific_name,
                "order": self.order,
                "family": self.family,
                "genus": self.genus,
                "audio_path": self.audio_path,
                "image_path": self.image_path
                }

@app.get("/api/bird/random")
def get_random_bird():
    bird = Bird(random.choice(bird_list))
    while bird.image_path is None:
        bird = Bird(random.choice(bird_list))
    print(bird.to_dict())
    return bird.to_dict()

@app.get("/api/bird/all")
def get_all_birds_route():
    return [Bird(bird).to_dict() for bird in bird_list]

# Mount static files LAST so API routes take priority
app.mount("/", StaticFiles(directory="static", html=True), name="static")
