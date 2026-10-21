import csv
import io
import re
import secrets
from datetime import datetime, timedelta

from fastapi import Request

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-']+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def smart_title(name: str) -> str:
    """'praphul  BHARADWAJ' -> 'Praphul Bharadwaj', "anita d'souza" -> "Anita D'Souza"."""
    name = re.sub(r"\s+", " ", str(name)).strip()
    return re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), name.lower())


def normalize_email(email: str) -> str:
    return str(email).strip().lower()


def clean_person_name(raw: str) -> str:
    """Validates a name typed by a participant. Raises ValueError with a friendly message."""
    name = re.sub(r"\s+", " ", str(raw)).strip()
    if len(name) < 2:
        raise ValueError("Please enter your full name.")
    if len(name) > 80:
        raise ValueError("The name is too long (maximum 80 characters).")
    # Latin letters only (the certificate font supports Latin), plus space . ' -
    if not all((ch.isalpha() and ord(ch) < 0x250) or ch in " .'-" for ch in name):
        raise ValueError("Use letters only (A-Z), spaces, dots, hyphens or apostrophes.")
    if name.islower() or name.isupper():
        name = smart_title(name)
    return name


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40].strip("-") or "event"


def make_event_slug(event_name: str) -> str:
    """Readable but unguessable: zero-to-hero-on-ai-agent-observab-3fa91c2b7e"""
    return f"{slugify(event_name)}-{secrets.token_hex(5)}"


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1")


def _read_rows(content: bytes, filename: str) -> list[list]:
    fname = filename.lower()
    if fname.endswith(".csv"):
        text = _decode(content)
        first = text.splitlines()[0] if text.strip() else ""
        delim = max([",", ";", "\t"], key=first.count) if first else ","
        return [row for row in csv.reader(io.StringIO(text), delimiter=delim)]
    if fname.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
        return rows
    raise ValueError("Please upload a .csv or .xlsx file.")


def parse_participants(content: bytes, filename: str):
    """Returns (rows, issues). rows = [(Name, email)], issues = [str]."""
    raw = _read_rows(content, filename)
    rows = [[("" if c is None else str(c).strip()) for c in r] for r in raw]
    rows = [r for r in rows if any(r)]
    if not rows:
        raise ValueError("The file is empty.")

    header = [c.lower() for c in rows[0]]
    has_header = not any("@" in c for c in header)
    name_i = email_i = None
    if has_header:
        for i, c in enumerate(header):
            if name_i is None and "name" in c:
                name_i = i
            if email_i is None and "mail" in c:
                email_i = i
        body, first_line = rows[1:], 2
    else:
        body, first_line = rows, 1
    if name_i is None or email_i is None:
        if max(len(r) for r in rows) < 2:
            raise ValueError("The file needs two columns: name and email.")
        name_i, email_i = 0, 1

    out, issues, seen = [], [], set()
    for n, r in enumerate(body, start=first_line):
        name = smart_title(r[name_i]) if len(r) > name_i else ""
        email = normalize_email(r[email_i]) if len(r) > email_i else ""
        if not name:
            issues.append(f"Row {n}: missing name")
        elif not EMAIL_RE.match(email):
            issues.append(f"Row {n}: invalid email '{email}'")
        elif email in seen:
            issues.append(f"Row {n}: duplicate email '{email}' skipped")
        else:
            seen.add(email)
            out.append((name, email))
    return out, issues


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]


def to_ist(dt: datetime | None) -> str:
    if not dt:
        return "-"
    return (dt + timedelta(hours=5, minutes=30)).strftime("%d %b %Y, %I:%M %p")


def fmt_date(d) -> str:
    return f"{d.day} {d.strftime('%B %Y')}" if d else ""
