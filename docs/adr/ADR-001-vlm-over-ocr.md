# ADR-001: Use a Multimodal LLM Instead of a Traditional OCR Pipeline

**Status:** Accepted
**Date:** 2026-06-10

## Context

The core task is extracting fields (brand name, class/type, ABV, net contents, government warning) from alcohol label images and comparing them against application data. Label images are adversarial inputs for traditional OCR: stylized/decorative typefaces, curved bottle surfaces, off-angle photography, glare, and inconsistent lighting (explicitly raised by a junior agent in discovery).

A prior vendor pilot using a scanning/OCR approach failed on two fronts: per-label processing took 30–40 seconds (agents abandoned the tool), and stakeholders set a hard usability ceiling of ~5 seconds per label.

Additionally, field comparison requires *judgment*, not just string equality. A senior agent cited "STONE'S THROW" (label) vs. "Stone's Throw" (application) — technically a mismatch, substantively identical. A rules engine on top of OCR output handles this class of case poorly and accumulates brittle special cases.

## Decision

Use a multimodal LLM (Claude vision API) as the extraction and comparison engine. A single API call receives the label image plus the application's declared field values, and returns a structured, field-by-field comparison (via enforced JSON schema / tool use), including a verbatim transcription of the government warning text and per-field reasoning.

Model tier is configurable: a fast model (Haiku-class, ~2–4 s/label) as default to meet the 5-second ceiling, with a higher-accuracy model (Sonnet-class) selectable for harder images.

## Alternatives Considered

1. **Traditional OCR (Tesseract / PaddleOCR) + rules engine.** Rejected: poor accuracy on stylized label typography and imperfect photos; this is effectively the architecture that already failed in the vendor pilot. No capacity for fuzzy judgment.
2. **OCR + LLM hybrid (OCR for text, LLM for comparison).** Rejected: inherits OCR's accuracy floor as the bottleneck while adding pipeline complexity and latency.
3. **Fine-tuned vision model.** Rejected for a prototype: no labeled training corpus, long iteration cycle, and no evidence the accuracy gain is needed.

## Consequences

- (+) Handles imperfect images (angle, glare, lighting) with no preprocessing pipeline.
- (+) Naturally produces graded judgments ("substantive match, case differs") instead of binary string equality.
- (+) Single-call architecture keeps latency within the 5-second budget.
- (−) Per-label inference cost (API pricing) — acceptable at prototype scale; cost model documented in README.
- (−) LLM output is probabilistic; it must not be the sole authority for legally exact checks. Mitigated by ADR-002.
- (−) External API dependency conflicts with TTB's restrictive egress firewall *in production*. Out of scope for the externally hosted prototype; production path documented in ADR-004.
