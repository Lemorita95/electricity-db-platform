import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]  # project root
load_dotenv(BASE_DIR / ".env")


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB")
MANAGER_USER = os.getenv("MANAGER_USER")
MANAGER_PASSWORD = os.getenv("MANAGER_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

DATABASE_URL = f"postgresql://{MANAGER_USER}:{MANAGER_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# needed for alembic migrations
ADMIN_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{DB_HOST}:{DB_PORT}/{POSTGRES_DB}"