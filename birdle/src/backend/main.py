import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from util.logging_config import configure_logging

configure_logging()

from api import bird, stats

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

# Mount static files LAST so API routes take priority
app.mount("/", StaticFiles(directory="static", html=True), name="spa")

app.mount("/static", StaticFiles(directory="static"), name="static")
