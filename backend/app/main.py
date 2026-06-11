"""FastAPI app: single + batch label verification."""
import asyncio
import csv
import io
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import claude_client, matching
from .ratelimit import SlidingWindowLimiter
from .schemas import (
    ApplicationData,
    OverallStatus,
    VerificationResult,
)

app = FastAPI(title="TTB Label Verification Prototype", version="0.1.0")

# No CORS middleware: the frontend is served same-origin by this app
# (vite dev server proxies /api), so a wildcard CORS policy would only
# widen the abuse surface of a public prototype.

MAX_BATCH = 300  # Sarah: importers dump 200-300 applications at once
BATCH_CONCURRENCY = 8

# Second-layer abuse control for a public demo (first layer: Anthropic
# console spend limit). One unit per request; batch size is capped separately.
_limiter = SlidingWindowLimiter(
    limit=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30")), window_seconds=60
)


def _enforce_rate_limit(request: Request) -> None:
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    if not _limiter.allow(ip):
        raise HTTPException(429, "Rate limit exceeded — please retry in a minute.")


def _verify_one(image_bytes: bytes, filename: str, app_data: ApplicationData) -> VerificationResult:
    start = time.perf_counter()
    try:
        extracted = claude_client.extract_label(image_bytes, filename)
    except Exception as exc:  # extraction failure -> surfaced, never silently passed
        return VerificationResult(
            filename=filename,
            overall_status=OverallStatus.error,
            checks=[],
            summary="Could not analyze the label image.",
            processing_seconds=round(time.perf_counter() - start, 2),
            error=str(exc),
        )
    checks = matching.run_checks(app_data, extracted)
    status = matching.overall_status(checks, extracted)
    return VerificationResult(
        filename=filename,
        overall_status=status,
        checks=checks,
        extracted=extracted,
        summary=matching.summarize(status, checks, extracted),
        processing_seconds=round(time.perf_counter() - start, 2),
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/verify", response_model=VerificationResult)
async def verify(
    request: Request,
    image: UploadFile = File(...),
    application: str = Form(..., description="ApplicationData as JSON"),
):
    """Verify a single label image against its application data."""
    _enforce_rate_limit(request)
    try:
        app_data = ApplicationData.model_validate_json(application)
    except Exception as exc:
        raise HTTPException(422, f"Invalid application JSON: {exc}")
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(422, "Empty image file.")
    return await asyncio.to_thread(_verify_one, image_bytes, image.filename or "", app_data)


@app.post("/api/verify/batch")
async def verify_batch(
    request: Request,
    images: list[UploadFile] = File(...),
    applications: UploadFile = File(
        ..., description="CSV keyed by filename, or JSON array with a 'filename' field"
    ),
):
    """Batch verification, streamed (ADR-007).

    Returns NDJSON (`application/x-ndjson`): one VerificationResult JSON object
    per line, emitted in *completion order* so the client can render each label
    the moment it finishes instead of staring at a spinner for the whole batch.

    Applications are matched to images by filename.
    CSV columns: filename, brand_name, class_type, alcohol_content, net_contents,
    beverage_type (optional), producer_name_address (optional), country_of_origin (optional)
    """
    _enforce_rate_limit(request)
    if len(images) > MAX_BATCH:
        raise HTTPException(422, f"Batch too large (max {MAX_BATCH}).")

    apps_by_filename = await _parse_applications(applications)

    sem = asyncio.Semaphore(BATCH_CONCURRENCY)

    # Starlette closes the uploaded files when this endpoint function returns,
    # which happens *before* a StreamingResponse finishes. Spool each upload to
    # our own temp file first (chunked, so memory stays bounded at ~1MB per
    # copy); workers then read from disk inside the semaphore, and each file is
    # deleted as soon as its label has been processed.
    tmpdir = tempfile.mkdtemp(prefix="ttb-batch-")
    spooled: list[tuple[str, str]] = []  # (original filename, temp path)
    for i, upload in enumerate(images):
        path = os.path.join(tmpdir, f"{i:04d}.img")
        with open(path, "wb") as out:
            while chunk := await upload.read(1024 * 1024):
                out.write(chunk)
        spooled.append((upload.filename or "", path))

    async def process(name: str, path: str) -> VerificationResult:
        app_data = apps_by_filename.get(name)
        if app_data is None:
            return VerificationResult(
                filename=name,
                overall_status=OverallStatus.error,
                checks=[],
                summary="No application row found for this image filename.",
                processing_seconds=0.0,
                error=f"Missing application data for '{name}'.",
            )

        def run() -> VerificationResult:
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError as exc:
                return VerificationResult(
                    filename=name,
                    overall_status=OverallStatus.error,
                    checks=[],
                    summary="Could not read the uploaded image.",
                    processing_seconds=0.0,
                    error=str(exc),
                )
            finally:
                try:
                    os.unlink(path)  # free disk as we go
                except OSError:
                    pass
            if not data:
                return VerificationResult(
                    filename=name,
                    overall_status=OverallStatus.error,
                    checks=[],
                    summary="Empty image file.",
                    processing_seconds=0.0,
                    error="Empty image file.",
                )
            return _verify_one(data, name, app_data)

        async with sem:
            # At most BATCH_CONCURRENCY images are in memory at once.
            return await asyncio.to_thread(run)

    tasks = [asyncio.create_task(process(name, path)) for name, path in spooled]

    async def stream():
        try:
            for fut in asyncio.as_completed(tasks):
                result = await fut
                yield result.model_dump_json() + "\n"
        finally:
            # Client disconnected or stream finished — don't leave work running
            # or temp files behind.
            for t in tasks:
                t.cancel()
            shutil.rmtree(tmpdir, ignore_errors=True)

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"X-Total-Count": str(len(images))},
    )


async def _parse_applications(upload: UploadFile) -> dict[str, ApplicationData]:
    raw = (await upload.read()).decode("utf-8-sig")
    name = (upload.filename or "").lower()
    rows: list[dict]
    if name.endswith(".json") or raw.lstrip().startswith("["):
        rows = json.loads(raw)
    else:
        rows = list(csv.DictReader(io.StringIO(raw)))
    out: dict[str, ApplicationData] = {}
    for row in rows:
        row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        filename = row.pop("filename", None)
        if not filename:
            raise HTTPException(422, "Every application row needs a 'filename' column.")
        row = {k: v for k, v in row.items() if v}  # drop blanks
        try:
            out[filename] = ApplicationData.model_validate(row)
        except Exception as exc:
            raise HTTPException(422, f"Bad application row for '{filename}': {exc}")
    return out


# Serve the built frontend (single deploy unit).
_static = Path(__file__).resolve().parent.parent / "static"
if _static.is_dir():
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = _static / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(_static / "index.html")
