import secrets
import time
from threading import Lock

from pwdlib import PasswordHash
from sqlalchemy import select

from app.contracts import ErrorCode
from app.database import transaction
from app.errors import ApiError
from app.models.schema import admins, tenants

COOKIE = "certificate_admin_session"
passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("unused-password")


class Sessions:
    def __init__(self, ttl):
        self.ttl = ttl
        self.tokens = {}
        self.lock = Lock()

    def create(self, admin_id):
        token = secrets.token_urlsafe(32)
        with self.lock:
            now = time.monotonic()
            self.tokens = {k: v for k, v in self.tokens.items() if v[1] > now}
            self.tokens[token] = (admin_id, now + self.ttl)
        return token

    def remove(self, token):
        with self.lock:
            self.tokens.pop(token, None)

    def resolve(self, token):
        with self.lock:
            value = self.tokens.get(token)
            if value and value[1] > time.monotonic():
                return value[0]
            self.tokens.pop(token, None)
        raise ApiError(401, ErrorCode.UNAUTHORIZED, "Please log in.")


def identity(connection, admin_id):
    admin = connection.execute(select(admins).where(admins.c.id == admin_id)).mappings().first()
    if admin is None:
        raise ApiError(401, ErrorCode.UNAUTHORIZED, "Please log in.")
    tenant = (
        connection.execute(select(tenants).where(tenants.c.id == admin["tenant_id"]))
        .mappings()
        .one()
    )
    return {"admin": {k: admin[k] for k in ("id", "username", "name")}, "tenant": dict(tenant)}


def current(request):
    admin_id = request.app.state.sessions.resolve(request.cookies.get(COOKIE))
    with transaction(request.app.state.engine) as connection:
        return identity(connection, admin_id)


def login(request, body, response):
    with transaction(request.app.state.engine) as connection:
        admin = (
            connection.execute(select(admins).where(admins.c.username == body.username))
            .mappings()
            .first()
        )
        valid = passwords.verify(body.password, admin["password_hash"] if admin else DUMMY_HASH)
        if not admin or not valid:
            raise ApiError(401, ErrorCode.INVALID_CREDENTIALS, "Invalid username or password.")
        result = identity(connection, admin["id"])
    request.app.state.sessions.remove(request.cookies.get(COOKIE))
    token = request.app.state.sessions.create(admin["id"])
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=request.app.state.cookie_secure or request.url.scheme == "https",
        path="/",
        max_age=request.app.state.sessions.ttl,
    )
    return result
