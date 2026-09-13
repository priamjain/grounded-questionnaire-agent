"""Cookie session auth. One user, from env, no user table."""
import secrets
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import config

_serializer = URLSafeTimedSerializer(
    config.SETTINGS["SESSION_SECRET"], salt="questionnaire-session"
)

# Routes reachable without a session.
PUBLIC_PATHS = {"/health", "/api/login"}


def check_credentials(username: str, password: str) -> bool:
    """Constant-time compare against both env credentials."""
    user_ok = secrets.compare_digest(username, config.SETTINGS["APP_USERNAME"])
    pass_ok = secrets.compare_digest(password, config.SETTINGS["APP_PASSWORD"])
    return user_ok and pass_ok


def issue_token(username: str) -> str:
    return _serializer.dumps({"u": username, "iat": int(time.time())})


def read_token(token: str) -> str | None:
    """Return the username, or None if the cookie is missing/tampered/expired."""
    try:
        data = _serializer.loads(token, max_age=config.SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("u")


def set_session_cookie(response: JSONResponse, username: str) -> None:
    response.set_cookie(
        config.SESSION_COOKIE,
        issue_token(username),
        max_age=config.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: JSONResponse) -> None:
    response.delete_cookie(config.SESSION_COOKIE, path="/")


async def session_middleware(request: Request, call_next):
    """Guard every /api route except the public ones."""
    path = request.url.path
    if path.startswith("/api") and path not in PUBLIC_PATHS:
        token = request.cookies.get(config.SESSION_COOKIE)
        username = read_token(token) if token else None
        if not username:
            return JSONResponse({"detail": "not authenticated"}, status_code=401)
        request.state.username = username
    return await call_next(request)
