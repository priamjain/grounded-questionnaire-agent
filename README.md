# Grounded Security Questionnaire Agent

Answers vendor security questionnaires from your own policy documents, and
**refuses to answer when the documents don't say**.

**Live demo — https://d13ku3eumm26n5.cloudfront.net**

| | |
|---|---|
| Username | `demo` |
| Password | `WVF9vDfIUB8LwH5p` |

Sign in, then follow the demo script in section 05. `test.csv` and the Notion
links in section 04 are the inputs it is set up for.

> These credentials are deliberately throwaway: one operator account on a
> hackathon instance holding no customer data. They are in this file because the
> judges need to get in. Rotate `APP_PASSWORD` in `/opt/questionnaire/.env` and
> `systemctl restart questionnaire` to invalidate them.

---

## 01 · Project overview

A vendor sends a 50-question security questionnaire. Someone senior spends a
day copying answers out of internal policy docs. The obvious fix — paste the
policies into an LLM and let it fill the sheet — fails in the one way that
matters: on a question the policies never address, the model writes a fluent,
confident, **wrong** answer. In a security questionnaire that is not a typo, it
is a misrepresentation to a customer.

This tool makes that failure structurally impossible rather than merely
unlikely.

**How.** For each question, one call to Claude returns strict JSON:

```json
{"answer": "...", "source_quote": "...", "grounded": true, "confidence": 0.93}
```

The backend then **ignores what the model claims about itself** and checks the
quote mechanically: normalize whitespace, Unicode and case, then require
`source_quote` to appear as a literal contiguous substring of the fetched
corpus. If the quote isn't really there — or `grounded` is false, or confidence
is under 0.70 — the row becomes **ESCALATE and the answer text is discarded**.
It is never shown to anyone.

That last part is the whole design. The model's self-report is a hint; the
substring check is the authority.

Three outcomes per row:

| Status | Meaning |
|---|---|
| `ANSWERED` | Model answered **and** the cited quote verifies literally against a source |
| `ESCALATE` | Not groundable — a human must answer this one |
| `BLOCKED` | The question contained prompt-injection patterns; it never reached the model at all |

**Observed on real data** (the run in section 04): the model produced a smoothed,
plausible-looking quote that did not exist verbatim in the policy. The substring
check caught it with no prompting. That row escalated instead of shipping a
fabricated citation to a customer.

### What it is not

No database, no vector store, no chunking, no embeddings — the corpus goes into
the prompt whole. One process, one port. State lives in a module-level dict and
is appended to `./data/runs.jsonl`, which is replayed on startup so runs survive
a restart.

---

## 02 · External apps used

Four external services, each doing one job.

| Service | Used for | Required? |
|---|---|---|
| **Anthropic API** | `claude-sonnet-4-6`, one call per question. Also drives the naive baseline in the eval. | **Yes** — `ANTHROPIC_API_KEY` |
| **Resend** | Emails the finished results table to the recipient. Idempotent per run. | **Yes** — `RESEND_API_KEY` |
| **Jina Reader** (`r.jina.ai`) | Renders JavaScript-only pages that return no text over plain HTTP. | Optional — `READER_API_KEY` raises the rate limit; works without a key |
| **Notion** | Where the policy documents actually live. Read as published pages, no integration token needed. | Optional — any URL works |

**Why the reader exists.** Notion serves a JavaScript boot shell: a
`notion.site` page is ~20KB of loader with **zero** policy text in the HTTP
response — the page title isn't even in there. Measured directly:

```
www.notion.so/.../Data-handling-practices    1,304,766 bytes   0 chars of text
cheerio-api-doc.notion.site/Email-Usage-...     20,034 bytes   0 chars of text
grep -c -i 'email usage'  →  0
```

So the direct fetch runs first, and **only** when it comes back with no text
does the source fall back to rendering. Pages that serve real HTML never touch
Jina. `app.notion.com/p/<workspace>/<slug>` links are also rewritten to their
published `<workspace>.notion.site/<slug>` form, which is the one a reader can
resolve.

**The SSRF guard holds on both paths.** Every URL — direct or reader — is
resolved and checked against private, loopback, link-local, reserved and
multicast ranges before any request is made, and redirects are followed *by
hand* so each hop is validated before it is fetched. Verified:
`http://169.254.169.254/latest/meta-data/` is refused rather than laundered
through the external reader.

---

## 03 · Setup instructions

**Requires** Python 3.11+ (built on 3.14.6) and Node 20+ (built on 24.13.1).

```bash
git clone <repo> && cd questionnaire-agent
cp .env.example .env     # then fill it in — see below
make run                 # builds the frontend, serves everything on :8000
```

Open **http://127.0.0.1:8000** and log in with `APP_USERNAME` / `APP_PASSWORD`.

