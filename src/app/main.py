# main.py — just the app, no uvicorn
from app.web.app import create_app
app = create_app()