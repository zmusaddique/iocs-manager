from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .db import init_schema

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema()
    yield


app = FastAPI(title="IOC Watchlist", lifespan=lifespan)
app.include_router(router)


@app.get("/", include_in_schema=False)
def index_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/iocs", include_in_schema=False)
def iocs_page():
    return FileResponse(STATIC_DIR / "iocs.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