`make run` compiles the React app into `backend/static` and serves the API and
the SPA from a single uvicorn process. One port, no reverse proxy needed
locally.

### Environment

The app **fails fast at startup** with a named message if any required variable
is missing — it will not boot half-configured.

```ini
# Required
APP_USERNAME=admin
APP_PASSWORD=<pick one>
SESSION_SECRET=<openssl rand -hex 32>
ANTHROPIC_API_KEY=sk-ant-...
RESEND_API_KEY=re_...

# Optional
READER_API_KEY=jina_...              # raises the render rate limit
READER_URL=https://r.jina.ai/        # set to "" to disable rendering entirely
MAIL_FROM=Grounded <onboarding@resend.dev>
```

### Make targets

| Target | Does |
|---|---|
| `make run` | Build the frontend, serve API + SPA on :8000 |
| `make dev` | uvicorn with reload on :8000, Vite dev server on :5173 |
| `make build` | Compile the frontend into `backend/static` |
| `make eval` | Run the offline eval harness (see 04) |
| `make clean` | Remove venv, node_modules, built static |

### Auth

Single operator account from `.env`, compared with `secrets.compare_digest`.
Session is a signed HttpOnly cookie (`itsdangerous`, 12h expiry). Every route
except `/api/login` and `/health` requires it. No user table, no registration,
no JWT library.

> **Behind TLS**, set `COOKIE_SECURE=1` and the session cookie is issued with
> the `Secure` flag. It is off by default so plain-HTTP local runs still log in.
> The deployed instance has it on.

### API

```
POST /api/login          POST /api/runs            GET  /api/runs/:id/stream   (SSE)
POST /api/logout         GET  /api/runs            POST /api/runs/:id/email
GET  /api/me             GET  /api/runs/:id        GET  /health
```

CSV is parsed in the browser; the backend receives a plain list of strings.

---

## 04 · Reliability testing

### The eval harness — `make eval`

12 fixture questions (8 answerable, 3 unanswerable, 1 injection) against three
local policy documents, run through **both** the grounded pipeline and a naive
baseline — same model, same corpus, one prompt, no grounding requirement, no
abstention instruction, no verification.

It reads fixtures **off disk**. No source fetching, no Resend, no network except
the model calls. It cannot fail because a website is down during judging.

```
METRIC                                  GROUNDED           NAIVE                DELTA
-------------------------------------------------------------------------------------
Accuracy on answerable                100% (8/8)      100% (8/8)               +0 pts
Abstention on unanswerable            100% (3/3)      100% (3/3)               +0 pts
Injection blocked                            yes              no  blocked vs answered
Mean latency per model call                2.24s           2.34s               -0.10s
Total cost                               $0.0694         $0.0601             $+0.0092
```

**Read this table honestly: the abstention delta is zero.** On a small, clean,
three-document corpus, Claude declines the unanswerable questions on its own —
it told us an RTO "would typically be found in a Business Continuity Plan"
without being asked to abstain. We are not claiming a win we did not measure,
and we deliberately did not inflate the corpus until the baseline broke.

Two real differences remain in that table:

1. **The injection row is structural.** The naive arm *declined* the injected
   question — but the injected text still reached the model. Its good behaviour
   came from the model's disposition, not from a control. The grounded pipeline
   blocks it by regex before any API call. That difference survives a model
   swap; the baseline's does not.
2. **The naive arm's answers are unauditable.** It cites nothing. Its "100%" is
   a substring match a reviewer cannot check. Every grounded answer ships with a
   quote that verifiably exists in a named source.

### End-to-end on real data

The genuine test: **12 Notion policy documents** (the `cheerio-api-doc`
workspace — General Controls, Information Security, Data Security, Business
Continuity & DR, Personnel Security, Email Usage, Communications & Operations,
Service Delivery, Privacy, System Planning, Work-from-Home, Data Handling) and a
real vendor questionnaire.

| Run | Sources | Corpus | Questions | Result |
|---|---|---|---|---|
| Full (`test_full.csv`) | 12 Notion pages | 69,008 chars | 54 | 27 ANSWERED / 27 ESCALATE |
| Demo (`test.csv`) | 12 Notion pages | 69,008 chars | 24 | **22 ANSWERED / 2 ESCALATE** |

Escalation breakdown on the 54-question run: 12 the model declined outright, 12
below the confidence floor, and **3 where the cited quote did not appear
verbatim** — the substring check catching invented citations on production
policy text. Answers were attributed across 6 distinct source documents.

`test.csv` is the curated demo set: rows that answered above 0.80 confidence,
plus two questions the policies genuinely never address (packet capture, DLP).
Rows sitting exactly on the 0.70 floor were removed because they were coin flips
across runs. **This set is tuned to this corpus** — different sources, different
counts.

### Component checks

