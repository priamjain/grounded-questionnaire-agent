"""Send run results via Resend.

The email is the deliverable a reviewer forwards, so escalations are shown as
prominently as answers — an unanswered row is a task, not a failure to hide.
"""
import html
import os

import httpx

from . import config
from .models import Run, tally

RESEND_URL = "https://api.resend.com/emails"
# Resend's shared sender works without a verified domain, but only delivers to
# the address that owns the Resend account. Set MAIL_FROM once a domain is set up.
FROM = os.environ.get("MAIL_FROM", "Grounded <onboarding@resend.dev>")
TIMEOUT = 15.0

_PILL = {
    "ANSWERED": ("#15803d", "#f0fdf4"),
    "ESCALATE": ("#b45309", "#fffbeb"),
    "BLOCKED": ("#b91c1c", "#fef2f2"),
}


class MailError(Exception):
    pass


def _row_html(row) -> str:
    color, background = _PILL.get(row.status, ("#64748b", "#f8fafc"))
    detail = html.escape(row.answer) if row.answer else (
        f'<span style="color:#94a3b8;font-style:italic">{html.escape(row.reason)}</span>'
    )
    source = ""
    if row.source_quote and row.source_url:
        safe = html.escape(row.source_url, quote=True)
        inner = (
            f'<a href="{safe}" style="color:#64748b">{safe}</a>'
            if row.source_url.lower().startswith(("http://", "https://"))
            else safe
        )
        source = (
            f'<div style="margin-top:6px;font-size:11px;color:#94a3b8;'
            f'word-break:break-all">Source: {inner}</div>'
        )
    quote = (
        f'<div style="margin-top:8px;padding:8px 10px;background:#f8fafc;'
        f'border-left:2px solid #cbd5e1;color:#475569;font-size:12px;'
        f'font-family:ui-monospace,Menlo,monospace">&ldquo;{html.escape(row.source_quote)}&rdquo;'
        f'</div>{source}'
        if row.source_quote
        else ""
    )
    return f"""
    <tr>
      <td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;vertical-align:top;width:34%">
        <div style="color:#0f172a">{html.escape(row.question)}</div>
      </td>
      <td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;vertical-align:top;white-space:nowrap">
        <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;
                     font-weight:600;color:{color};background:{background};border:1px solid {color}33">
          {row.status}
        </span>
      </td>
      <td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;vertical-align:top;color:#475569">
        {detail}{quote}
      </td>
    </tr>"""


def render(run: Run) -> tuple[str, str]:
    """Return (subject, html_body)."""
    stats = tally(run.rows)
    subject = (
        f"Security questionnaire — {stats['answered']} answered, "
        f"{stats['escalated']} to review, {stats['blocked']} blocked"
    )
    sources = "".join(
        f'<li style="margin-bottom:2px"><a href="{html.escape(u)}" '
        f'style="color:#1d4ed8;text-decoration:none">{html.escape(u)}</a></li>'
        for u in run.source_urls
    )
    body = f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#f8fafc;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  font-size:14px;color:#0f172a">
  <div style="max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px">
    <div style="padding:20px 24px;border-bottom:1px solid #e2e8f0">
      <div style="font-size:15px;font-weight:600">Security questionnaire results</div>
      <div style="margin-top:4px;color:#64748b;font-size:13px">
        Run {html.escape(run.run_id)} &middot; {len(run.rows)} questions
      </div>
    </div>

    <div style="padding:16px 24px;border-bottom:1px solid #e2e8f0">
      <table cellpadding="0" cellspacing="0" width="100%"><tr>
        <td><div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Answered</div>
            <div style="font-size:22px;font-weight:600;color:#15803d">{stats['answered']}</div></td>
        <td><div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Escalated</div>
            <div style="font-size:22px;font-weight:600;color:#b45309">{stats['escalated']}</div></td>
        <td><div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Blocked</div>
            <div style="font-size:22px;font-weight:600;color:#b91c1c">{stats['blocked']}</div></td>
      </tr></table>
    </div>

    <div style="padding:14px 24px;background:#f8fafc;border-bottom:1px solid #e2e8f0;
                color:#475569;font-size:13px;line-height:1.5">
      Every answer below is supported by a quote taken verbatim from the policy
      sources. Rows marked <strong>ESCALATE</strong> could not be grounded in
      those sources and need a human answer &mdash; they were not guessed.
      Rows marked <strong>BLOCKED</strong> contained instruction-like text and
      were never sent to the model.
    </div>

    <table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;font-size:13px">
      <thead><tr style="background:#f8fafc">
        <th style="text-align:left;padding:10px 16px;border-bottom:1px solid #e2e8f0;
                   color:#64748b;font-weight:500">Question</th>
        <th style="text-align:left;padding:10px 16px;border-bottom:1px solid #e2e8f0;
                   color:#64748b;font-weight:500">Status</th>
        <th style="text-align:left;padding:10px 16px;border-bottom:1px solid #e2e8f0;
                   color:#64748b;font-weight:500">Answer &amp; source</th>
      </tr></thead>
      <tbody>{"".join(_row_html(r) for r in run.rows)}</tbody>
    </table>

    <div style="padding:16px 24px;color:#64748b;font-size:12px">
      <div style="margin-bottom:6px">Policy sources</div>
      <ul style="margin:0;padding-left:18px">{sources}</ul>
    </div>
  </div>
</body></html>"""
    return subject, body


async def send_results(run: Run) -> str:
    """Send via Resend and return the provider message id."""
    subject, body = render(run)
    payload = {
        "from": FROM,
        "to": [run.email],
        "subject": subject,
        "html": body,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {config.SETTINGS['RESEND_API_KEY']}"},
        )
    if response.status_code >= 400:
        detail = response.text[:300]
        raise MailError(f"Resend returned {response.status_code}: {detail}")
    return response.json().get("id", "")
