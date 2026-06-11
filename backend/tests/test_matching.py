from app.matching import (
    STATUTORY_WARNING,
    check_government_warning,
    compare_alcohol_content,
    compare_net_contents,
    compare_text_field,
    overall_status,
    run_checks,
)
from app.schemas import (
    ApplicationData,
    CheckStatus,
    ExtractedLabel,
    ExtractedWarning,
    OverallStatus,
)


# --- brand name / generic text ------------------------------------------------

def test_exact_match():
    c = compare_text_field("brand_name", "OLD TOM DISTILLERY", "OLD TOM DISTILLERY")
    assert c.status == CheckStatus.match
    assert c.note is None


def test_dave_stones_throw_case():
    """Case/punctuation-only difference = MATCH with a note, not a rejection."""
    c = compare_text_field("brand_name", "Stone's Throw", "STONE'S THROW")
    assert c.status == CheckStatus.match
    assert c.note  # explains the normalization


def test_curly_apostrophe():
    c = compare_text_field("brand_name", "Stone's Throw", "STONE’S THROW")
    assert c.status == CheckStatus.match


def test_close_but_different_needs_review():
    c = compare_text_field("brand_name", "Old Tom Distillery", "Old Tom Distilling")
    assert c.status == CheckStatus.needs_review


def test_clear_mismatch():
    c = compare_text_field("brand_name", "OLD TOM DISTILLERY", "RIVERBEND VODKA")
    assert c.status == CheckStatus.mismatch


def test_missing_field():
    c = compare_text_field("brand_name", "OLD TOM", None)
    assert c.status == CheckStatus.missing


# --- alcohol content ----------------------------------------------------------

def test_abv_format_variants_match():
    c = compare_alcohol_content("45% Alc./Vol. (90 Proof)", "ALC. 45.0% BY VOL. 90 PROOF")
    assert c.status == CheckStatus.match


def test_abv_number_mismatch():
    c = compare_alcohol_content("45% Alc./Vol.", "40% Alc./Vol.")
    assert c.status == CheckStatus.mismatch


def test_proof_inconsistent_with_abv():
    c = compare_alcohol_content("45% Alc./Vol.", "45% Alc./Vol. (80 Proof)")
    assert c.status == CheckStatus.mismatch
    assert "Proof" in c.note


def test_unparseable_abv_falls_back_to_review():
    c = compare_alcohol_content("forty-five percent", "45 percent-ish")
    assert c.status == CheckStatus.needs_review


# --- net contents ---------------------------------------------------------

def test_net_contents_spacing_and_case():
    c = compare_net_contents("750 mL", "750ML")
    assert c.status == CheckStatus.match


def test_net_contents_unit_conversion():
    c = compare_net_contents("750 mL", "75 cl")
    assert c.status == CheckStatus.match
    assert "Equivalent" in c.note


def test_net_contents_mismatch():
    c = compare_net_contents("750 mL", "1 L")
    assert c.status == CheckStatus.mismatch


# --- government warning -------------------------------------------------------

def _warning(text=STATUTORY_WARNING, present=True, caps=True, bold=True):
    return ExtractedLabel(
        government_warning=ExtractedWarning(
            present=present, text=text, header_all_caps=caps, header_bold=bold
        )
    )


def test_warning_exact_passes():
    c = check_government_warning(_warning())
    assert c.status == CheckStatus.match


def test_warning_missing():
    c = check_government_warning(ExtractedLabel())
    assert c.status == CheckStatus.missing


def test_warning_title_case_header_rejected():
    """Jenny's catch: 'Government Warning' in title case must be rejected."""
    text = STATUTORY_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
    c = check_government_warning(_warning(text=text, caps=False))
    assert c.status == CheckStatus.mismatch
    assert "capital" in c.note.lower()


def test_warning_title_case_header_rejected_despite_model_boolean():
    """The vision model has been observed transcribing 'Government Warning:'
    correctly while wrongly reporting header_all_caps=True. The transcription
    is the primary evidence — the boolean must not overrule it."""
    text = STATUTORY_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
    c = check_government_warning(_warning(text=text, caps=True))
    assert c.status == CheckStatus.mismatch
    assert "capital" in c.note.lower()


def test_warning_not_bold_rejected():
    c = check_government_warning(_warning(bold=False))
    assert c.status == CheckStatus.mismatch
    assert "bold" in c.note.lower()


def test_warning_reworded_rejected():
    text = STATUTORY_WARNING.replace("birth defects", "complications")
    c = check_government_warning(_warning(text=text))
    assert c.status == CheckStatus.mismatch


def test_warning_whitespace_tolerated():
    text = STATUTORY_WARNING.replace(" (2)", "\n(2)")
    c = check_government_warning(_warning(text=text))
    assert c.status == CheckStatus.match


def test_warning_bold_unknown_needs_review():
    """Unconfirmable formatting is routed to a human, never silently passed
    (ADR-002) — the warning is the field applicants most often try to game."""
    c = check_government_warning(_warning(bold=None))
    assert c.status == CheckStatus.needs_review
    assert "bold" in c.note.lower()


# --- overall status -----------------------------------------------------------

APP = ApplicationData(
    brand_name="OLD TOM DISTILLERY",
    class_type="Kentucky Straight Bourbon Whiskey",
    alcohol_content="45% Alc./Vol. (90 Proof)",
    net_contents="750 mL",
)


def _good_label():
    return ExtractedLabel(
        brand_name="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content="45% ALC./VOL. (90 PROOF)",
        net_contents="750 mL",
        government_warning=ExtractedWarning(
            present=True, text=STATUTORY_WARNING, header_all_caps=True, header_bold=True
        ),
    )


def test_clean_label_approved():
    label = _good_label()
    checks = run_checks(APP, label)
    assert overall_status(checks, label) == OverallStatus.approved


def test_any_mismatch_rejects():
    label = _good_label()
    label.alcohol_content = "40% ALC./VOL."
    checks = run_checks(APP, label)
    assert overall_status(checks, label) == OverallStatus.rejected


def test_unreadable_image_needs_review():
    label = _good_label()
    label.legibility = "unreadable"
    checks = run_checks(APP, label)
    assert overall_status(checks, label) == OverallStatus.needs_review
