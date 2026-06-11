# ADR-003: Three-State Verdict (PASS / NEEDS REVIEW / FAIL)

**Status:** Accepted
**Date:** 2026-06-10

## Context

Discovery interviews surfaced a clear tension. Leadership wants automation of "routine matching." A 28-year senior agent warned that label review "has nuance" and cannot be fully pattern-matched, citing borderline cases that are technically mismatches but substantively fine. Prior modernization efforts at the agency failed partly through over-automation that ignored practitioner judgment.

A binary PASS/FAIL design forces the system to make exactly the judgment calls agents distrust automation for — and every wrong call erodes adoption.

## Decision

Every label receives one of three verdicts, computed per field and rolled up:

- **PASS** — all fields match within deterministic rules and high-confidence model judgment.
- **NEEDS REVIEW** — substantive match with discrepancies (case, punctuation, layout), or any low-confidence extraction, or visually ambiguous formatting attributes. The UI shows the specific field, the model's reasoning, and a one-click accept/reject for the agent.
- **FAIL** — deterministic violation (warning text mismatch, ABV numeric mismatch) or high-confidence substantive mismatch.

The tool's role is **triage, not adjudication**: it clears the unambiguous cases and concentrates agent attention on the ambiguous ones.

## Alternatives Considered

1. **Binary PASS/FAIL.** Rejected: forces the system to over-claim on borderline cases; misclassifications in either direction damage trust and adoption.
2. **Confidence score only (e.g., 0–100).** Rejected: pushes interpretation burden back onto agents ("is 73 ok?"); the team spans a wide range of technical comfort and needs categorical, glanceable results.

## Consequences

- (+) Aligns the tool with how agents describe their own work: routine cases automated, judgment preserved.
- (+) NEEDS REVIEW with reasoning doubles as an explainability surface — every flagged field shows *why*.
- (+) Thresholds (what confidence routes to review) are tunable in one place without UI changes.
- (−) Some throughput is "lost" to NEEDS REVIEW that a bolder system would auto-pass; this is deliberate. The conservative default can be relaxed as trust and measured accuracy accumulate.
