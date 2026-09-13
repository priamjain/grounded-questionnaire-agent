"""Canned rows so the UI can be built before the real agent exists.

Enabled with MOCK_AGENT=1. Deterministic per question so screenshots are
stable: every 4th question escalates, injection-looking ones are blocked.
"""
import asyncio

from .models import Row

_QUOTE = (
    "All production access requires multi-factor authentication. Access is "
    "reviewed quarterly by the security team and revoked within 24 hours of "
    "an employee's departure."
)


async def run_pipeline(run, emit) -> None:
    for i, question in enumerate(run.questions):
        await asyncio.sleep(0.6)  # visible streaming while building the UI
        lowered = question.lower()
        if "ignore" in lowered or "disregard" in lowered or "system prompt" in lowered:
            row = Row(
                key=f"mock-{i}",
                question=question,
                status="BLOCKED",
                reason="Question contains instruction-like text and was not sent to the model.",
            )
        elif i % 4 == 3:
            row = Row(
                key=f"mock-{i}",
                question=question,
                status="ESCALATE",
                reason="No supporting text found in the policy sources.",
                confidence=0.31,
            )
        else:
            row = Row(
                key=f"mock-{i}",
                question=question,
                status="ANSWERED",
                answer=(
                    "Yes. Production access is gated behind multi-factor "
                    "authentication, with quarterly access reviews and removal "
                    "within 24 hours of departure."
                ),
                source_quote=_QUOTE,
                confidence=0.93,
            )
        run.rows.append(row)
        await emit(row)
