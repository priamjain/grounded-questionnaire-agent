"""The grounded pipeline: fetch sources, ask once per question, verify locally."""
import json
import re

from anthropic import AsyncAnthropic

from . import config, grounding, prompts, sources
from .models import Row

_client = AsyncAnthropic(api_key=config.SETTINGS["ANTHROPIC_API_KEY"])

MAX_TOKENS = 1024


def parse_claim(text: str) -> dict:
    """Pull the JSON object out of the reply, tolerating stray prose or fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


async def answer_question(corpus: str, question: str, with_usage: bool = False):
    """One call per question, returning the model's raw claim."""
    message = await _client.messages.create(
        model=config.MODEL,
        max_tokens=MAX_TOKENS,
        system=prompts.SYSTEM,
        messages=[{"role": "user", "content": prompts.user_message(corpus, question)}],
    )
    text = "".join(b.text for b in message.content if b.type == "text")
    claim = parse_claim(text)
    if with_usage:
        return claim, {
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        }
    return claim


async def run_pipeline(run, emit) -> None:
    corpus, errors = await sources.build_corpus(run.source_urls)
    if not corpus:
        raise RuntimeError(
            "No readable policy text could be fetched. " + "; ".join(errors)
        )
    run.source_chars = len(corpus)
    if errors:
        run.error = "Some sources failed: " + "; ".join(errors)

    for question in run.questions:
        key = grounding.row_key(run.run_id, question)

        # Blocked questions never reach the answering call at all.
        if grounding.looks_like_injection(question):
            row = Row(
                key=key,
                question=question,
                status="BLOCKED",
                reason="Contains instruction-like text; not sent to the model.",
            )
            run.rows.append(row)
            await emit(row)
            continue

        try:
            claim = await answer_question(corpus, question)
        except Exception as exc:
            row = Row(
                key=key,
                question=question,
                status="ESCALATE",
                reason=f"The model call failed ({type(exc).__name__}).",
            )
            run.rows.append(row)
            await emit(row)
            continue

        status, reason = grounding.verify(claim, corpus)
        if status == "ANSWERED":
            row = Row(
                key=key,
                question=question,
                status="ANSWERED",
                answer=str(claim.get("answer", "")),
                source_quote=str(claim.get("source_quote", "")),
                confidence=float(claim.get("confidence", 0.0)),
            )
        else:
            # The answer text is discarded — an ungrounded answer is not shown.
            row = Row(
                key=key,
                question=question,
                status="ESCALATE",
                reason=reason,
                confidence=float(claim.get("confidence") or 0.0),
            )
        run.rows.append(row)
        await emit(row)


async def answer_naive(corpus: str, question: str) -> tuple[dict, dict]:
    """The baseline the eval compares against.

    Same model, same corpus, one call — but no grounding requirement, no
    abstention instruction, no quote, and no verification afterwards.
    """
    message = await _client.messages.create(
        model=config.MODEL,
        max_tokens=MAX_TOKENS,
        system=prompts.NAIVE_SYSTEM,
        messages=[
            {"role": "user", "content": prompts.naive_user_message(corpus, question)}
        ],
    )
    text = "".join(b.text for b in message.content if b.type == "text")
    usage = {
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }
    try:
        return parse_claim(text), usage
    except json.JSONDecodeError:
        return {"answer": text, "confidence": 0.0}, usage
