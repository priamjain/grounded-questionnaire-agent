"""FastAPI app: API routes plus the built frontend served as static files."""
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, config

app = FastAPI(title="Grounded Questionnaire Agent", docs_url=None, redoc_url=None)
app.middleware("http")(auth.session_middleware)


class LoginBody(BaseModel):
    username: str
    password: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
def login(body: LoginBody):
    if not auth.check_credentials(body.username, body.password):
        return JSONResponse({"detail": "Invalid username or password"}, status_code=401)
    response = JSONResponse({"username": body.username})
    auth.set_session_cookie(response, body.username)
    return response


@app.post("/api/logout")
def logout():
    response = JSONResponse({"ok": True})
    auth.clear_session_cookie(response)
    return response


@app.get("/api/me")
def me(request: Request):
    return {"username": request.state.username}


def mount_static() -> None:
    """Serve the Vite build, with SPA fallback to index.html."""
    assets = config.STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        index = config.STATIC_DIR / "index.html"
        if not index.exists():
            return JSONResponse(
                {"detail": "frontend not built; run `make build`"}, status_code=404
            )
        return FileResponse(index)


mount_static()
