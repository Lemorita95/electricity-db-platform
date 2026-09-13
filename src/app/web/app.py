from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.web import routes

BASE = Path(__file__).resolve().parent
STATIC_DIR = BASE / "static"

def create_app() -> FastAPI:
    app = FastAPI(title="price and demand nordics")
    app.include_router(routes.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app