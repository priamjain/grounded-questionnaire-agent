"""In-memory run state, mirrored to ./data/runs.jsonl so restarts keep history.

The dict is the source of truth while the process is alive; the file is an
append-only log replayed at startup. Last line for a run_id wins.
"""
import json
import threading

from . import config
from .models import Row, Run

_runs: dict[str, Run] = {}
_lock = threading.Lock()


def _append(run: Run) -> None:
    with config.RUNS_FILE.open("a") as fh:
        fh.write(json.dumps(run.dict()) + "\n")


def load_from_disk() -> None:
    """Replay the log. A corrupt trailing line (killed mid-write) is skipped."""
    if not config.RUNS_FILE.exists():
        return
    for line in config.RUNS_FILE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows = [Row(**r) for r in data.pop("rows", [])]
        _runs[data["run_id"]] = Run(**data, rows=rows)


def put(run: Run) -> None:
    with _lock:
        _runs[run.run_id] = run
        _append(run)


def checkpoint(run: Run) -> None:
    """Persist the current state of an already-registered run."""
    with _lock:
        _append(run)


def get(run_id: str) -> Run | None:
    return _runs.get(run_id)


def list_runs() -> list[Run]:
    return sorted(_runs.values(), key=lambda r: r.created_at, reverse=True)
