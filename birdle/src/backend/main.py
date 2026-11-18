import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from util.logging_config import configure_logging

configure_logging()

from db import init_db

init_db()

# Dev convenience: an empty database gets the birds from the committed
# legacy birds.db. Production is migrated explicitly (migrate_sqlite_to_db.py).
from migrate_sqlite_to_db import seed_birds_if_empty

seed_birds_if_empty()

from api import admin, bird, stats

app = FastAPI()

request_logger = logging.getLogger("birdle.request")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    request_logger.info(
        "%s %s -> %s %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(bird.router, prefix="/api/bird")
app.include_router(stats.router, prefix="/internal/stats")
app.include_router(admin.api_router, prefix="/internal/admin/api")
app.include_router(admin.router, prefix="/internal/admin")

# Mount static files LAST so API routes take priority
app.mount("/", StaticFiles(directory="static", html=True), name="spa")

app.mount("/static", StaticFiles(directory="static"), name="static")
