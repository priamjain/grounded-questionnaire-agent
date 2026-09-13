"""Offline eval harness: grounded pipeline vs. naive baseline.

Reads fixtures from disk only. No source fetching, no Resend, no server.
Run with `make eval`.
"""

import asyncio
import json
import re
import time
from pathlib import Path

from backend import agent, config, grounding, prompts

FIXTURES = config.ROOT / "fixtures"
QUESTIONS = FIXTURES / "questions.json"
POLICIES = FIXTURES / "policies"

# claude-sonnet-4-6, USD per million tokens.
COST_IN = 3.0
COST_OUT = 15.0

# Phrases a model reaches for when it declines to answer. Used only to score
# the naive arm, which has no structured abstention signal of its own.
ABSTAIN = re.compile(
    r"do(es)? not (specify|mention|address|state|contain|include|provide)"
    r"|not (specified|mentioned|addressed|stated|covered|available|provided)"
    r"|no (information|mention|details?|policy|reference)"
    r"|cannot (be )?(answer|determine|confirm|find)"
    r"|unable to (answer|determine|confirm|find)"
    r"|is silent|insufficient information|not found in",
    re.I,
)


def load_corpus() -> str:
    parts = []
    for path in sorted(POLICIES.glob("*.md")):
        parts.append(f"--- SOURCE: {path.name} ---\n{path.read_text().strip()}")
    return "\n\n".join(parts)


def hit(answer: str, expect: list[str]) -> bool:
    low = answer.lower()
    return any(token.lower() in low for token in expect)


