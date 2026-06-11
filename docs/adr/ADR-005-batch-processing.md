# ADR-005: Client-Orchestrated Parallel Batch with Streaming Results

**Status:** Superseded by [ADR-007](./ADR-007-streamed-server-side-batch.md)
**Date:** 2026-06-10

## Context

During peak season, large importers submit 200–300 label applications at once; agents currently process them strictly one at a time, and batch handling was named as the highest-value capability by the deputy director.

Two constraints shape the design:

1. **Perceived latency:** stakeholders abandoned a prior tool over ~30–40 s waits. Even a fast parallel batch of 300 labels takes minutes end-to-end; a spinner followed by a wall of results would reproduce the failure mode psychologically.
2. **Platform limits:** Vercel serverless functions have execution-duration and payload limits; a single long-running "process whole batch" endpoint is a poor fit and a single point of failure.

## Decision

- The **client orchestrates** the batch: uploaded images are queued in the browser and dispatched to a per-label API endpoint with bounded concurrency (semaphore, ~5–8 in flight) to respect API rate limits.
- **Results stream back individually** and render as they arrive — each label card flips from "pending" to its verdict in roughly the single-label latency (2–4 s for the first results, continuous progress thereafter).
- Each label is an **independent unit of work**: one failed/timed-out label retries or surfaces an error card without affecting the rest of the batch.
- Batch summary (counts by verdict, filterable to NEEDS REVIEW) renders incrementally at the top.

## Alternatives Considered

1. **Single batch endpoint processing all labels server-side.** Rejected: collides with serverless duration limits, all-or-nothing failure mode, and no incremental feedback.
2. **Job queue + worker + polling (e.g., Redis/queue service).** Correct architecture at production scale; rejected for prototype as unnecessary infrastructure. The ADR notes this as the production evolution path.
3. **Server-Sent Events from one long-lived connection.** Considered; client-side orchestration achieves the same UX with simpler code and better fit to serverless constraints.

## Consequences

- (+) First results visible within seconds regardless of batch size — directly addresses the adoption-killing latency perception.
- (+) Per-label isolation: partial failures degrade gracefully.
- (+) Concurrency cap is a single tunable constant balancing throughput vs. rate limits.
- (−) Closing the browser tab abandons an in-flight batch (no server-side job state) — acceptable for prototype, documented; production path is alternative 2.
- (−) Client orchestration trusts the browser to drive the queue; fine for a tool used by authenticated agents at desks, not designed for unattended bulk jobs.
