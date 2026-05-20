from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
app.mount("/audio", StaticFiles(directory="audio"), name="audio")
app.mount("/images", StaticFiles(directory="bird_images"), name="images")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
