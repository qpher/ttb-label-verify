# Architecture Decision Records

Decision log for the TTB Label Verification prototype. Format follows Michael Nygard's ADR template (Context / Decision / Consequences), one decision per record. Superseded records are kept — the change history is part of the record.

| # | Title | Status |
|---|-------|--------|
| [ADR-001](./ADR-001-vlm-over-ocr.md) | Use a multimodal LLM instead of a traditional OCR pipeline | Accepted |
| [ADR-002](./ADR-002-deterministic-vs-llm-layers.md) | Separate deterministic validation from LLM judgment | Accepted |
| [ADR-003](./ADR-003-three-state-verdict.md) | Three-state verdict (PASS / NEEDS REVIEW / FAIL) | Accepted |
| [ADR-004](./ADR-004-stack-and-deployment.md) | Next.js full-stack on Vercel, stateless by design | Superseded by ADR-006 |
| [ADR-005](./ADR-005-batch-processing.md) | Client-orchestrated parallel batch with streaming results | Superseded by ADR-007 |
| [ADR-006](./ADR-006-fastapi-react-render.md) | FastAPI + React/Vite, single-container deploy on Render | Accepted |
| [ADR-007](./ADR-007-streamed-server-side-batch.md) | Server-side batch with bounded concurrency, streamed as NDJSON | Accepted |

## Reading order

ADR-001 and ADR-002 define the verification engine and are the load-bearing decisions; ADR-003 defines the product behavior built on them. ADR-006 and ADR-007 record how the delivery stack and batch design evolved during implementation — each preserves the commitments of the record it supersedes (statelessness, server-side keys, the streamed-progress UX requirement) while changing the mechanism.
