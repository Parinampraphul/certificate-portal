from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    """Naive UTC timestamp (everything is stored in UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    event_date: Mapped[date] = mapped_column(Date)       # participation date
    issue_date: Mapped[date] = mapped_column(Date)
    event_format: Mapped[str] = mapped_column(String(100), default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    link_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # the public slug
    link_expires_at: Mapped[datetime] = mapped_column(DateTime)
    link_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    participants: Mapped[list["Participant"]] = relationship(back_populates="event")

    @property
    def slug(self) -> str:
        return self.link_token

    @property
    def link_is_valid(self) -> bool:
        return bool(self.link_active) and utcnow() < self.link_expires_at


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("event_id", "email", name="uq_participant_event_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    name_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    first_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    event: Mapped[Event] = relationship(back_populates="participants")

    @property
    def cert_no(self) -> str:
        return f"GUILD-{self.event_id:03d}-{self.id:04d}"


class CertificateLog(Base):
    """Audit trail: VERIFIED, VERIFY_FAILED, NAME_CHANGED, DOWNLOADED, ADMIN_DOWNLOAD."""

    __tablename__ = "certificate_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    participant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("participants.id"), nullable=True)
    email_entered: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(30))
    detail: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
