from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import CertificateLog, Event, Participant, utcnow
from ..pdf_service import render_certificate_pdf
from ..security import check_admin_credentials, require_admin
from ..templating import templates
from ..utils import client_ip, make_event_slug, normalize_email, parse_participants

router = APIRouter(prefix="/admin")


def _go(path: str):
    return RedirectResponse(path, status_code=303)


# ---------------- auth ----------------
@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {"error": None})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if check_admin_credentials(username, password):
        request.session.clear()
        request.session["admin"] = True
        return _go("/admin")
    return templates.TemplateResponse(request, "admin_login.html", {"error": "Wrong username or password."},
                                      status_code=401)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return _go("/admin/login")


# ---------------- dashboard ----------------
def _stats(db: Session) -> dict:
    rows = db.execute(
        select(
            Participant.event_id,
            func.count(),
            func.sum(case((Participant.download_count > 0, 1), else_=0)),
            func.coalesce(func.sum(Participant.download_count), 0),
        ).group_by(Participant.event_id)).all()
    return {r[0]: {"total": r[1], "claimed": int(r[2] or 0), "downloads": int(r[3] or 0)} for r in rows}


def _dashboard(request, db, error=None, issues=None, form=None, status=200):
    events = db.scalars(select(Event).order_by(Event.id.desc())).all()
    return templates.TemplateResponse(request, "admin_dashboard.html", {
        "events": events, "stats": _stats(db), "error": error, "issues": issues or [], "form": form or {},
        "today": date.today().isoformat(), "default_hours": settings.DEFAULT_LINK_HOURS,
        "flash": request.session.pop("flash", None),
    }, status_code=status)


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db), _=Depends(require_admin)):
    return _dashboard(request, db)


