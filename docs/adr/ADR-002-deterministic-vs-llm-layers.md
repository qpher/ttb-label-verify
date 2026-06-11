# ADR-002: Separate Deterministic Validation from LLM Judgment

**Status:** Accepted
**Date:** 2026-06-10

## Context

Not all label checks have the same tolerance for interpretation:

- The **Government Health Warning Statement** must match the statutory text *verbatim*, with "GOVERNMENT WARNING:" in all capitals and bold. Agents report deliberate evasion attempts (reduced font size, reworded text, "Government Warning" in title case — a real rejection case).
- **Brand name / class-type comparison** legitimately requires judgment (case differences, punctuation, layout variations).

Relying on the LLM to simply answer "does the warning match?" risks a probabilistic yes/no on a question that is legally binary. Conversely, applying exact string matching to brand names reproduces the brittleness agents already complain about.

## Decision

Split verification into two layers with different trust models:

1. **LLM layer (extraction + judgment):** The model transcribes the warning text *verbatim* and reports formatting attributes as separate structured fields (`is_all_caps`, `appears_bold`, `relative_font_size`). For fuzzy fields (brand name, class/type), the model returns a graded judgment with reasoning.
2. **Deterministic layer (application code):** The transcribed warning text is normalized (whitespace-collapsed) and compared against the statutory text with an exact string match in code. The all-caps requirement on "GOVERNMENT WARNING:" is verified by code against the transcription, not taken from the model's opinion.

The final verdict for the warning field is computed in code from (transcription match) AND (formatting attributes). The LLM never directly outputs "warning: pass."

## Alternatives Considered

1. **LLM decides everything.** Rejected: unauditable for the legally exact check; a hallucinated "match" on the warning is the worst possible failure mode for this tool.
2. **Code decides everything (exact match on all fields).** Rejected: reintroduces the false-mismatch problem on brand names that motivated the project.

## Consequences

- (+) The legally exact check is auditable: the transcription is shown to the agent next to the statutory text, with the diff highlighted.
- (+) Each layer is applied where it is strong: code for exactness, model for judgment.
- (−) Transcription errors by the model can still cause false results; mitigated by displaying the transcription for human confirmation in NEEDS REVIEW cases (ADR-003).
- (−) Bold detection from a photo is inherently visual/approximate; it is reported as a model-judged attribute with confidence, and low confidence routes to NEEDS REVIEW rather than PASS.
