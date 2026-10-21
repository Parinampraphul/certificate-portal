# Guild Certificates

Admin uploads a participant list, shares one link. Participants enter their email, check their name (one correction allowed), download the PDF.

## Run
1. `python -m venv .venv` then `.venv\Scripts\activate`
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in DATABASE_URL, ADMIN_PASSWORD, SECRET_KEY, BASE_URL.
4. `python run.py` (checks SQL Server, creates/updates tables, starts the server)
5. Open http://127.0.0.1:8000/admin

## Public link
`BASE_URL/claim/<event-slug>` (copy it from the event page). Valid for 48 hours by default; extend or disable any time.

## Certificate design
- Background (with logo, signatories, Sparity): `app/static/assets/certificate_bg.png`
- Text positions and sizes: top of `app/certificate.py`
