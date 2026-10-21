from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def _prepare_url(url: str) -> str:
    """Make sure SQL Server URLs carry TrustServerCertificate=yes (ODBC 17/18 SSL policy)."""
    if not url.lower().startswith("mssql"):
        return url
    low = url.lower()
    if "trustservercertificate" in low:
        return url
    if "odbc_connect=" in low:
        return url + "%3BTrustServerCertificate%3Dyes"
    return url + ("&" if "?" in url else "?") + "TrustServerCertificate=yes"


DATABASE_URL = _prepare_url(settings.DATABASE_URL)
_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release. Applied automatically to existing databases.
_MIGRATIONS = [
    ("participants", "name_locked", "BIT NOT NULL DEFAULT 0"),
    ("participants", "download_count", "INT NOT NULL DEFAULT 0"),
    ("participants", "first_generated_at", "DATETIME NULL"),
    ("participants", "last_downloaded_at", "DATETIME NULL"),
]


def check_connection() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def init_db() -> None:
    """Create missing tables and add missing columns. Safe to run on every start."""
    from . import models  # noqa: F401  (registers all tables)

    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    for table, column, ddl in _MIGRATIONS:
        if table in insp.get_table_names():
            existing = {c["name"] for c in insp.get_columns(table)}
            if column not in existing:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD {column} {ddl}"))
