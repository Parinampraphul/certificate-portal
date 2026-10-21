"""Start the portal:  python run.py"""
import sys

import uvicorn
from sqlalchemy import text

from app.config import settings
from app.database import check_connection, engine, init_db

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    print("\n" + "=" * 60)
    print("STARTING THE DATA & AI GUILD CERTIFICATE PORTAL")
    print("=" * 60)
    try:
        check_connection()
        with engine.connect() as conn:
            db_name = conn.execute(text("SELECT DB_NAME()")).scalar() if engine.dialect.name == "mssql" else "sqlite"
        print(f"[OK] Connected to database '{db_name}'")
        init_db()
        print("[OK] Tables verified / created")
    except Exception as exc:
        print("\n[ERROR] Database problem:")
        print(exc)
        print("\nCheck DATABASE_URL in .env (server name, login, database exists, ODBC driver installed).")
        sys.exit(1)

    print(f"\nAdmin dashboard : http://{settings.HOST}:{settings.PORT}/admin")
    print(f"Shareable links : {settings.BASE_URL}/claim/<event-slug>")
    print("=" * 60 + "\n")

    from app.main import app  # imported after the DB check so failures are readable

    uvicorn.run(app, host=settings.HOST, port=settings.PORT, reload=False, workers=1)


if __name__ == "__main__":
    main()
