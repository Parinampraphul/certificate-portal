from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import init_db
from .routers import admin, public
from .security import NotAdmin
from .templating import templates

BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # idempotent: creates tables / adds missing columns
    yield


app = FastAPI(title="Guild Certificates", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=8 * 3600,
    same_site="lax",
    https_only=settings.BASE_URL.startswith("https"),
)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.exception_handler(NotAdmin)
async def not_admin_handler(request: Request, exc: NotAdmin):
    return RedirectResponse("/admin/login", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    titles = {404: "Page not found", 405: "Not allowed"}
    return templates.TemplateResponse(
        request, "message.html",
        {"title": titles.get(exc.status_code, "Something went wrong"),
         "text": "Please check the link and try again."},
        status_code=exc.status_code)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}


app.include_router(admin.router)
app.include_router(public.router)
