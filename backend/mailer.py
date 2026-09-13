"""Stub until step 5 wires Resend."""


async def send_results(run) -> None:
    print(f"[mailer stub] would send {len(run.rows)} rows to {run.email}")
