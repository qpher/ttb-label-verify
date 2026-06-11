# TTB Label Verification Prototype

**Live demo: <https://ttb-label-verify.onrender.com>** *(free tier — first load after idle takes ~30s to wake)*

AI-assisted verification of alcohol beverage label artwork against COLA application data. An agent (or a batch of up to 300 labels) gets a field-by-field comparison — brand name, class/type, alcohol content, net contents, and the mandatory government health warning — with an APPROVED / NEEDS REVIEW / REJECTED result in a few seconds per label.

Verified end-to-end on the deployed instance: 8/8 expected verdicts on the
[precision test set](test-labels/) (3–4s per label) and APPROVED on a
[real approved COLA label](test-labels/real/) from TTB's public registry.

## How it works

> Full pipeline diagram: [docs/app-flow.html](docs/app-flow.html) *(HTML — view via the [deployed copy](https://ttb-label-verify.onrender.com/docs/app-flow.html) or open locally)* — decision log: [docs/adr/](docs/adr/)

1. The label image is sent to **Claude Vision** (Haiku, for speed), which *only extracts* what is printed on the label — brand name, ABV, warning text, formatting cues (caps/bold), and image-quality issues. It is explicitly instructed not to judge or correct.
2. **Deterministic, unit-tested Python code** compares the extraction against the application data. All pass/fail decisions live in `backend/app/matching.py`, so results are auditable, consistent, and testable — important for a compliance tool.

| Check | Logic |
|---|---|
| Brand name, class/type | Exact → match. Case/punctuation-only difference (`STONE'S THROW` vs `Stone's Throw`) → match with note. Close-but-different → NEEDS REVIEW. Otherwise mismatch. |
| Alcohol content | Parsed numerically: `45% Alc./Vol.` = `ALC. 45.0% BY VOL.` Proof cross-checked (must equal 2× ABV). |
| Net contents | Unit-aware: `750 mL` = `750ML` = `75 cl`. |
| Government warning | Strict: word-for-word against 27 CFR 16.21, `GOVERNMENT WARNING:` must be ALL CAPS and bold. Title-case header → rejected. Bold unconfirmable from the photo → NEEDS REVIEW (never silently passed). |

Any mismatch/missing field → **REJECTED**. Fuzzy-close fields or poor image legibility → **NEEDS REVIEW** (never silently passed). All checks clean → **APPROVED**.

## Run locally

Requirements: Python 3.10+, Node 18+, an Anthropic API key.

```bash
# 1. Backend deps
cd backend
pip install -r requirements.txt

# 2. Build frontend (outputs to backend/static)
cd ../frontend
npm install
npm run build

# 3. Run
cd ../backend
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --port 8000
```

Open http://localhost:8000. API docs at http://localhost:8000/docs.

For frontend development with hot reload: `npm run dev` in `frontend/` (proxies `/api` to port 8000).

### Docker

```bash
docker build -t ttb-label-verify .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... ttb-label-verify
```

### Deploy (Render)

Push to GitHub, create a new Blueprint service from `render.yaml`, set `ANTHROPIC_API_KEY` in the dashboard. Any Docker host (Fly.io, Railway, Azure Container Apps) works the same way.

## Tests

```bash
cd backend && python -m pytest tests/ -v
```

28 tests cover the matching logic and the streaming batch endpoint (run against a real uvicorn instance to prove results arrive incrementally), including the stakeholder edge cases: Dave's `STONE'S THROW` capitalization scenario, Jenny's title-case `Government Warning` rejection, format-variant ABV/volume strings, and proof/ABV consistency.

## API

- `POST /api/verify` — multipart: `image` (file) + `application` (JSON string)
- `POST /api/verify/batch` — multipart: `images` (multiple files) + `applications` (CSV or JSON file, rows matched to images by `filename`). **Streams NDJSON**: one `VerificationResult` per line, in completion order, so the UI renders each label the moment it finishes — first rows in single-label latency, not after the whole batch.

CSV columns: `filename, brand_name, class_type, alcohol_content, net_contents` (+ optional `beverage_type`, `producer_name_address`, `country_of_origin`). A template is downloadable in the UI.

## Design decisions & assumptions

- **Application data arrives structured** (form fields / CSV / JSON), mirroring how it exists
  in the COLA system — only the label is an image. Parsing application *documents* would add an
  extraction error source on the trusted side of the comparison for no benefit.

- **Extraction ≠ judgment.** The LLM reads the label; deterministic code decides. A compliance decision should never depend on a model's mood — and it makes the decision logic unit-testable.
- **Speed budget (~5s).** Claude Haiku typically returns in 2–4s per label. Model is configurable via `CLAUDE_MODEL`. Batch runs 8 labels concurrently and streams each result as it completes, so a 300-label batch shows its first rows in seconds and fills live — a couple of minutes of visible progress, not a spinner.
- **NEEDS REVIEW is a first-class outcome.** The tool drafts, the agent decides. Anything ambiguous (close-but-not-equal text, partial legibility, unconfirmable bold) is routed to a human rather than auto-approved or auto-rejected.
- **Imperfect photos** (angle, glare, low light) are handled by the vision model; legibility issues downgrade the result to NEEDS REVIEW with the issue described.
- **Standalone prototype** per Marcus — no COLA integration, no persistence, nothing stored server-side. The only external call is to the Anthropic API (one domain to allowlist on the TTB firewall).
- **UI for the whole team**: large type and targets, three obvious colors, no hidden actions — built for Dave as much as Jenny.
- Beverage-type-specific rules (e.g. wine ABV tolerance bands, beer exemptions) are noted as future work; the field is captured but rules are uniform in this prototype.

## Test labels

[`test-labels/`](test-labels/) is a programmatically rendered **precision attack set**: every
label varies exactly one thing from the canonical application data, so a wrong verdict points
at a specific check (title-case warning header, reworded statutory text, ABV mismatch, missing
warning, tilt + glare). `applications.csv` is ready for the batch tab — drop all 8 images plus
the CSV in and the whole set runs in one go. See [`test-labels/README.md`](test-labels/README.md)
for the expected-verdict table, and `generate.py` to regenerate or extend.

Rendered with Pillow rather than AI image generation on purpose: the government warning is 60
words of statutory text that image models reliably garble, and a precision set needs exact,
known ground truth.

[`test-labels/real/`](test-labels/real/) complements the synthetic set with **real approved
label artwork from TTB's public COLA registry** (Buffalo Trace, TTB ID 24009001000244) —
verified end-to-end: back label APPROVED, front-label-only correctly REJECTED for the missing
warning, and a falsified application ABV correctly caught. See its README for the run results.

## Abuse & cost controls

This is a public demo that spends API credits per request, so two layers:

1. **Spend limit in the Anthropic console** — the hard backstop.
2. **Per-IP rate limiting** (`RATE_LIMIT_PER_MINUTE`, default 30) — in-memory sliding window,
   enough to stop drive-by abuse of a prototype. Production would use edge rate limiting or a
   shared store.

## Future work

- **Field-inspection mode.** Single-label verification is phone-shaped: the upload control
  already offers direct camera capture (`capture="environment"`), so an inspector can point a
  phone at a bottle and get a verdict in seconds. The FastAPI backend is client-agnostic — a
  native (SwiftUI) front end would reuse the API unchanged.
- **Resumable batches.** A job queue (ADR-007, alternative 4) so a dropped connection doesn't
  re-run completed labels; CSV export of batch results.
- **COLA integration.** Pull application data directly instead of CSV upload — the structured
  -data assumption below maps 1:1 to COLA fields.

## Development notes

Built with Claude (Claude Code for implementation, with independent architecture review in a
separate session). Architecture decisions, the deterministic/LLM trust split, verification
rules, test design, and all trade-off calls are mine and are documented in
[docs/adr/](docs/adr/); the decision records include two superseded entries because the stack
evolved during implementation — the change history is kept deliberately.

## Project structure

```
backend/
  app/
    main.py           # FastAPI routes (single + batch), serves built frontend
    claude_client.py  # Claude Vision extraction (extraction only)
    matching.py       # All comparison/decision logic (unit-tested)
    schemas.py        # Pydantic models
  tests/                # matching logic + batch streaming (live-server) tests
frontend/             # React + Vite, builds into backend/static
docs/                 # adr/ decision records + app-flow.html pipeline diagram
test-labels/          # precision attack set + applications.csv + generator
Dockerfile            # Single-container deploy
render.yaml           # One-click Render blueprint
```
