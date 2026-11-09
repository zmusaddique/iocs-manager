from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .db import init_schema

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


class NoCacheStaticFiles(StaticFiles):
    """Static assets that browsers must revalidate on every load.

    Without this the browser heuristically caches the JS/HTML and can keep
    serving stale assets after a deploy, silently breaking features.
    `no-cache` still allows cheap 304 revalidation via Last-Modified.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema()
    yield


app = FastAPI(title="IOC Watchlist", lifespan=lifespan)
app.include_router(router)


@app.get("/", include_in_schema=False)
def index_page():
    return FileResponse(
        STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"}
    )


@app.get("/iocs", include_in_schema=False)
def iocs_page():
    return FileResponse(
        STATIC_DIR / "iocs.html", headers={"Cache-Control": "no-cache"}
    )


app.mount("/static", NoCacheStaticFiles(directory=STATIC_DIR), name="static")
