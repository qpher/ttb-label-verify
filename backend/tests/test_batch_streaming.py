"""Batch endpoint streaming behavior (ADR-007).

Verifies that /api/verify/batch returns NDJSON and that results arrive
*incrementally* — a fast label's result must reach the client before a slow
label finishes, instead of the whole batch buffering until the end.

Runs against a real uvicorn server in a background thread: in-process ASGI
test transports buffer the full response, which would hide exactly the
regression this test exists to catch. Claude extraction is stubbed; each fake
image's bytes encode how long the "extraction" should take.
"""
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from app import claude_client, main
from app.matching import STATUTORY_WARNING
from app.schemas import ExtractedLabel

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _fake_extract(image_bytes: bytes, filename: str = "") -> ExtractedLabel:
    time.sleep(float(image_bytes.decode()))  # runs in a worker thread
    return ExtractedLabel(
        brand_name="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content="45% Alc./Vol. (90 Proof)",
        net_contents="750 mL",
        government_warning={
            "present": True,
            "text": STATUTORY_WARNING,
            "header_all_caps": True,
            "header_bold": True,
        },
        legibility="ok",
    )


@pytest.fixture
def live_server(monkeypatch):
    monkeypatch.setattr(claude_client, "extract_label", _fake_extract)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.01)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


_CSV = (
    "filename,brand_name,class_type,alcohol_content,net_contents\n"
    'fast.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,"45% Alc./Vol. (90 Proof)",750 mL\n'
    'slow.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,"45% Alc./Vol. (90 Proof)",750 mL\n'
)


async def test_batch_streams_results_incrementally(live_server):
    files = [
        ("images", ("fast.png", b"0.0", "image/png")),
        ("images", ("slow.png", b"1.2", "image/png")),
        # No CSV row for this one -> should stream an ERROR result, not 500.
        ("images", ("orphan.png", b"0.0", "image/png")),
        ("applications", ("apps.csv", _CSV.encode(), "text/csv")),
    ]

    arrivals: list[tuple[float, dict]] = []
    async with httpx.AsyncClient(timeout=10) as client:
        async with client.stream(
            "POST", f"{live_server}/api/verify/batch", files=files
        ) as res:
            assert res.status_code == 200
            assert res.headers["content-type"].startswith("application/x-ndjson")
            assert res.headers["x-total-count"] == "3"
            start = time.perf_counter()
            async for line in res.aiter_lines():
                if line.strip():
                    arrivals.append((time.perf_counter() - start, json.loads(line)))

    assert len(arrivals) == 3
    by_name = {r["filename"]: (t, r) for t, r in arrivals}

    # Correctness of each streamed result.
    assert by_name["fast.png"][1]["overall_status"] == "APPROVED"
    assert by_name["slow.png"][1]["overall_status"] == "APPROVED"
    assert by_name["orphan.png"][1]["overall_status"] == "ERROR"
    assert "application data" in by_name["orphan.png"][1]["error"].lower()

    # Incrementality: the fast result must arrive well before the slow label
    # finishes, and the slow one only after its 1.2s extraction.
    assert by_name["fast.png"][0] < 0.6, "fast result was buffered behind the slow one"
    assert by_name["slow.png"][0] >= 1.0
