from pathlib import Path

from fastapi.templating import Jinja2Templates

from .utils import fmt_date, to_ist

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
templates.env.filters["ist"] = to_ist
templates.env.filters["pdate"] = fmt_date
