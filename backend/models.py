"""Shared shapes for a run and its rows. Plain dicts on the wire."""
from dataclasses import asdict, dataclass, field
from typing import Literal

Status = Literal["ANSWERED", "ESCALATE", "BLOCKED"]


@dataclass
class Row:
    key: str  # sha256(run_id + normalized question) — the idempotency key
    question: str
    status: Status
    answer: str = ""
    source_quote: str = ""
    confidence: float = 0.0
    reason: str = ""  # why it escalated or was blocked

    def dict(self) -> dict:
        return asdict(self)


@dataclass
class Run:
    run_id: str
    created_at: str
    email: str
    source_urls: list[str]
    questions: list[str]
    status: Literal["running", "done", "error"] = "running"
    rows: list[Row] = field(default_factory=list)
    error: str = ""
    email_sent_at: str = ""
    source_chars: int = 0

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "total": len(self.questions),
            "status": self.status,
        }

    def dict(self) -> dict:
        d = asdict(self)
        d["rows"] = [r.dict() for r in self.rows]
        return d


def tally(rows: list[Row]) -> dict:
    return {
        "answered": sum(1 for r in rows if r.status == "ANSWERED"),
        "escalated": sum(1 for r in rows if r.status == "ESCALATE"),
        "blocked": sum(1 for r in rows if r.status == "BLOCKED"),
    }