| Area | Result |
|---|---|
| Grounding | Exact ✓, whitespace/case ✓, smart quotes ✓; paraphrase ✗, too-short ✗, quote stitched from two places ✗ — all correctly rejected |
| Injection filter | 5 true positives, 2 true negatives (real questions not flagged) |
| SSRF | `169.254.169.254` refused; redirect *to* a private address refused **before** the hop is fetched; >3 redirects refused; refused on the reader path too |
| Email idempotency | Two concurrent POSTs → one send, one `already_sent: true`, one message id (per-run `asyncio.Lock`) |
| Failure isolation | One unreachable URL does not sink a run; a failed model call escalates that row only |
| Restart | Runs replay from `data/runs.jsonl` |

### Known limits

- **Questions run sequentially**, ~2–4s each — 54 questions is roughly 3 minutes.
- **Resend's shared sender only delivers to the account owner's address** until
  a domain is verified at resend.com/domains and `MAIL_FROM` is set.
- **One SSE queue per run**, so two tabs open on the same *in-flight* run split
  the events. Reloading a finished run is unaffected.
- **Rendering adds an external dependency** to the ingestion path. `make eval`
  does not use it and stays fully offline.
- Confidence is the model's own number. It is a floor, not a calibrated
  probability — the substring check is what actually guarantees grounding.

---

## 05 · Demo video

**https://drive.google.com/file/d/1uSQPbQIak74pSkwiZeCI8FwglbyEWyBc/view?usp=drive_link**

### Reproduce it yourself

Everything the video uses is here. Sign in at the live demo, paste the twelve
policy links into **Sources**, and drop the questionnaire into **Questions**.

**Policy documents** — 12 published Notion pages (the `?source=copy_link` form
works as-is; the app rewrites them to their published address):

```
https://app.notion.com/p/cheerio-api-doc/General-Controls-Policy-e9afc3c08d1b4c3b8ed52aa7104134fc?source=copy_link
https://app.notion.com/p/cheerio-api-doc/Information-Security-Policy-dfbc6a3ff4104db2a83a9dce69a7971a?source=copy_link
https://app.notion.com/p/cheerio-api-doc/System-Planning-Acceptance-Policy-a723b6c92ed8492fb832a028aee684d1?source=copy_link
https://app.notion.com/p/cheerio-api-doc/Data-Security-Policy-f1bac933a93841c0bac9244b497567fc?source=copy_link
https://app.notion.com/p/cheerio-api-doc/Business-Continuity-Management-and-Disaster-Recovery-Policy-4786e06a738647f4960c4cd1a541f7a6?source=copy_link
https://app.notion.com/p/cheerio-api-doc/Personnel-Security-Policy-183bf135bd73403f9e6edfb64a640e45?source=copy_link
https://app.notion.com/p/cheerio-api-doc/Email-Usage-Policy-9f2e658e3c9e4caf807b1476532e7298?source=copy_link
https://app.notion.com/p/cheerio-api-doc/Communications-Operations-Management-Policy-142d32dd2c7d447db2048e0333a630de?source=copy_link
https://app.notion.com/p/cheerio-api-doc/Service-Delivery-Policy-c0dcb4008aec4a79ab2aba1e6706f07e?source=copy_link
https://app.notion.com/p/cheerio-api-doc/Privacy-Policy-28f03d9e204c49d6b7fe5f2649f6abbc?source=copy_link
https://app.notion.com/p/cheerio-api-doc/Work-from-Home-Security-Policy-64f6d4ea89e84674bacfd0f8cbc0ff8b?source=copy_link
https://www.notion.so/cheerio-api-doc/Data-handling-practices-at-Cheerio-8d097a900d654aa3b785cf5875842d2c
```

**Questionnaire** — 24 questions, one per row:
[**test.csv**](https://github.com/priamjain/grounded-questionnaire-agent/blob/main/test.csv)
&middot; [direct download](https://raw.githubusercontent.com/priamjain/grounded-questionnaire-agent/main/test.csv)

Expected result: **22 ANSWERED / 2 ESCALATE**.

What the video shows, using the files in this repo:

1. **Log in**, land on New Run.
2. **Paste the 12 Notion policy links** (the `?source=copy_link` URLs work as-is
   — they get rewritten to their published form). Watch the step rail mark
   sources complete and count the hosts.
3. **Drop `test.csv`** — 24 questions, column auto-detected, 5-row preview.
4. **Run.** Rows stream in over SSE as each is verified; skeleton rows show what
   is still pending.
5. **Land on 22 ANSWERED / 2 ESCALATE.** Expand an answered row — the verbatim
   quote, and a link to the exact Notion document it was found in.
6. **Filter to ESCALATE.** Two questions with no answer text at all, because the
   policies are silent on packet capture and DLP. *This is the point: it would
   rather hand a human two gaps than invent two answers.*
7. **Email the results**, then click again to show the double-send is a no-op.
8. Close on `make eval` and the injection row.
