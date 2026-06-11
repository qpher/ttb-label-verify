# ADR-007: Server-Side Batch with Bounded Concurrency, Streamed as NDJSON

**Status:** Accepted — Supersedes [ADR-005](./ADR-005-batch-processing.md)
**Date:** 2026-06-10

## Context

ADR-005 chose client-orchestrated batching to fit Vercel's serverless limits. ADR-006 moved to a long-running container, removing that constraint — but the underlying UX requirement is unchanged and non-negotiable: **first results within seconds, continuous visible progress.** The prior vendor tool died on a 30–40 second blank wait; a naive server-side batch (gather all results, return once) reproduces exactly that failure mode at minutes scale for a 300-label batch.

Two implementation constraints surfaced and are encoded in tests:

1. **Memory:** reading all uploads up front puts an entire batch in RAM at once — enough to OOM a 512 MB instance at 300 images.
2. **Upload lifecycle:** Starlette closes request upload files when the endpoint function returns, which is *before* a streaming response finishes — so workers cannot lazily read the framework's `UploadFile` objects mid-stream.

## Decision

One multipart request (`images[]` + CSV/JSON manifest); the server:

1. **Spools each upload to its own temp file** (chunked copy, ~1 MB in memory at a time) before streaming begins — solving the upload-lifecycle constraint with bounded memory.
2. Processes labels under a **semaphore (8 concurrent)**; each worker reads its image from disk inside the semaphore and deletes the temp file when done.
3. **Streams results back as NDJSON in completion order** (`application/x-ndjson`, one `VerificationResult` per line, `X-Total-Count` header). The client renders each row the moment it arrives and shows an `n / total` progress count.
4. Per-label failures (missing manifest row, unreadable file, extraction error) yield an **ERROR row** without affecting the rest of the batch.

A live-server test (`tests/test_batch_streaming.py`) asserts incrementality — a fast label's result must reach the client before a slow label finishes. In-process ASGI test transports buffer full responses and would hide exactly this regression, so the test runs against a real uvicorn instance.

## Alternatives Considered

1. **Client-orchestrated per-label requests (ADR-005).** Still sound; rejected because the server already owns filename↔application matching from the manifest, one request keeps the API surface smaller, and the container has no duration limits to work around.
2. **Gather-then-return server batch.** Rejected: minutes of blank spinner — the documented adoption killer.
3. **SSE.** No advantage over NDJSON for a single consumer; more framing overhead.
4. **Job queue + polling (Redis/worker).** The production path for resumable, unattended batches; unnecessary infrastructure for the prototype.

## Consequences

- (+) First rows appear in single-label latency (~2–4 s); a 300-label batch is minutes of visible progress, not a spinner.
- (+) Memory bounded by chunk size + concurrency, not batch size; disk usage is transient (per-image files deleted as processed, directory removed on stream end/disconnect).
- (−) A dropped connection loses the *remaining* results — completed rows are already rendered; resubmitting re-runs the batch. Acceptable for a prototype; alternative 4 is the production fix.
- (−) Very large multipart bodies are a practical ceiling (hundreds of images per request, enforced by `MAX_BATCH = 300`).
