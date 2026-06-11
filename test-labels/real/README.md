# Real-World Labels — TTB COLA Public Registry

Real, approved label artwork pulled from TTB's own [Public COLA Registry](https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do)
— the exact image format this tool would see in production. Source: **TTB ID
24009001000244** (Buffalo Trace Kentucky Straight Bourbon Whiskey, approved
Jan 2024; images are public records).

Application data to use (from the COLA filing):

```json
{
  "brand_name": "BUFFALO TRACE",
  "class_type": "Kentucky Straight Bourbon Whiskey",
  "alcohol_content": "45% Alc./Vol. (90 Proof)",
  "net_contents": "750 mL"
}
```

Observed results (local run, Claude Haiku):

| Image | Scenario | Verdict | Notes |
|---|---|---|---|
| `buffalo_trace_back.jpg` | Back label — carries ABV, net contents, and the government warning | **APPROVED** (3.0s) | All five checks pass; proof cross-check (90 = 2×45) and unit note triggered correctly |
| `buffalo_trace_front.png` | Front label only — warning lives on the back | **REJECTED** (2.0s) | `government_warning`, `alcohol_content`, `net_contents` flagged MISSING — the realistic "agent uploaded the wrong image" case |
| `buffalo_trace_back.jpg` vs application claiming 40% | Application/label disagreement | **REJECTED** (2.6s) | `ABV differs: application 40.0% vs label 45.0%` |

The front-label case is a deliberate keeper: real COLAs are multi-image
(front + back + neck), and a single-image check **must** reject rather than
assume the warning exists somewhere else. Multi-image-per-application support
is listed as future work in the main README.
