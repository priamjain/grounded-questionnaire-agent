"""Deterministic verification. The model's self-report is never trusted alone.

A quote counts as grounded only if it appears as a literal substring of the
policy corpus after normalizing whitespace and case. That substring check is
the authority: if it fails, the row escalates and the answer is discarded.
"""
import hashlib
import re
import unicodedata

CONFIDENCE_FLOOR = 0.7
MIN_QUOTE_CHARS = 12

# Instruction-shaped text in a question is an injection attempt, not a question.
INJECTION_PATTERNS = [
    r"\bignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\b",
    r"\bdisregard\s+(all\s+|any\s+)?(previous|prior|above|earlier|instructions)\b",
    r"\b(system|developer)\s+prompt\b",
    r"\byou\s+are\s+now\b",
    r"\bact\s+as\s+(a|an|if)\b",
    r"\bpretend\s+(to\s+be|that)\b",
    r"\bnew\s+instructions?\b",
    r"\boverride\s+(your|the|all)\b",
    r"\breveal\s+(your|the)\s+(prompt|instructions|system)\b",
    r"\boutput\s+(your|the)\s+(prompt|instructions)\b",
    r"</?(system|instructions?|untrusted_input)>",
    r"\bjailbreak\b",
    r"\bDAN\b",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def normalize(text: str) -> str:
    """Casefold, collapse whitespace, and flatten smart quotes and dashes."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip().casefold()


def quote_is_grounded(quote: str, corpus: str) -> bool:
    """Literal substring check against the normalized corpus."""
    if not quote or len(quote.strip()) < MIN_QUOTE_CHARS:
        return False
    return normalize(quote) in normalize(corpus)


def looks_like_injection(question: str) -> bool:
    return bool(_INJECTION_RE.search(question))


def row_key(run_id: str, question: str) -> str:
    return hashlib.sha256(f"{run_id}{normalize(question)}".encode()).hexdigest()


_SOURCE_RE = re.compile(r"^--- SOURCE: (.+?) ---$", re.M)


def locate_source(quote: str, corpus: str) -> str:
    """Which source the quote came from, using the same substring rule.

    Returns "" when the corpus is unlabelled or the quote straddles two
    sections — better to show no attribution than the wrong one.
    """
    marks = list(_SOURCE_RE.finditer(corpus))
    if not marks:
        return ""
    needle = normalize(quote)
    if not needle:
        return ""
    hits = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(corpus)
        if needle in normalize(corpus[mark.end():end]):
            hits.append(mark.group(1).strip())
    return hits[0] if len(hits) == 1 else ""


def verify(claim: dict, corpus: str) -> tuple[str, str]:
    """Decide the row's status from the model's claim.

    Returns (status, reason). ANSWERED only if the model claimed grounding,
    cleared the confidence floor, AND the quote is really in the corpus.
    """
    quote = (claim.get("source_quote") or "").strip()
    answer = (claim.get("answer") or "").strip()
    grounded = bool(claim.get("grounded"))
    try:
        confidence = float(claim.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    if not answer:
        return "ESCALATE", "The model returned no answer."
    if not grounded:
        return "ESCALATE", "The model reported it could not ground this in the sources."
    if confidence < CONFIDENCE_FLOOR:
        return "ESCALATE", f"Confidence {confidence:.2f} is below the {CONFIDENCE_FLOOR} floor."
    if not quote_is_grounded(quote, corpus):
        return (
            "ESCALATE",
            "The cited quote does not appear verbatim in the policy sources.",
        )
    return "ANSWERED", ""
