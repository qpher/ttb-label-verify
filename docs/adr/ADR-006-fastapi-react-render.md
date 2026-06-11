# ADR-006: FastAPI (Python) + React/Vite, Single-Container Deploy on Render

**Status:** Accepted — Supersedes [ADR-004](./ADR-004-stack-and-deployment.md)
**Date:** 2026-06-10

## Context

ADR-004 selected Next.js on Vercel for delivery speed. Implementation surfaced reasons to revisit:

1. **The verification core is Python-shaped.** The deterministic layer (ADR-002) leans on mature Python tooling — `rapidfuzz` for the review band, regex/unit parsing for ABV, proof, and net-contents — and the decision logic benefits from `pytest` ergonomics. Porting this to TypeScript bought nothing and cost test depth.
2. **Serverless limits constrain the batch design.** Vercel function duration/payload limits forced batch orchestration onto the client (ADR-005). A long-running container removes that constraint and reopens the design space (see ADR-007).

## Decision

- **Backend:** FastAPI owns all verification logic (`extraction → deterministic checks → verdict`), fully unit-tested.
- **Frontend:** React (Vite), built into static files served by the same FastAPI app — still a single deploy unit.
- **Packaging/Hosting:** one multi-stage Dockerfile; Render free tier via `render.yaml` blueprint. Any Docker host works identically.

**Preserved from ADR-004 (unchanged commitments):** fully stateless, no persistence; API key server-side only via environment variable; single deploy unit; documented production path of inference inside a government-authorized boundary (Claude via AWS Bedrock GovCloud / Azure Government).

## Alternatives Considered

1. **Keep Next.js/Vercel (ADR-004).** Rejected: requires a JS port of the matching layer and keeps serverless duration limits that force client-side batch orchestration.
2. **Separate frontend and backend deployments.** Rejected: two services, CORS configuration, no capability gain for a prototype.

## Consequences

- (+) Decision logic lives in one unit-tested Python module (`matching.py`) — the auditability goal of ADR-002 is strengthened.
- (+) No serverless execution limits; enables streamed server-side batch (ADR-007).
- (−) Loses Vercel's zero-config deploys; mitigated by the one-click `render.yaml` blueprint.
- (−) Single container is a single point of scale — acceptable and explicit for a prototype; horizontal scaling is a production concern.
