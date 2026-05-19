import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random
import uuid
import os
from fastapi.responses import JSONResponse
from requests import Session
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from schemas import Bird

app = FastAPI()

from fastapi import FastAPI
from api import bird

app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        )


app.include_router(bird.router, prefix="/api/bird")    

# Mount static files LAST so API routes take priority
app.mount("/static", StaticFiles(directory="static"), name="static")
