import time
from collections import defaultdict, deque
from io import BytesIO

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import CertificateLog, Event, Participant, utcnow
from ..pdf_service import render_certificate_pdf
from ..templating import templates
from ..utils import clean_person_name, client_ip, normalize_email

router = APIRouter()

# Simple in-memory brake against guessing emails (single-process app).
_fails: dict[str, deque] = defaultdict(deque)


def _too_many_fails(ip: str) -> bool:
    q = _fails[ip]
    cutoff = time.time() - settings.LOOKUP_WINDOW_SECONDS
    while q and q[0] < cutoff:
        q.popleft()
    return len(q) >= settings.LOOKUP_MAX_FAILS


def _log(db, request, event_id, action, participant_id=None, email=None, detail=None):
    db.add(CertificateLog(
        event_id=event_id, participant_id=participant_id, email_entered=(email or None)[:255] if email else None,
        action=action, detail=(detail or None) and detail[:255],
        ip=client_ip(request), user_agent=request.headers.get("user-agent", "")[:400]))
    db.commit()


def _message(request, title, text, status=200):
    return templates.TemplateResponse(request, "message.html", {"title": title, "text": text}, status_code=status)


def _event_state(request, db, slug):
    """Returns (event, error_response). error_response is None when the link is usable."""
    event = db.scalar(select(Event).where(Event.link_token == slug))
    if not event:
        return None, _message(request, "Invalid link", "This link is not valid. Please check the link you were given.", 404)
    if not event.link_is_valid:
        return None, _message(request, "Link expired",
                              "This certificate link is no longer active. Please contact the Community Manager.", 410)
    return event, None


def _page(request, event, step="email", participant=None, error=None, email="", form_name=None, status=200):
    return templates.TemplateResponse(request, "claim.html", {
        "event": event, "slug": event.link_token, "step": step, "participant": participant,
        "error": error, "email": email, "form_name": form_name if form_name is not None else (participant.name if participant else ""),
    }, status_code=status)


def _session_participant(request, db, event):
    pid = request.session.get(f"claim:{event.link_token}")
    if not pid:
        return None
    p = db.get(Participant, pid)
    return p if p and p.event_id == event.id else None


@router.get("/")
def home(request: Request):
    return _message(request, "The Data & AI Guild",
                    "Certificates are issued through the link shared in the community channel.")


@router.get("/claim/{event_slug}")
def claim_page(event_slug: str, request: Request, db: Session = Depends(get_db)):
    event, err = _event_state(request, db, event_slug)
    if err:
        return err
    p = _session_participant(request, db, event)
    if p:
        return _page(request, event, step="preview", participant=p)
    return _page(request, event)


@router.post("/claim/{event_slug}")
def check_email(event_slug: str, request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    event, err = _event_state(request, db, event_slug)
    if err:
        return err
    ip = client_ip(request)
    if _too_many_fails(ip):
        return _page(request, event, error="Too many attempts. Please wait a few minutes and try again.", status=429)

    clean = normalize_email(email)
    p = db.scalar(select(Participant).where(Participant.event_id == event.id, Participant.email == clean))
    if not p:
        _fails[ip].append(time.time())
        _log(db, request, event.id, "VERIFY_FAILED", email=clean, detail="email not in list")
        return _page(request, event, email=clean,
                     error="This email is not on the list for this event. Use the email you registered with, "
                           "or contact the Community Manager.")

    request.session[f"claim:{event.link_token}"] = p.id
    _log(db, request, event.id, "VERIFIED", p.id, clean)
    return RedirectResponse(f"/claim/{event.link_token}", status_code=303)


@router.get("/claim/{event_slug}/switch")
def switch_user(event_slug: str, request: Request):
    request.session.pop(f"claim:{event_slug}", None)
    return RedirectResponse(f"/claim/{event_slug}", status_code=303)


@router.post("/claim/{event_slug}/download")
def download_certificate(event_slug: str, request: Request, full_name: str = Form(""),
                         db: Session = Depends(get_db)):
    event, err = _event_state(request, db, event_slug)
    if err:
        return err
    p = _session_participant(request, db, event)
    if not p:
        return RedirectResponse(f"/claim/{event_slug}", status_code=303)

    old_name = p.name
    final_name = p.name
    if not p.name_locked:  # one chance to correct the name
        try:
            final_name = clean_person_name(full_name or p.name)
        except ValueError as exc:
            return _page(request, event, step="preview", participant=p, error=str(exc), form_name=full_name, status=400)

    try:
        pdf = render_certificate_pdf(name=final_name, event=event, participant=p)
    except Exception as exc:  # nothing is locked if generation fails
        _log(db, request, event.id, "GENERATE_FAILED", p.id, p.email, detail=str(exc))
        return _message(request, "Something went wrong",
                        "We couldn't generate your certificate. Please try again or contact the Community Manager.", 500)

    now = utcnow()
    if not p.name_locked:
        p.name = final_name
        p.name_locked = True
    p.download_count = (p.download_count or 0) + 1
    p.first_generated_at = p.first_generated_at or now
    p.last_downloaded_at = now
    db.add(CertificateLog(event_id=event.id, participant_id=p.id, email_entered=p.email, action="DOWNLOADED",
                          detail=(f"name corrected: {old_name} -> {final_name}" if final_name != old_name else "name unchanged")[:255],
                          ip=client_ip(request), user_agent=request.headers.get("user-agent", "")[:400]))
    db.commit()

    safe = "".join(ch for ch in final_name if ch.isalnum() or ch in " -_").strip().replace(" ", "_") or "certificate"
    return StreamingResponse(BytesIO(pdf), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="Certificate_{safe}.pdf"',
        "Content-Length": str(len(pdf)),
        "Cache-Control": "no-store"})
