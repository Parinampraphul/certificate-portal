"""Draws the dynamic text on top of certificate_bg.png (A4 landscape).

The static branding is part of certificate_bg.png itself.
"""
from io import BytesIO
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .utils import fmt_date

BASE = Path(__file__).resolve().parent
BG_PATH = BASE / "static" / "assets" / "certificate_bg.png"
FONT_DIR = BASE / "static" / "fonts"

W, H = landscape(A4)
K = W / 1308  # all positions below are in a 1308px-wide design space


def _register_fonts() -> dict:
    fonts = {}
    for key, file, fallback in [
        ("regular", "Montserrat-Regular.ttf", "Helvetica"),
        ("semibold", "Montserrat-SemiBold.ttf", "Helvetica-Bold"),
    ]:
        path = FONT_DIR / file
        if path.exists():
            name = f"Mont-{key}"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))
            fonts[key] = name
        else:
            fonts[key] = fallback
    return fonts


FONTS = _register_fonts()

# ---- Layout (px in the 1308-wide design space; y measured from the top) ----
NAME_BASELINE_Y, NAME_SIZE, NAME_MAX_W, NAME_MIN = 553, 52, 860, 12
EVENT_BASELINE_Y, EVENT_SIZE, EVENT_MAX_W, EVENT_MIN = 643, 24, 900, 10
DETAILS_BASELINE_Y, DETAILS_SIZE, DETAILS_MAX_W = 681, 14.5, 950
FOOTER_BASELINE_Y, FOOTER_SIZE = 866, 12


def _fit(text, font, size, max_w, min_size):
    """Largest font size (px) <= size at which the text fits max_w; never below min_size."""
    while size > min_size and pdfmetrics.stringWidth(text, font, size * K) > max_w * K:
        size -= 0.5
    return size


def _centered(c, text, font, size, y, color):
    c.setFont(font, size * K)
    c.setFillColor(HexColor(color))
    c.drawCentredString(W / 2, H - y * K, text)


def generate_certificate(*, name, event_name, cert_no, issue_date, event_date,
                         event_format="", location="") -> bytes:
    if not BG_PATH.exists():
        raise FileNotFoundError(f"Certificate background not found: {BG_PATH}")

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"Certificate of Participation - {name}")
    c.setAuthor("The Data & AI Guild")
    c.drawImage(str(BG_PATH), 0, 0, width=W, height=H)

    size = _fit(name, FONTS["semibold"], NAME_SIZE, NAME_MAX_W, NAME_MIN)
    _centered(c, name, FONTS["semibold"], size, NAME_BASELINE_Y, "#6A0F5C")

    size = _fit(event_name, FONTS["semibold"], EVENT_SIZE, EVENT_MAX_W, EVENT_MIN)
    _centered(c, event_name, FONTS["semibold"], size, EVENT_BASELINE_Y, "#333333")

    parts = [f"Participation Date: {fmt_date(event_date)}"]
    if event_format:
        parts.append(f"Format: {event_format}")
    if location:
        parts.append(f"Location: {location}")
    details = "   |   ".join(parts)
    size = _fit(details, FONTS["regular"], DETAILS_SIZE, DETAILS_MAX_W, 8)
    _centered(c, details, FONTS["regular"], size, DETAILS_BASELINE_Y, "#555555")

    footer = f"Issued on {fmt_date(issue_date)}   \u2022   Certificate ID: {cert_no}"
    _centered(c, footer, FONTS["regular"], FOOTER_SIZE, FOOTER_BASELINE_Y, "#777777")

    c.showPage()
    c.save()
    return buf.getvalue()
