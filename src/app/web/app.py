from fastapi import FastAPI
from app.web import routes


def create_app() -> FastAPI:
    app = FastAPI(title="price and demand nordics")
    app.include_router(routes.router)
    return app