# ---------------- events: create / read / update / delete ----------------
@router.post("/events")
async def create_event(
    request: Request,
    name: str = Form(...),
    event_date: str = Form(...),
    issue_date: str = Form(...),
    event_format: str = Form(""),
    location: str = Form(""),
    valid_hours: int = Form(48),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    form = {"name": name, "event_date": event_date, "issue_date": issue_date,
            "event_format": event_format, "location": location, "valid_hours": valid_hours}
    rows, issues = [], []
    if file is not None and file.filename:
        try:
            rows, issues = parse_participants(await file.read(), file.filename)
        except Exception as exc:
            return _dashboard(request, db, error=str(exc), form=form, status=400)
        if not rows:
            return _dashboard(request, db, error="No valid participants found in the file.", issues=issues,
                              form=form, status=400)
    try:
        ev_date, is_date = date.fromisoformat(event_date), date.fromisoformat(issue_date)
    except ValueError:
        return _dashboard(request, db, error="Please enter valid dates.", form=form, status=400)

    event = Event(name=name.strip(), event_date=ev_date, issue_date=is_date,
                  event_format=event_format.strip(), location=location.strip(),
                  link_token=make_event_slug(name), link_expires_at=utcnow() + timedelta(hours=max(valid_hours, 1)),
                  link_active=True)
    db.add(event)
    db.flush()
    db.add_all([Participant(event_id=event.id, name=n, email=e) for n, e in rows])
    db.commit()
    msg = f"Event created with {len(rows)} participants."
    if issues:
        msg += f" {len(issues)} rows skipped: " + "; ".join(issues[:10])
    request.session["flash"] = msg
    return _go(f"/admin/events/{event.id}")


@router.get("/events/{event_id}")
def event_detail(event_id: int, request: Request, db: Session = Depends(get_db), _=Depends(require_admin)):
    event = db.get(Event, event_id)
    if not event:
        return _go("/admin")
    participants = db.scalars(select(Participant).where(Participant.event_id == event_id)
                              .order_by(Participant.name)).all()
    logs = db.execute(
        select(CertificateLog, Participant.name)
        .join(Participant, Participant.id == CertificateLog.participant_id, isouter=True)
        .where(CertificateLog.event_id == event_id)
        .order_by(CertificateLog.id.desc()).limit(200)).all()
    return templates.TemplateResponse(request, "admin_event.html", {
        "event": event, "participants": participants, "logs": logs,
        "stats": _stats(db).get(event_id, {"total": 0, "claimed": 0, "downloads": 0}),
        "link": f"{settings.BASE_URL}/claim/{event.link_token}",
        "flash": request.session.pop("flash", None),
        "default_hours": settings.DEFAULT_LINK_HOURS,
    })


@router.post("/events/{event_id}/edit")
def edit_event(event_id: int, request: Request, name: str = Form(...), event_date: str = Form(...),
               issue_date: str = Form(...), event_format: str = Form(""), location: str = Form(""),
               db: Session = Depends(get_db), _=Depends(require_admin)):
    event = db.get(Event, event_id)
    if not event:
        return _go("/admin")
    try:
        event.event_date, event.issue_date = date.fromisoformat(event_date), date.fromisoformat(issue_date)
    except ValueError:
        request.session["flash"] = "Invalid date, nothing was changed."
        return _go(f"/admin/events/{event_id}")
    event.name, event.event_format, event.location = name.strip(), event_format.strip(), location.strip()
    db.commit()
    request.session["flash"] = "Event updated. Names already downloaded are not affected."
    return _go(f"/admin/events/{event_id}")


@router.post("/events/{event_id}/delete")
def delete_event(event_id: int, request: Request, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.get(Event, event_id):
        db.execute(delete(CertificateLog).where(CertificateLog.event_id == event_id))
        db.execute(delete(Participant).where(Participant.event_id == event_id))
        db.execute(delete(Event).where(Event.id == event_id))
        db.commit()
        request.session["flash"] = "Event deleted."
    return _go("/admin")


# ---------------- link control ----------------
@router.post("/events/{event_id}/extend")
def extend_link(event_id: int, hours: int = Form(48), db: Session = Depends(get_db), _=Depends(require_admin)):
    event = db.get(Event, event_id)
    if event:
        event.link_expires_at = utcnow() + timedelta(hours=max(hours, 1))
        event.link_active = True
        db.commit()
    return _go(f"/admin/events/{event_id}")


@router.post("/events/{event_id}/disable")
def disable_link(event_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    event = db.get(Event, event_id)
    if event:
        event.link_active = False
        db.commit()
    return _go(f"/admin/events/{event_id}")


# ---------------- participants ----------------
@router.post("/events/{event_id}/participants/upload")
async def upload_participants(event_id: int, request: Request, file: UploadFile = File(...),
                              db: Session = Depends(get_db), _=Depends(require_admin)):
    event = db.get(Event, event_id)
    if not event:
        return _go("/admin")
    try:
        rows, issues = parse_participants(await file.read(), file.filename or "")
    except Exception as exc:
        request.session["flash"] = f"Upload failed: {exc}"
        return _go(f"/admin/events/{event_id}")
    existing = set(db.scalars(select(Participant.email).where(Participant.event_id == event_id)).all())
    new = [(n, e) for n, e in rows if e not in existing]
    db.add_all([Participant(event_id=event_id, name=n, email=e) for n, e in new])
    db.commit()
    skipped = len(rows) - len(new)
    msg = f"{len(new)} participants added."
    if skipped:
        msg += f" {skipped} already existed."
    if issues:
        msg += f" {len(issues)} rows skipped: " + "; ".join(issues[:10])
    request.session["flash"] = msg
    return _go(f"/admin/events/{event_id}")


@router.post("/events/{event_id}/participants/add")
def add_participant(event_id: int, request: Request, name: str = Form(...), email: str = Form(...),
                    db: Session = Depends(get_db), _=Depends(require_admin)):
    from ..utils import EMAIL_RE, smart_title
    clean = normalize_email(email)
    if not db.get(Event, event_id) or not name.strip() or not EMAIL_RE.match(clean):
        request.session["flash"] = "Enter a valid name and email."
    elif db.scalar(select(Participant).where(Participant.event_id == event_id, Participant.email == clean)):
        request.session["flash"] = "That email is already in this event."
    else:
        db.add(Participant(event_id=event_id, name=smart_title(name), email=clean))
        db.commit()
        request.session["flash"] = "Participant added."
    return _go(f"/admin/events/{event_id}")


@router.post("/events/{event_id}/participants/{pid}/unlock")
def unlock_name(event_id: int, pid: int, request: Request, db: Session = Depends(get_db), _=Depends(require_admin)):
    p = db.get(Participant, pid)
    if p and p.event_id == event_id:
        p.name_locked = False
        db.commit()
        request.session["flash"] = f"Name unlocked for {p.name}."
    return _go(f"/admin/events/{event_id}")


@router.post("/events/{event_id}/participants/{pid}/delete")
def delete_participant(event_id: int, pid: int, request: Request, db: Session = Depends(get_db),
                       _=Depends(require_admin)):
    p = db.get(Participant, pid)
    if p and p.event_id == event_id:
        db.execute(delete(CertificateLog).where(CertificateLog.participant_id == pid))
        db.delete(p)
        db.commit()
        request.session["flash"] = "Participant removed."
    return _go(f"/admin/events/{event_id}")


@router.get("/events/{event_id}/certificate/{pid}")
def admin_download(event_id: int, pid: int, request: Request, db: Session = Depends(get_db),
                   _=Depends(require_admin)):
    """Hand a certificate over manually (does not lock the participant's name)."""
    p = db.get(Participant, pid)
    if not p or p.event_id != event_id:
        return _go(f"/admin/events/{event_id}")
    pdf = render_certificate_pdf(name=p.name, event=p.event, participant=p)
    db.add(CertificateLog(event_id=event_id, participant_id=p.id, email_entered=p.email, action="ADMIN_DOWNLOAD",
                          ip=client_ip(request), user_agent=request.headers.get("user-agent", "")[:400]))
    db.commit()
    safe = "".join(ch for ch in p.name if ch.isalnum() or ch in " -_").strip().replace(" ", "_") or "certificate"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Certificate_{safe}.pdf"'})
