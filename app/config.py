import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # works regardless of the current working directory


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
    DEFAULT_LINK_HOURS = int(os.getenv("DEFAULT_LINK_HOURS", "48"))
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))

    # Public email lookups: max failed attempts per IP in the window
    LOOKUP_MAX_FAILS = 15
    LOOKUP_WINDOW_SECONDS = 600


settings = Settings()
