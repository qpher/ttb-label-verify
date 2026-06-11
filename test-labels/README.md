# Test Labels — Precision Attack Set

Programmatically rendered (`generate.py`, Pillow) rather than AI-generated on
purpose: the government warning is 60 words of statutory text that image
generation models reliably garble, and a precision test set needs exact,
known ground truth. **Every label varies exactly one thing** from the
canonical application data in `applications.csv` (all rows are identical), so
a wrong verdict points at a specific check.

`applications.csv` is ready for the batch tab: drop all 8 images + the CSV in
and the whole set runs in one go.

| File | What varies on the label | Expected verdict | Exercises |
|---|---|---|---|
| 01_clean_pass.png | nothing | **APPROVED** | happy path |
| 02_brand_title_case.png | brand printed `Old Tom Distillery` | **APPROVED**, match-with-note | normalization band (Dave's STONE'S THROW scenario) |
| 03_net_contents_75cl.png | net contents printed `75 cl` | **APPROVED**, equivalent-volume note | unit-aware volume comparison |
| 04_warning_title_case.png | header printed `Government Warning:` (bold, not caps) | **REJECTED** | header all-caps rule (Jenny's real rejection) |
| 05_warning_reworded.png | warning paraphrased | **REJECTED** | word-for-word statutory text check |
| 06_abv_mismatch.png | `43% Alc./Vol. (86 Proof)` (internally consistent) | **REJECTED** | numeric ABV comparison (not proof cross-check) |
| 07_warning_missing.png | no warning block | **REJECTED** | mandatory-presence check |
| 08_angled_glare.png | tilted photo, glare hotspot, slight blur | **APPROVED** (NEEDS REVIEW acceptable if legibility flagged) | vision robustness / legibility downgrade path |

Regenerate or extend: `python generate.py`.
