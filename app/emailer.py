import smtplib
from email.message import EmailMessage

from .config import settings


def send_otp(to_email: str, name: str, otp: str, event_name: str) -> None:
    if not settings.SMTP_HOST:
        # Dev mode: no SMTP configured, print OTP to the console instead.
        print(f"\n[DEV MODE] OTP for {to_email}: {otp}\n", flush=True)
        return

    msg = EmailMessage()
    msg["Subject"] = f"Your verification code: {otp}"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        f"Hi {name},\n\n"
        f"Your verification code to download your certificate for \"{event_name}\" is:\n\n"
        f"    {otp}\n\n"
        f"It is valid for {settings.OTP_TTL_MINUTES} minutes. "
        f"If you didn't request this, you can ignore this email.\n\n"
        f"- The Data & AI Guild"
    )
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
        s.starttls()
        if settings.SMTP_USER:
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        s.send_message(msg)
