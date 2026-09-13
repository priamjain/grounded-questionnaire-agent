"""Environment configuration with fail-fast validation at import time."""
import os
import sys
from pathlib import Path

REQUIRED = [
    "APP_USERNAME",
    "APP_PASSWORD",
    "SESSION_SECRET",
    "ANTHROPIC_API_KEY",
    "RESEND_API_KEY",
]

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RUNS_FILE = DATA_DIR / "runs.jsonl"
STATIC_DIR = Path(__file__).resolve().parent / "static"

MODEL = "claude-sonnet-4-6"
SESSION_COOKIE = "qa_session"
SESSION_MAX_AGE = 12 * 60 * 60  # 12 hours

def _load_dotenv() -> None:
    """Minimal .env loader. Existing environment always wins."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load() -> dict:
    _load_dotenv()
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        sys.stderr.write(
            "\nFATAL: missing required environment variables:\n"
            + "".join(f"  - {k}\n" for k in missing)
            + "\nCopy .env.example to .env and fill these in, then restart.\n\n"
        )
        raise SystemExit(1)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return {k: os.environ[k] for k in REQUIRED}


SETTINGS = load()

# Read after load() so a value in .env counts. Set COOKIE_SECURE=1 when the app
# is served over HTTPS (behind CloudFront); off by default so local HTTP works.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "").strip() in {"1", "true", "yes"}