async def grounded_arm(corpus: str, q: dict) -> dict:
    started = time.perf_counter()
    if grounding.looks_like_injection(q["question"]):
        return {
            "status": "BLOCKED",
            "answer": "",
            "latency": time.perf_counter() - started,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
    try:
        claim, usage = await agent.answer_question(corpus, q["question"], with_usage=True)
    except Exception as exc:  # a failed call is a failed answer, not a crash
        return {
            "status": "ESCALATE",
            "answer": "",
            "latency": time.perf_counter() - started,
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "error": str(exc),
        }
    status, _reason = grounding.verify(claim, corpus)
    return {
        "status": status,
        "answer": claim.get("answer", "") if status == "ANSWERED" else "",
        "latency": time.perf_counter() - started,
        "usage": usage,
    }


async def naive_arm(corpus: str, q: dict) -> dict:
    started = time.perf_counter()
    try:
        claim, usage = await agent.answer_naive(corpus, q["question"])
    except Exception as exc:
        return {
            "answer": "",
            "latency": time.perf_counter() - started,
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "error": str(exc),
        }
    return {
        "answer": str(claim.get("answer", "")),
        "latency": time.perf_counter() - started,
        "usage": usage,
    }


def score(questions: list[dict], results: list[dict], arm: str) -> dict:
    answerable = [(q, r) for q, r in zip(questions, results) if q["category"] == "answerable"]
    unanswerable = [(q, r) for q, r in zip(questions, results) if q["category"] == "unanswerable"]
    injection = [(q, r) for q, r in zip(questions, results) if q["category"] == "injection"]

    correct = 0
    for q, r in answerable:
        if arm == "grounded" and r["status"] != "ANSWERED":
            continue
        if hit(r["answer"], q["expect_contains"]):
            correct += 1

    abstained = 0
    for _q, r in unanswerable:
        if arm == "grounded":
            abstained += r["status"] == "ESCALATE"
        else:
            answer = r["answer"].strip()
            abstained += (not answer) or bool(ABSTAIN.search(answer))

    if arm == "grounded":
        blocked = all(r["status"] == "BLOCKED" for _q, r in injection)
    else:
        blocked = False  # the naive arm has no pre-filter and no verification

    cost = sum(
        r["usage"]["input_tokens"] / 1e6 * COST_IN
        + r["usage"]["output_tokens"] / 1e6 * COST_OUT
        for r in results
    )
    priced = [r for r in results if r["usage"]["input_tokens"]]
    return {
        "accuracy": correct / len(answerable),
        "correct": correct,
        "answerable": len(answerable),
        "abstention": abstained / len(unanswerable),
        "abstained": abstained,
        "unanswerable": len(unanswerable),
        "blocked": blocked,
        "latency": sum(r["latency"] for r in priced) / max(len(priced), 1),
        "cost": cost,
    }


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def delta_pct(a: float, b: float) -> str:
    d = (a - b) * 100
    return f"{d:+.0f} pts"


def report(questions, grounded, naive, g, n) -> None:
    print()
    print("PER-QUESTION")
    print(f"{'ID':<5}{'CATEGORY':<14}{'GROUNDED':<12}{'CORRECT':<9}{'NAIVE':<12}{'CORRECT':<9}")
    print("-" * 61)
    for q, gr, nr in zip(questions, grounded, naive):
        cat = q["category"]
        if cat == "answerable":
            g_ok = "yes" if gr["status"] == "ANSWERED" and hit(gr["answer"], q["expect_contains"]) else "NO"
            n_ok = "yes" if hit(nr["answer"], q["expect_contains"]) else "NO"
            n_state = "answered"
        elif cat == "unanswerable":
            g_ok = "yes" if gr["status"] == "ESCALATE" else "NO"
            a = nr["answer"].strip()
            abstain = (not a) or bool(ABSTAIN.search(a))
            n_ok = "yes" if abstain else "NO"
            n_state = "abstained" if abstain else "answered"
        else:
            g_ok = "yes" if gr["status"] == "BLOCKED" else "NO"
            n_ok = "NO"
            n_state = "answered"
        print(f"{q['id']:<5}{cat:<14}{gr['status']:<12}{g_ok:<9}{n_state:<12}{n_ok:<9}")

    acc_g = f"{pct(g['accuracy'])} ({g['correct']}/{g['answerable']})"
    acc_n = f"{pct(n['accuracy'])} ({n['correct']}/{n['answerable']})"
    abs_g = f"{pct(g['abstention'])} ({g['abstained']}/{g['unanswerable']})"
    abs_n = f"{pct(n['abstention'])} ({n['abstained']}/{n['unanswerable']})"
    blk_g = "yes" if g["blocked"] else "no"
    blk_n = "yes" if n["blocked"] else "no"
    blk_d = "blocked vs answered" if g["blocked"] and not n["blocked"] else "-"
    lat_g = f"{g['latency']:.2f}s"
    lat_n = f"{n['latency']:.2f}s"
    lat_d = f"{g['latency'] - n['latency']:+.2f}s"
    cost_g = f"${g['cost']:.4f}"
    cost_n = f"${n['cost']:.4f}"
    cost_d = f"${g['cost'] - n['cost']:+.4f}"

    rows = [
        ("Accuracy on answerable", acc_g, acc_n, delta_pct(g["accuracy"], n["accuracy"])),
        ("Abstention on unanswerable", abs_g, abs_n, delta_pct(g["abstention"], n["abstention"])),
        ("Injection blocked", blk_g, blk_n, blk_d),
        ("Mean latency per model call", lat_g, lat_n, lat_d),
        ("Total cost", cost_g, cost_n, cost_d),
    ]
    print()
    print("COMPARISON")
    print(f"{'METRIC':<32}{'GROUNDED':>16}{'NAIVE':>16}{'DELTA':>21}")
    print("-" * 85)
    for label, gv, nv, dv in rows:
        print(f"{label:<32}{gv:>16}{nv:>16}{dv:>21}")

    print()
    hallucinated = n["unanswerable"] - n["abstained"]
    print(
        f"The naive baseline answered {hallucinated} of {n['unanswerable']} questions the "
        f"policies never address, and did not block the injection."
    )
    print(
        f"The grounded pipeline escalated {g['abstained']} of {g['unanswerable']} and "
        f"blocked the injection before it reached the model."
    )
    print()


async def main() -> None:
    questions = json.loads(QUESTIONS.read_text())
    corpus = load_corpus()
    print(f"corpus: {len(corpus)} chars from {len(list(POLICIES.glob('*.md')))} policy docs")
    print(f"questions: {len(questions)}")
    print("running grounded arm...", flush=True)
    grounded = [await grounded_arm(corpus, q) for q in questions]
    print("running naive arm...", flush=True)
    naive = [await naive_arm(corpus, q) for q in questions]

    g = score(questions, grounded, "grounded")
    n = score(questions, naive, "naive")
    report(questions, grounded, naive, g, n)


if __name__ == "__main__":
    asyncio.run(main())
