import secrets

from fastapi import Request

from .config import settings


class NotAdmin(Exception):
    pass


def require_admin(request: Request):
    if not request.session.get("admin"):
        raise NotAdmin()


def check_admin_credentials(username: str, password: str) -> bool:
    ok_user = secrets.compare_digest(username.encode(), settings.ADMIN_USERNAME.encode())
    ok_pass = secrets.compare_digest(password.encode(), settings.ADMIN_PASSWORD.encode())
    return ok_user and ok_pass
