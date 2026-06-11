"""Deterministic comparison logic between application data and extracted label data.

Design notes:
- Extraction (vision) is probabilistic; comparison is deterministic and unit-tested.
- "Judgment" cases (Dave's STONE'S THROW example) resolve to MATCH with a note
  when the only differences are case/punctuation/whitespace, and NEEDS_REVIEW
  when strings are close but not normalization-equal.
- The government warning check is strict (Jenny's point): word-for-word against
  the statutory text (27 CFR 16.21) and the "GOVERNMENT WARNING:" header must be
  all caps and bold.
"""
import re
import unicodedata
from typing import Optional

from rapidfuzz import fuzz

from .schemas import (
    ApplicationData,
    CheckStatus,
    ExtractedLabel,
    FieldCheck,
    OverallStatus,
)

# Statutory health warning text, 27 CFR 16.21.
STATUTORY_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)

FUZZY_REVIEW_THRESHOLD = 80  # >= this (but not normalized-equal) -> NEEDS_REVIEW


def _normalize(s: str) -> str:
    """Case-fold, strip accents/punctuation, collapse whitespace."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = s.replace("’", "'")
    s = re.sub(r"[^a-z0-9%./ ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compare_text_field(
    field: str, app_value: Optional[str], label_value: Optional[str]
) -> FieldCheck:
    """Generic text comparison with normalization + fuzzy review band."""
    if not app_value:
        return FieldCheck(field=field, status=CheckStatus.not_checked)
    if not label_value:
        return FieldCheck(
            field=field,
            status=CheckStatus.missing,
            application_value=app_value,
            note="Not found on label.",
        )

    if app_value.strip() == label_value.strip():
        return FieldCheck(
            field=field,
            status=CheckStatus.match,
            application_value=app_value,
            label_value=label_value,
        )

    norm_app, norm_label = _normalize(app_value), _normalize(label_value)
    if norm_app == norm_label:
        return FieldCheck(
            field=field,
            status=CheckStatus.match,
            application_value=app_value,
            label_value=label_value,
            note="Matches after normalizing case/punctuation (e.g. STONE'S THROW vs Stone's Throw).",
        )

    score = fuzz.ratio(norm_app, norm_label)
    if score >= FUZZY_REVIEW_THRESHOLD:
        return FieldCheck(
            field=field,
            status=CheckStatus.needs_review,
            application_value=app_value,
            label_value=label_value,
            note=f"Close but not identical (similarity {score:.0f}/100). Agent judgment needed.",
        )
    return FieldCheck(
        field=field,
        status=CheckStatus.mismatch,
        application_value=app_value,
        label_value=label_value,
        note=f"Values differ (similarity {score:.0f}/100).",
    )


_NUM = r"(\d+(?:\.\d+)?)"


def _parse_abv(s: str) -> Optional[float]:
    """Pull the alcohol-by-volume percentage out of a string like
    '45% Alc./Vol. (90 Proof)' or 'ALC. 45% BY VOL.'"""
    m = re.search(_NUM + r"\s*%", s)
    if m:
        return float(m.group(1))
    m = re.search(r"%\s*" + _NUM, s)
    if m:
        return float(m.group(1))
    return None


def _parse_proof(s: str) -> Optional[float]:
    m = re.search(_NUM + r"\s*proof", s, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"proof\s*[:]?\s*" + _NUM, s, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def compare_alcohol_content(
    app_value: Optional[str], label_value: Optional[str]
) -> FieldCheck:
    """Numeric comparison: '45% Alc./Vol.' == 'ALC. 45.0% BY VOL.'.
    Also cross-checks proof when present (proof must equal 2x ABV)."""
    field = "alcohol_content"
    if not app_value:
        return FieldCheck(field=field, status=CheckStatus.not_checked)
    if not label_value:
        return FieldCheck(
            field=field,
            status=CheckStatus.missing,
            application_value=app_value,
            note="Alcohol content not found on label.",
        )

    app_abv, label_abv = _parse_abv(app_value), _parse_abv(label_value)
    if app_abv is None or label_abv is None:
        # Fall back to text comparison if we can't parse a percentage.
        check = compare_text_field(field, app_value, label_value)
        if check.status == CheckStatus.match:
            return check
        check.status = CheckStatus.needs_review
        check.note = "Could not parse ABV numerically; manual check advised."
        return check

    notes = []
    if app_abv != label_abv:
        return FieldCheck(
            field=field,
            status=CheckStatus.mismatch,
            application_value=app_value,
            label_value=label_value,
            note=f"ABV differs: application {app_abv}% vs label {label_abv}%.",
        )

    label_proof = _parse_proof(label_value)
    if label_proof is not None and abs(label_proof - 2 * label_abv) > 0.01:
        return FieldCheck(
            field=field,
            status=CheckStatus.mismatch,
            application_value=app_value,
            label_value=label_value,
            note=f"Proof inconsistent: {label_proof} proof should be {2 * label_abv} for {label_abv}% ABV.",
        )
    if label_proof is not None:
        notes.append(f"Proof cross-check OK ({label_proof} = 2 x {label_abv}%).")

    return FieldCheck(
        field=field,
        status=CheckStatus.match,
        application_value=app_value,
        label_value=label_value,
        note=" ".join(notes) or None,
    )


_UNIT_TO_ML = {
    "ml": 1.0,
    "milliliter": 1.0,
    "milliliters": 1.0,
    "cl": 10.0,
    "centiliter": 10.0,
    "centiliters": 10.0,
    "l": 1000.0,
    "liter": 1000.0,
    "liters": 1000.0,
    "litre": 1000.0,
    "litres": 1000.0,
    "oz": 29.5735,
    "fl oz": 29.5735,
    "fl. oz.": 29.5735,
}


def _parse_volume_ml(s: str) -> Optional[float]:
    m = re.search(
        _NUM + r"\s*(fl\.?\s*oz\.?|ml|cl|l(?:iters?|itres?)?|oz)\b",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None
    qty = float(m.group(1))
    unit = re.sub(r"[.\s]+", " ", m.group(2).lower()).strip()
    if unit.startswith("fl"):
        unit = "fl oz"
    return qty * _UNIT_TO_ML.get(unit, float("nan"))


def compare_net_contents(
    app_value: Optional[str], label_value: Optional[str]
) -> FieldCheck:
    """Unit-aware comparison: '750 mL' == '750ML' == '75 cl'."""
    field = "net_contents"
    if not app_value:
        return FieldCheck(field=field, status=CheckStatus.not_checked)
    if not label_value:
        return FieldCheck(
            field=field,
            status=CheckStatus.missing,
            application_value=app_value,
            note="Net contents not found on label.",
        )

    app_ml, label_ml = _parse_volume_ml(app_value), _parse_volume_ml(label_value)
    if app_ml is not None and label_ml is not None and label_ml == label_ml:  # not NaN
        if abs(app_ml - label_ml) < 0.5:
            note = None
            if _normalize(app_value) != _normalize(label_value):
                note = f"Equivalent volumes ({app_value} = {label_value})."
            return FieldCheck(
                field=field,
                status=CheckStatus.match,
                application_value=app_value,
                label_value=label_value,
                note=note,
            )
        return FieldCheck(
            field=field,
            status=CheckStatus.mismatch,
            application_value=app_value,
            label_value=label_value,
            note=f"Volumes differ: {app_ml:.0f} mL vs {label_ml:.0f} mL.",
        )
    return compare_text_field(field, app_value, label_value)


def _normalize_warning(s: str) -> str:
    """Whitespace-collapse only — wording and punctuation must be exact.
    Case is preserved for the body comparison done case-insensitively below;
    the header caps check is separate and strict."""
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()


def check_government_warning(extracted) -> FieldCheck:
    """Strict statutory warning check (27 CFR 16.21):
    - must be present
    - body must match word-for-word (whitespace-insensitive, case-insensitive body)
    - 'GOVERNMENT WARNING:' header must be ALL CAPS and bold
    - header formatting that cannot be confirmed from the image -> NEEDS_REVIEW
    """
    field = "government_warning"
    w = extracted.government_warning
    if not w.present or not w.text:
        return FieldCheck(
            field=field,
            status=CheckStatus.missing,
            application_value=STATUTORY_WARNING,
            note="Government warning statement not found on label. Mandatory on all alcohol beverages.",
        )

    label_text = _normalize_warning(w.text)
    required = _normalize_warning(STATUTORY_WARNING)
    problems = []

    # Word-for-word body check (case-insensitive — caps handled separately).
    if label_text.casefold() != required.casefold():
        sim = fuzz.ratio(label_text.casefold(), required.casefold())
        return FieldCheck(
            field=field,
            status=CheckStatus.mismatch,
            application_value=STATUTORY_WARNING,
            label_value=w.text,
            note=(
                f"Warning text does not match the statutory wording word-for-word "
                f"(similarity {sim:.0f}/100). The required text is fixed by 27 CFR 16.21."
            ),
        )

    # Header must literally read 'GOVERNMENT WARNING:' in all caps on the label.
    # The transcription is the primary evidence: the model is instructed to
    # preserve capitalization exactly, and its header_all_caps boolean has been
    # observed to contradict its own transcription (claiming caps over a
    # title-case header). The boolean can only downgrade a caps verdict —
    # never overrule a transcription that shows lowercase.
    header_caps = (
        label_text.startswith("GOVERNMENT WARNING:") and w.header_all_caps is not False
    )
    if not header_caps:
        problems.append("'GOVERNMENT WARNING:' must appear in capital letters.")
    if w.header_bold is False:
        problems.append("'GOVERNMENT WARNING:' must appear in bold type.")

    if problems:
        return FieldCheck(
            field=field,
            status=CheckStatus.mismatch,
            application_value=STATUTORY_WARNING,
            label_value=w.text,
            note=" ".join(problems),
        )

    if w.header_bold is None:
        # Conservative by design (ADR-002): an attribute we could not confirm is
        # routed to a human, never silently passed — the warning is the field
        # applicants most often try to game.
        return FieldCheck(
            field=field,
            status=CheckStatus.needs_review,
            application_value=STATUTORY_WARNING,
            label_value=w.text,
            note=(
                "Wording and capitalization verified; bold formatting of "
                "'GOVERNMENT WARNING:' could not be confirmed from the image — "
                "agent confirmation needed."
            ),
        )
    return FieldCheck(
        field=field,
        status=CheckStatus.match,
        application_value=STATUTORY_WARNING,
        label_value=w.text,
    )


def run_checks(app_data: ApplicationData, extracted: ExtractedLabel) -> list[FieldCheck]:
    checks = [
        compare_text_field("brand_name", app_data.brand_name, extracted.brand_name),
        compare_text_field("class_type", app_data.class_type, extracted.class_type),
        compare_alcohol_content(app_data.alcohol_content, extracted.alcohol_content),
        compare_net_contents(app_data.net_contents, extracted.net_contents),
        check_government_warning(extracted),
    ]
    if app_data.producer_name_address:
        checks.append(
            compare_text_field(
                "producer_name_address",
                app_data.producer_name_address,
                extracted.producer_name_address,
            )
        )
    if app_data.country_of_origin:
        checks.append(
            compare_text_field(
                "country_of_origin",
                app_data.country_of_origin,
                extracted.country_of_origin,
            )
        )
    return checks


def overall_status(checks: list[FieldCheck], extracted: ExtractedLabel) -> OverallStatus:
    if extracted.legibility == "unreadable":
        return OverallStatus.needs_review
    statuses = {c.status for c in checks}
    if CheckStatus.mismatch in statuses or CheckStatus.missing in statuses:
        return OverallStatus.rejected
    if CheckStatus.needs_review in statuses or extracted.legibility == "partial":
        return OverallStatus.needs_review
    return OverallStatus.approved


def summarize(status: OverallStatus, checks: list[FieldCheck], extracted: ExtractedLabel) -> str:
    bad = [c for c in checks if c.status in (CheckStatus.mismatch, CheckStatus.missing)]
    review = [c for c in checks if c.status == CheckStatus.needs_review]
    if status == OverallStatus.approved:
        return "All checks passed. Label matches the application."
    parts = []
    if bad:
        parts.append("Issues: " + "; ".join(f"{c.field} — {c.note or c.status.value}" for c in bad))
    if review:
        parts.append("Needs agent review: " + ", ".join(c.field for c in review))
    if extracted.legibility != "ok":
        parts.append(f"Image legibility: {extracted.legibility}. {extracted.image_quality_issues or ''}".strip())
    return " ".join(parts) or "Review required."
